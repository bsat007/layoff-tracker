"""
Scraper for Layoffs.fyi - Tech Layoff Tracker
Uses airtable_scraper package to get ALL data from public Airtable views
"""
import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, date

from airtable_scraper import AirtableScraper

from config.settings import settings
from src.scrapers.base import BaseScraper, ScrapeError
from src.models.layoff import LayoffCreate

logger = logging.getLogger(__name__)


class LayoffsFyiScraper(BaseScraper):
    """
    Scraper for layoffs.fyi

    Source: https://layoffs.fyi/
    Tracks tech company layoffs since COVID-19
    
    Uses airtable_scraper package to get complete data from Airtable shared views.
    """

    # Airtable shared view URLs extracted from layoffs.fyi
    AIRTABLE_URLS = {
        'tech': "https://airtable.com/app1PaujS9zxVGUZ4/shroKsHx3SdYYOzeh",
        'federal': "https://airtable.com/app1PaujS9zxVGUZ4/shrJatoY0sANFEG3C"
    }
    
    # Column ID to name mapping for tech layoffs
    TECH_COLUMN_MAP = {
        'fld9AHA9YDoNhrVFQ': 'company',
        'fldeoYEol1GhizODE': 'location',
        'fldH1FcSF7DAaS1EB': 'employees_affected',
        'fldaRiRVH3vaD9DRC': 'layoff_date',
        'fldZRD6CwpFopYqqv': 'percentage',
        'fldZxgn3xoVqoHWuj': 'industry',
        'fldpt9Gt8PewUC1Sh': 'source_url',
        'fldoYp88YU5yEaK2P': 'stage',
        'fldiT8WOrVKce4LDj': 'raised_mm',
        'fldATTnRRO0iX7jr0': 'country',
        'fldwGtACkf7IYtRZ6': 'date_added'
    }

    def __init__(self, *args, include_federal: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_name = "layoffs.fyi"
        self.include_federal = include_federal

    @property
    def base_url(self) -> str:
        return settings.LAYOFFS_FYI_URL

    def fetch_layoffs(self) -> List[LayoffCreate]:
        """
        Fetch layoff data from layoffs.fyi via Airtable API

        Returns:
            List of LayoffCreate objects

        Raises:
            ScrapeError: If scraping fails
        """
        all_layoffs = []

        try:
            # Scrape tech layoffs
            logger.info("Fetching Tech Layoffs from layoffs.fyi...")
            tech_layoffs = self._scrape_airtable(
                url=self.AIRTABLE_URLS['tech'],
                source_name="layoffs.fyi",
                source_type='tech'
            )
            all_layoffs.extend(tech_layoffs)
            logger.info(f"Found {len(tech_layoffs)} tech layoff records")
            
            # Scrape federal layoffs if enabled
            if self.include_federal:
                logger.info("Fetching Federal Government Layoffs...")
                federal_layoffs = self._scrape_airtable(
                    url=self.AIRTABLE_URLS['federal'],
                    source_name="layoffs.fyi (Federal)",
                    source_type='federal'
                )
                all_layoffs.extend(federal_layoffs)
                logger.info(f"Found {len(federal_layoffs)} federal layoff records")

            logger.info(f"Total layoff records from {self.source_name}: {len(all_layoffs)}")

        except Exception as e:
            logger.error(f"Error scraping {self.source_name}: {e}")
            raise ScrapeError(f"Failed to scrape {self.source_name}: {e}")

        return all_layoffs
    
    def _scrape_airtable(self, url: str, source_name: str, source_type: str = 'tech') -> List[LayoffCreate]:
        """
        Scrape data from an Airtable shared view
        
        Args:
            url: Airtable shared view URL
            source_name: Name to use as the source
            source_type: Type of data ('tech' or 'federal')
            
        Returns:
            List of LayoffCreate objects
        """
        layoffs = []
        
        try:
            # Use airtable_scraper to get ALL data
            table = AirtableScraper(url=url)
            
            if table.status != 'success':
                logger.warning(f"Airtable scraper status: {table.status}")
            
            # Get raw data directly - more reliable than processed data
            raw_rows = table.raw_rows_json
            raw_columns = table.raw_columns_json
            
            if not raw_rows:
                logger.warning(f"No rows returned from {url}")
                return []
            
            logger.info(f"Retrieved {len(raw_rows)} raw rows from Airtable")
            
            # Build column ID to name mapping dynamically
            column_map = {}
            for col in raw_columns:
                col_id = col.get('id')
                col_name = col.get('name', '').lower().replace(' ', '_').replace('#', '').strip('_')
                column_map[col_id] = col_name
            
            logger.debug(f"Column mapping: {column_map}")
            
            # Process each row
            seen = set()
            for row in raw_rows:
                try:
                    cell_values = row.get('cellValuesByColumnId', {})
                    
                    # Extract company name (first column typically)
                    company = None
                    for col_id, value in cell_values.items():
                        col_name = column_map.get(col_id, '')
                        if 'company' in col_name or 'name' in col_name:
                            company = value if isinstance(value, str) else str(value) if value else None
                            break
                    
                    # Fallback: just use the first text value
                    if not company:
                        for value in cell_values.values():
                            if isinstance(value, str) and len(value) > 1:
                                company = value
                                break
                    
                    if not company or company in seen:
                        continue
                    
                    seen.add(company)
                    
                    # Extract other fields
                    employees_affected = None
                    layoff_date = None
                    industry = None
                    source_url = None
                    country = None
                    stage = None
                    percentage = None
                    
                    for col_id, value in cell_values.items():
                        col_name = column_map.get(col_id, '')
                        
                        # Skip if it's the company field
                        if 'company' in col_name or 'name' == col_name:
                            continue
                        
                        # Employees laid off
                        if any(x in col_name for x in ['laid_off', 'employees', 'affected', 'laid']):
                            if isinstance(value, (int, float)):
                                employees_affected = int(value)
                        
                        # Date
                        elif 'date' in col_name and 'added' not in col_name:
                            layoff_date = self._parse_airtable_date(value)
                        
                        # Industry
                        elif 'industry' in col_name:
                            industry = self._resolve_select_value(value, col_id, raw_columns)
                        
                        # Source URL
                        elif 'source' in col_name and 'url' not in col_name:
                            if isinstance(value, str) and value.startswith('http'):
                                source_url = value
                            elif isinstance(value, str):
                                source_url = value
                        
                        # Country
                        elif 'country' in col_name:
                            country = self._resolve_select_value(value, col_id, raw_columns)
                        
                        # Stage
                        elif 'stage' in col_name:
                            stage = self._resolve_select_value(value, col_id, raw_columns)
                        
                        # Percentage
                        elif '%' in column_map.get(col_id, '') or 'percent' in col_name:
                            if isinstance(value, (int, float)):
                                percentage = value
                    
                    # Default country for US-based tech companies
                    if not country:
                        country = "US"
                    
                    # For federal layoffs, set industry and country
                    if source_type == 'federal':
                        industry = "Government"
                        country = "US"
                    
                    # Create layoff object
                    layoff = LayoffCreate(
                        company_name=company[:200] if company else "Unknown",  # Truncate long names
                        industry=industry,
                        layoff_date=layoff_date or date.today(),
                        employees_affected=employees_affected,
                        employees_remaining=None,
                        source=source_name,
                        source_url=source_url or self.base_url,
                        country=country,
                        description=f"Stage: {stage}" if stage else None
                    )
                    layoffs.append(layoff)
                    
                except Exception as row_error:
                    logger.debug(f"Error processing row: {row_error}")
                    continue
            
        except Exception as e:
            logger.error(f"Error scraping Airtable {url}: {e}")
            raise
        
        return layoffs
    
    def _resolve_select_value(self, value: Any, col_id: str, columns: List[dict]) -> Optional[str]:
        """
        Resolve a select/multiSelect value to its display name
        
        Args:
            value: The cell value (could be an ID or list of IDs)
            col_id: The column ID
            columns: List of column definitions
            
        Returns:
            Resolved string value or None
        """
        if not value:
            return None
        
        if isinstance(value, str):
            # It might already be the actual value
            if not value.startswith('sel'):
                return value
        
        # Find the column definition
        col_def = None
        for col in columns:
            if col.get('id') == col_id:
                col_def = col
                break
        
        if not col_def:
            return str(value) if value else None
        
        # Get type options (choice definitions)
        type_options = col_def.get('typeOptions', {})
        choices = type_options.get('choices', type_options.get('choiceOrder', {}))
        
        if isinstance(choices, dict):
            # choices is a mapping of ID -> choice object
            if isinstance(value, str) and value in choices:
                choice = choices[value]
                return choice.get('name', str(value))
            elif isinstance(value, list):
                # Multi-select
                names = []
                for v in value:
                    if v in choices:
                        names.append(choices[v].get('name', str(v)))
                return ', '.join(names) if names else None
        
        return str(value) if value else None
    
    def _parse_airtable_date(self, value: Any) -> Optional[date]:
        """
        Parse Airtable date value
        
        Args:
            value: Date value from Airtable (ISO format string)
            
        Returns:
            date object or None
        """
        if not value:
            return None
        
        try:
            if isinstance(value, str):
                # Airtable returns dates in ISO format: 2025-12-28T00:00:00.000Z
                if 'T' in value:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt.date()
                # Also try DD/MM/YYYY format
                elif '/' in value:
                    parts = value.split('/')
                    if len(parts) == 3:
                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        return date(year, month, day)
        except (ValueError, IndexError) as e:
            logger.debug(f"Error parsing date {value}: {e}")
        
        return None
