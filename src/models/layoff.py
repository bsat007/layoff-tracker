"""
Data models for layoff information
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import hashlib


class LayoffCreate(BaseModel):
    """Model for creating a new layoff record"""
    company_name: str = Field(..., min_length=1, description="Name of the company")
    industry: Optional[str] = Field(None, description="Industry of the company")
    layoff_date: date = Field(..., description="Date of the layoff announcement")
    employees_affected: Optional[int] = Field(None, ge=0, description="Number of employees laid off")
    employees_remaining: Optional[int] = Field(None, ge=0, description="Number of remaining employees")
    source: str = Field(..., min_length=1, description="Source of the data (e.g., 'layoffs.fyi')")
    source_url: str = Field(..., min_length=1, description="URL to the source")
    country: str = Field(default="US", description="Country where layoff occurred")
    description: Optional[str] = Field(None, description="Additional description or context")

    @field_validator('layoff_date')
    @classmethod
    def layoff_date_not_future(cls, v: date) -> date:
        """Validate that layoff date is not in the future"""
        if v > date.today():
            raise ValueError("Layoff date cannot be in the future")
        return v

    @field_validator('company_name')
    @classmethod
    def normalize_company_name(cls, v: str) -> str:
        """Normalize company name (strip, title case)"""
        return v.strip().title()


class Layoff(LayoffCreate):
    """Complete layoff model with database fields"""
    id: int = Field(..., description="Database ID")
    unique_id: str = Field(..., description="Unique hash for deduplication")
    scraped_at: datetime = Field(default_factory=datetime.now, description="When this record was scraped")

    class Config:
        from_attributes = True


    @classmethod
    def generate_unique_id(cls, company_name: str, layoff_date: date, source: str) -> str:
        """
        Generate a unique ID for deduplication based on company + date + source
        """
        # Create a unique string from the combination
        unique_str = f"{company_name.lower()}_{layoff_date}_{source.lower()}"

        # Generate hash
        hash_obj = hashlib.md5(unique_str.encode())
        return hash_obj.hexdigest()


    @classmethod
    def from_create(cls, layoff_create: LayoffCreate, id: int = None) -> "Layoff":
        """
        Create a Layoff instance from LayoffCreate with generated unique_id
        """
        unique_id = cls.generate_unique_id(
            layoff_create.company_name,
            layoff_create.layoff_date,
            layoff_create.source
        )

        return cls(
            id=id or 0,  # Will be set by database
            unique_id=unique_id,
            scraped_at=datetime.now(),
            **layoff_create.model_dump()
        )


    def to_dict(self) -> dict:
        """Convert layoff to dictionary"""
        return {
            "id": self.id,
            "company_name": self.company_name,
            "industry": self.industry,
            "layoff_date": self.layoff_date.isoformat() if self.layoff_date else None,
            "employees_affected": self.employees_affected,
            "employees_remaining": self.employees_remaining,
            "source": self.source,
            "source_url": self.source_url,
            "country": self.country,
            "description": self.description,
            "unique_id": self.unique_id,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
        }
