"""
Database manager for layoff data
"""
import logging
from datetime import datetime, date
from typing import List, Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from config.settings import settings
from src.models.layoff import Layoff, LayoffCreate

# Setup logging
logger = logging.getLogger(__name__)

# Create base class for models
Base = declarative_base()


class LayoffModel(Base):
    """SQLAlchemy model for layoff data"""
    __tablename__ = "layoffs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(255), nullable=False, index=True)
    industry = Column(String(255), nullable=True)
    layoff_date = Column(Date, nullable=False, index=True)
    employees_affected = Column(Integer, nullable=True)
    employees_remaining = Column(Integer, nullable=True)
    source = Column(String(100), nullable=False, index=True)
    source_url = Column(Text, nullable=False)
    country = Column(String(100), nullable=False, default="US")
    description = Column(Text, nullable=True)
    unique_id = Column(String(32), nullable=False, unique=True, index=True)
    scraped_at = Column(DateTime, nullable=False, default=datetime.now)

    # Composite index for common queries
    __table_args__ = (
        Index('idx_layoff_date_source', 'layoff_date', 'source'),
        Index('idx_company_layoff_date', 'company_name', 'layoff_date'),
    )


class DatabaseManager:
    """Manager for database operations"""

    def __init__(self, database_url: str = None):
        """
        Initialize database manager

        Args:
            database_url: Database connection URL. Defaults to settings.DATABASE_URL
        """
        self.database_url = database_url or settings.DATABASE_URL
        self.engine = create_engine(
            self.database_url,
            echo=False,  # Set to True for SQL query logging
            connect_args={"check_same_thread": False} if "sqlite" in self.database_url else {}
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        logger.info(f"Database initialized: {self.database_url}")

    def create_tables(self):
        """Create all tables in the database"""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")

    def drop_tables(self):
        """Drop all tables from the database (use with caution!)"""
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("Database tables dropped")

    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for database sessions

        Yields:
            Session: SQLAlchemy session
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def add_layoff(self, layoff_create: LayoffCreate) -> Optional[Layoff]:
        """
        Add a layoff record to the database

        Args:
            layoff_create: Layoff data to add

        Returns:
            Layoff: Created layoff record or None if duplicate
        """
        try:
            with self.get_session() as session:
                # Check for duplicate
                unique_id = Layoff.generate_unique_id(
                    layoff_create.company_name,
                    layoff_create.layoff_date,
                    layoff_create.source
                )

                existing = session.query(LayoffModel).filter(
                    LayoffModel.unique_id == unique_id
                ).first()

                if existing:
                    logger.debug(f"Duplicate layoff found: {layoff_create.company_name} on {layoff_create.layoff_date}")
                    return None

                # Create new record
                db_layoff = LayoffModel(
                    company_name=layoff_create.company_name,
                    industry=layoff_create.industry,
                    layoff_date=layoff_create.layoff_date,
                    employees_affected=layoff_create.employees_affected,
                    employees_remaining=layoff_create.employees_remaining,
                    source=layoff_create.source,
                    source_url=layoff_create.source_url,
                    country=layoff_create.country,
                    description=layoff_create.description,
                    unique_id=unique_id,
                    scraped_at=datetime.now()
                )

                session.add(db_layoff)
                session.flush()  # Get the ID before commit
                session.refresh(db_layoff)

                logger.info(f"Added layoff: {layoff_create.company_name} ({layoff_create.employees_affected} employees)")

                return Layoff.from_create(layoff_create, id=db_layoff.id)

        except IntegrityError as e:
            logger.warning(f"Integrity error adding layoff: {e}")
            return None
        except Exception as e:
            logger.error(f"Error adding layoff: {e}")
            raise

    def add_layoffs_batch(self, layoffs: List[LayoffCreate]) -> int:
        """
        Add multiple layoff records to the database

        Args:
            layoffs: List of layoff data to add

        Returns:
            int: Number of records successfully added
        """
        added_count = 0

        try:
            with self.get_session() as session:
                for layoff_create in layoffs:
                    # Check for duplicate
                    unique_id = Layoff.generate_unique_id(
                        layoff_create.company_name,
                        layoff_create.layoff_date,
                        layoff_create.source
                    )

                    existing = session.query(LayoffModel).filter(
                        LayoffModel.unique_id == unique_id
                    ).first()

                    if existing:
                        continue

                    # Create new record
                    db_layoff = LayoffModel(
                        company_name=layoff_create.company_name,
                        industry=layoff_create.industry,
                        layoff_date=layoff_create.layoff_date,
                        employees_affected=layoff_create.employees_affected,
                        employees_remaining=layoff_create.employees_remaining,
                        source=layoff_create.source,
                        source_url=layoff_create.source_url,
                        country=layoff_create.country,
                        description=layoff_create.description,
                        unique_id=unique_id,
                        scraped_at=datetime.now()
                    )

                    session.add(db_layoff)
                    added_count += 1

                logger.info(f"Added {added_count} layoff records (batch)")
                return added_count

        except Exception as e:
            logger.error(f"Error adding layoffs in batch: {e}")
            raise

    def get_all_layoffs(self, limit: int = None) -> List[Layoff]:
        """
        Get all layoff records

        Args:
            limit: Maximum number of records to return

        Returns:
            List of layoff records
        """
        try:
            with self.get_session() as session:
                query = session.query(LayoffModel).order_by(LayoffModel.layoff_date.desc())

                if limit:
                    query = query.limit(limit)

                db_layoffs = query.all()

                return [
                    Layoff(
                        id=l.id,
                        company_name=l.company_name,
                        industry=l.industry,
                        layoff_date=l.layoff_date,
                        employees_affected=l.employees_affected,
                        employees_remaining=l.employees_remaining,
                        source=l.source,
                        source_url=l.source_url,
                        country=l.country,
                        description=l.description,
                        unique_id=l.unique_id,
                        scraped_at=l.scraped_at
                    )
                    for l in db_layoffs
                ]

        except Exception as e:
            logger.error(f"Error getting all layoffs: {e}")
            raise

    def get_layoff_by_id(self, layoff_id: int) -> Optional[Layoff]:
        """
        Get a specific layoff by ID

        Args:
            layoff_id: The ID of the layoff to retrieve

        Returns:
            Layoff record or None if not found
        """
        try:
            with self.get_session() as session:
                db_layoff = session.query(LayoffModel).filter(
                    LayoffModel.id == layoff_id
                ).first()

                if not db_layoff:
                    return None

                return Layoff(
                    id=db_layoff.id,
                    company_name=db_layoff.company_name,
                    industry=db_layoff.industry,
                    layoff_date=db_layoff.layoff_date,
                    employees_affected=db_layoff.employees_affected,
                    employees_remaining=db_layoff.employees_remaining,
                    source=db_layoff.source,
                    source_url=db_layoff.source_url,
                    country=db_layoff.country,
                    description=db_layoff.description,
                    unique_id=db_layoff.unique_id,
                    scraped_at=db_layoff.scraped_at
                )

        except Exception as e:
            logger.error(f"Error getting layoff by id {layoff_id}: {e}")
            raise

    def get_layoffs_by_date_range(
        self,
        start_date: date,
        end_date: date,
        limit: int = None
    ) -> List[Layoff]:
        """
        Get layoff records within a date range

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            limit: Maximum number of records to return

        Returns:
            List of layoff records
        """
        try:
            with self.get_session() as session:
                query = session.query(LayoffModel).filter(
                    LayoffModel.layoff_date >= start_date,
                    LayoffModel.layoff_date <= end_date
                ).order_by(LayoffModel.layoff_date.desc())

                if limit:
                    query = query.limit(limit)

                db_layoffs = query.all()

                return [
                    Layoff(
                        id=l.id,
                        company_name=l.company_name,
                        industry=l.industry,
                        layoff_date=l.layoff_date,
                        employees_affected=l.employees_affected,
                        employees_remaining=l.employees_remaining,
                        source=l.source,
                        source_url=l.source_url,
                        country=l.country,
                        description=l.description,
                        unique_id=l.unique_id,
                        scraped_at=l.scraped_at
                    )
                    for l in db_layoffs
                ]

        except Exception as e:
            logger.error(f"Error getting layoffs by date range: {e}")
            raise

    def get_layoffs_by_company(self, company_name: str) -> List[Layoff]:
        """
        Get all layoff records for a specific company

        Args:
            company_name: Name of the company

        Returns:
            List of layoff records
        """
        try:
            with self.get_session() as session:
                db_layoffs = session.query(LayoffModel).filter(
                    LayoffModel.company_name.ilike(f"%{company_name}%")
                ).order_by(LayoffModel.layoff_date.desc()).all()

                return [
                    Layoff(
                        id=l.id,
                        company_name=l.company_name,
                        industry=l.industry,
                        layoff_date=l.layoff_date,
                        employees_affected=l.employees_affected,
                        employees_remaining=l.employees_remaining,
                        source=l.source,
                        source_url=l.source_url,
                        country=l.country,
                        description=l.description,
                        unique_id=l.unique_id,
                        scraped_at=l.scraped_at
                    )
                    for l in db_layoffs
                ]

        except Exception as e:
            logger.error(f"Error getting layoffs by company: {e}")
            raise

    def get_statistics(self) -> dict:
        """
        Get overall statistics about layoff data

        Returns:
            Dictionary with statistics
        """
        try:
            with self.get_session() as session:
                total_companies = session.query(LayoffModel.company_name).distinct().count()
                total_records = session.query(LayoffModel).count()
                total_affected = session.query(LayoffModel.employees_affected).filter(
                    LayoffModel.employees_affected.isnot(None)
                ).all()

                total_affected_sum = sum([x[0] for x in total_affected])

                # Get date range
                earliest = session.query(LayoffModel.layoff_date).order_by(LayoffModel.layoff_date.asc()).first()
                latest = session.query(LayoffModel.layoff_date).order_by(LayoffModel.layoff_date.desc()).first()

                # Get top sources
                source_counts = session.query(
                    LayoffModel.source,
                    session.query(LayoffModel).filter(LayoffModel.source == LayoffModel.source).count()
                ).group_by(LayoffModel.source).all()

                return {
                    "total_companies": total_companies,
                    "total_records": total_records,
                    "total_affected": total_affected_sum,
                    "date_range": {
                        "earliest": earliest[0] if earliest else None,
                        "latest": latest[0] if latest else None
                    },
                }

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise
