#!/usr/bin/env python3
"""
Test script to verify the entire pipeline works
Adds sample data to test database, export, and dashboard functionality
"""
import sys
from pathlib import Path
from datetime import date, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging
from src.storage.database import DatabaseManager
from src.models.layoff import LayoffCreate

logger = setup_logging()


def add_sample_data():
    """Add sample layoff data for testing"""

    db_manager = DatabaseManager()

    # Sample layoffs based on real 2024-2025 data
    sample_layoffs = [
        LayoffCreate(
            company_name="Google",
            industry="Technology",
            layoff_date=date(2024, 1, 15),
            employees_affected=1000,
            employees_remaining=140000,
            source="layoffs.fyi",
            source_url="https://layoffs.fyi/",
            country="US",
            description=" layoffs in hardware and engineering teams"
        ),
        LayoffCreate(
            company_name="Amazon",
            industry="E-commerce",
            layoff_date=date(2024, 1, 20),
            employees_affected=18000,
            employees_remaining=1420000,
            source="layoffs.fyi",
            source_url="https://layoffs.fyi/",
            country="US",
            description="Prime Video and AWS Studios cuts"
        ),
        LayoffCreate(
            company_name="Microsoft",
            industry="Technology",
            layoff_date=date(2024, 1, 25),
            employees_affected=1900,
            employees_remaining=220000,
            source="trueup.io",
            source_url="https://www.trueup.io/layoffs",
            country="US",
            description="Gaming division layoffs"
        ),
        LayoffCreate(
            company_name="Salesforce",
            industry="Software",
            layoff_date=date(2024, 2, 1),
            employees_affected=700,
            employees_remaining=72000,
            source="layoffs.fyi",
            source_url="https://layoffs.fyi/",
            country="US",
            description="Post-sales workforce reduction"
        ),
        LayoffCreate(
            company_name="Meta",
            industry="Technology",
            layoff_date=date(2024, 2, 10),
            employees_affected=2000,
            employees_remaining=67000,
            source="trueup.io",
            source_url="https://www.trueup.io/layoffs",
            country="US",
            description="Technical program management cuts"
        ),
        LayoffCreate(
            company_name="PayPal",
            industry="Fintech",
            layoff_date=date(2024, 2, 15),
            employees_affected=2500,
            employees_remaining=23500,
            source="layoffs.fyi",
            source_url="https://layoffs.fyi/",
            country="US",
            description="Company-wide restructuring"
        ),
        LayoffCreate(
            company_name="Disney",
            industry="Entertainment",
            layoff_date=date(2024, 3, 1),
            employees_affected=7000,
            employees_remaining=200000,
            source="warntracker.com",
            source_url="https://www.warntracker.com/",
            country="US",
            description="Entertainment division cuts"
        ),
        LayoffCreate(
            company_name="Zoom",
            industry="Technology",
            layoff_date=date(2024, 3, 10),
            employees_affected=1300,
            employees_remaining=8500,
            source="layoffdata.com",
            source_url="https://layoffdata.com/",
            country="US",
            description="Workforce reduction amid slowing growth"
        ),
        LayoffCreate(
            company_name="Dell",
            industry="Hardware",
            layoff_date=date(2024, 3, 15),
            employees_affected=5000,
            employees_remaining=120000,
            source="warntracker.com",
            source_url="https://www.warntracker.com/",
            country="US",
            description="Global workforce reduction"
        ),
        LayoffCreate(
            company_name="eBay",
            industry="E-commerce",
            layoff_date=date(2024, 3, 20),
            employees_affected=1000,
            employees_remaining=10800,
            source="layoffs.fyi",
            source_url="https://layoffs.fyi/",
            country="US",
            description="Organizational restructuring"
        ),
        # Recent 2025 data
        LayoffCreate(
            company_name="Tesla",
            industry="Automotive",
            layoff_date=date(2025, 1, 5),
            employees_affected=3000,
            employees_remaining=120000,
            source="trueup.io",
            source_url="https://www.trueup.io/layoffs",
            country="US",
            description="Supercharger team layoffs"
        ),
        LayoffCreate(
            company_name="Unity",
            industry="Gaming",
            layoff_date=date(2025, 1, 10),
            employees_affected=2600,
            employees_remaining=7000,
            source="layoffs.fyi",
            source_url="https://layoffs.fyi/",
            country="US",
            description="Company-wide reset"
        ),
    ]

    logger.info(f"Adding {len(sample_layoffs)} sample layoff records...")

    added_count = 0
    for layoff in sample_layoffs:
        result = db_manager.add_layoff(layoff)
        if result:
            added_count += 1
            logger.info(f"✓ Added: {layoff.company_name} - {layoff.employees_affected} employees")
        else:
            logger.warning(f"✗ Skipped (duplicate): {layoff.company_name}")

    logger.info(f"\nTotal records added: {added_count}/{len(sample_layoffs)}")

    # Get statistics
    stats = db_manager.get_statistics()
    logger.info(f"\nDatabase Statistics:")
    logger.info(f"  Total companies: {stats['total_companies']}")
    logger.info(f"  Total records: {stats['total_records']}")
    logger.info(f"  Total affected: {stats['total_affected']}")
    logger.info(f"  Date range: {stats['date_range']['earliest']} to {stats['date_range']['latest']}")

    return added_count


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Adding Sample Data for Testing")
    logger.info("=" * 60)

    count = add_sample_data()

    logger.info("\n✅ Sample data added successfully!")
    logger.info("You can now:")
    logger.info("  1. View data in the database: data/layoffs.db")
    logger.info("  2. Export data: python -m src.main export")
    logger.info("  3. Launch dashboard: python -m src.main dashboard")
