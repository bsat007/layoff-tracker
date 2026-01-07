"""
Additional Layoff Scrapers for:
- LayoffsTracker.com (Airtable via airtable_scraper)
- Peerlist.io (HTML tables)
- OfficePulse.live (HTML tables - India focused)
"""
import logging
import re
from typing import List, Optional, Any
from datetime import datetime, date
from playwright.sync_api import sync_playwright

from airtable_scraper import AirtableScraper

from config.settings import settings
from src.scrapers.base import BaseScraper, ScrapeError
from src.models.layoff import LayoffCreate

logger = logging.getLogger(__name__)


class LayoffsTrackerScraper(BaseScraper):
    """
    Scraper for layoffstracker.com
    
    Source: https://layoffstracker.com/
    Uses airtable_scraper package to get ALL data from the Airtable shared view
    """
    
    BASE_URL = "https://layoffstracker.com/"
    AIRTABLE_URL = "https://airtable.com/shrclnXK0pfoGjtih"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_name = "layoffstracker.com"
    
    @property
    def base_url(self) -> str:
        return self.BASE_URL
    
    def fetch_layoffs(self) -> List[LayoffCreate]:
        """Fetch layoffs from layoffstracker.com via Airtable API"""
        layoffs = []
        
        try:
            logger.info(f"Fetching layoffs from {self.source_name} via Airtable...")
            
            # Use airtable_scraper to get ALL data
            table = AirtableScraper(url=self.AIRTABLE_URL)
            
            if table.status != 'success':
                logger.warning(f"Airtable scraper status: {table.status}")
            
            # Get raw data
            raw_rows = table.raw_rows_json
            raw_columns = table.raw_columns_json
            
            if not raw_rows:
                logger.warning(f"No rows returned from {self.AIRTABLE_URL}")
                return []
            
            logger.info(f"Retrieved {len(raw_rows)} raw rows from Airtable")
            
            # Build column ID to name mapping
            column_map = {}
            for col in raw_columns:
                col_id = col.get('id')
                col_name = col.get('name', '').lower().replace(' ', '_').replace('#', '').strip('_')
                column_map[col_id] = col_name
            
            # Process each row
            seen = set()
            for row in raw_rows:
                try:
                    cell_values = row.get('cellValuesByColumnId', {})
                    
                    # Extract fields based on column mapping
                    company = None
                    employees_affected = None
                    layoff_date = None
                    industry = None
                    source_url = None
                    country = None
                    location = None
                    
                    for col_id, value in cell_values.items():
                        col_name = column_map.get(col_id, '')
                        
                        # Company name
                        if 'company' in col_name:
                            company = value if isinstance(value, str) else str(value) if value else None
                        
                        # Employees laid off
                        elif 'laid_off' in col_name or col_name == 'laid':
                            if isinstance(value, (int, float)):
                                employees_affected = int(value)
                        
                        # Date
                        elif 'date' in col_name and 'added' not in col_name:
                            layoff_date = self._parse_airtable_date(value)
                        
                        # Industry
                        elif 'industry' in col_name:
                            industry = self._resolve_select_value(value, col_id, raw_columns)
                        
                        # Source URL
                        elif col_name == 'source':
                            if isinstance(value, str):
                                source_url = value if value.startswith('http') else None
                        
                        # Country
                        elif 'country' in col_name:
                            country = self._resolve_select_value(value, col_id, raw_columns)
                        
                        # Location
                        elif 'location' in col_name:
                            location = self._resolve_select_value(value, col_id, raw_columns)
                    
                    if not company or company in seen:
                        continue
                    
                    seen.add(company)
                    
                    # Default country
                    if not country:
                        country = "US"
                    
                    layoff = LayoffCreate(
                        company_name=company[:200] if company else "Unknown",
                        industry=industry,
                        layoff_date=layoff_date or date.today(),
                        employees_affected=employees_affected,
                        employees_remaining=None,
                        source=self.source_name,
                        source_url=source_url or self.base_url,
                        country=country,
                        description=f"Location: {location}" if location else None
                    )
                    layoffs.append(layoff)
                    
                except Exception as row_error:
                    logger.debug(f"Error processing row: {row_error}")
                    continue
            
            logger.info(f"Found {len(layoffs)} layoffs from {self.source_name}")
            
        except Exception as e:
            logger.error(f"Error scraping {self.source_name}: {e}")
            raise ScrapeError(f"Failed to scrape {self.source_name}: {e}")
        
        return layoffs
    
    def _resolve_select_value(self, value: Any, col_id: str, columns: List[dict]) -> Optional[str]:
        """Resolve a select/multiSelect value to its display name"""
        if not value:
            return None
        
        if isinstance(value, str) and not value.startswith('sel'):
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
            if isinstance(value, str) and value in choices:
                choice = choices[value]
                return choice.get('name', str(value))
            elif isinstance(value, list):
                names = []
                for v in value:
                    if v in choices:
                        names.append(choices[v].get('name', str(v)))
                return ', '.join(names) if names else None
        
        return str(value) if value else None
    
    def _parse_airtable_date(self, value: Any) -> Optional[date]:
        """Parse Airtable date value (ISO format)"""
        if not value:
            return None
        
        try:
            if isinstance(value, str):
                if 'T' in value:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt.date()
                elif '/' in value:
                    parts = value.split('/')
                    if len(parts) == 3:
                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        return date(year, month, day)
        except (ValueError, IndexError) as e:
            logger.debug(f"Error parsing date {value}: {e}")
        
        return None


class LayoffsTrackerNonTechScraper(BaseScraper):
    """
    Scraper for layoffstracker.com Non-Tech Layoffs
    
    Source: https://layoffstracker.com/non-tech-layoffs/
    Uses airtable_scraper package to get ALL data from the Airtable shared view
    Tracks non-tech layoffs from various industries
    """
    
    BASE_URL = "https://layoffstracker.com/non-tech-layoffs/"
    AIRTABLE_URL = "https://airtable.com/shr7MSwwevBnoS5fV"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_name = "layoffstracker.com (Non-Tech)"
    
    @property
    def base_url(self) -> str:
        return self.BASE_URL
    
    def fetch_layoffs(self) -> List[LayoffCreate]:
        """Fetch non-tech layoffs from layoffstracker.com via Airtable API"""
        layoffs = []
        
        try:
            logger.info(f"Fetching non-tech layoffs from {self.source_name} via Airtable...")
            
            # Use airtable_scraper to get ALL data
            table = AirtableScraper(url=self.AIRTABLE_URL)
            
            if table.status != 'success':
                logger.warning(f"Airtable scraper status: {table.status}")
            
            # Get raw data
            raw_rows = table.raw_rows_json
            raw_columns = table.raw_columns_json
            
            if not raw_rows:
                logger.warning(f"No rows returned from {self.AIRTABLE_URL}")
                return []
            
            logger.info(f"Retrieved {len(raw_rows)} raw rows from Airtable (Non-Tech)")
            
            # Build column ID to name mapping
            column_map = {}
            for col in raw_columns:
                col_id = col.get('id')
                col_name = col.get('name', '').lower().replace(' ', '_').replace('#', '').strip('_')
                column_map[col_id] = col_name
            
            logger.debug(f"Non-Tech column mapping: {column_map}")
            
            # Process each row
            seen = set()
            for row in raw_rows:
                try:
                    cell_values = row.get('cellValuesByColumnId', {})
                    
                    # Extract fields based on column mapping
                    company = None
                    employees_affected = None
                    layoff_date = None
                    industry = None
                    source_url = None
                    country = None
                    location = None
                    percentage = None
                    
                    for col_id, value in cell_values.items():
                        col_name = column_map.get(col_id, '')
                        
                        # Company name
                        if 'company' in col_name or 'name' == col_name:
                            company = value if isinstance(value, str) else str(value) if value else None
                        
                        # Employees laid off
                        elif any(x in col_name for x in ['laid_off', 'employees', 'affected', 'laid']):
                            if isinstance(value, (int, float)):
                                employees_affected = int(value)
                        
                        # Date
                        elif 'date' in col_name and 'added' not in col_name:
                            layoff_date = self._parse_airtable_date(value)
                        
                        # Industry / Category
                        elif any(x in col_name for x in ['industry', 'category', 'sector']):
                            industry = self._resolve_select_value(value, col_id, raw_columns)
                        
                        # Source URL
                        elif col_name == 'source' or 'link' in col_name or 'url' in col_name:
                            if isinstance(value, str):
                                source_url = value if value.startswith('http') else None
                        
                        # Country
                        elif 'country' in col_name:
                            country = self._resolve_select_value(value, col_id, raw_columns)
                        
                        # Location / HQ
                        elif any(x in col_name for x in ['location', 'hq', 'headquarter']):
                            location = self._resolve_select_value(value, col_id, raw_columns)
                        
                        # Percentage
                        elif '%' in column_map.get(col_id, '') or 'percent' in col_name:
                            if isinstance(value, (int, float)):
                                percentage = value
                    
                    if not company or company in seen:
                        continue
                    
                    seen.add(company)
                    
                    # Default country
                    if not country:
                        country = "US"
                    
                    # Build description
                    desc_parts = []
                    if location:
                        desc_parts.append(f"Location: {location}")
                    if percentage:
                        desc_parts.append(f"Percentage: {percentage}%")
                    
                    layoff = LayoffCreate(
                        company_name=company[:200] if company else "Unknown",
                        industry=industry,
                        layoff_date=layoff_date or date.today(),
                        employees_affected=employees_affected,
                        employees_remaining=None,
                        source=self.source_name,
                        source_url=source_url or self.base_url,
                        country=country,
                        description="; ".join(desc_parts) if desc_parts else None
                    )
                    layoffs.append(layoff)
                    
                except Exception as row_error:
                    logger.debug(f"Error processing non-tech row: {row_error}")
                    continue
            
            logger.info(f"Found {len(layoffs)} non-tech layoffs from {self.source_name}")
            
        except Exception as e:
            logger.error(f"Error scraping {self.source_name}: {e}")
            raise ScrapeError(f"Failed to scrape {self.source_name}: {e}")
        
        return layoffs
    
    def _resolve_select_value(self, value: Any, col_id: str, columns: List[dict]) -> Optional[str]:
        """Resolve a select/multiSelect value to its display name"""
        if not value:
            return None
        
        if isinstance(value, str) and not value.startswith('sel'):
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
            if isinstance(value, str) and value in choices:
                choice = choices[value]
                return choice.get('name', str(value))
            elif isinstance(value, list):
                names = []
                for v in value:
                    if v in choices:
                        names.append(choices[v].get('name', str(v)))
                return ', '.join(names) if names else None
        
        return str(value) if value else None
    
    def _parse_airtable_date(self, value: Any) -> Optional[date]:
        """Parse Airtable date value (ISO format)"""
        if not value:
            return None
        
        try:
            if isinstance(value, str):
                if 'T' in value:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt.date()
                elif '/' in value:
                    parts = value.split('/')
                    if len(parts) == 3:
                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        return date(year, month, day)
        except (ValueError, IndexError) as e:
            logger.debug(f"Error parsing date {value}: {e}")
        
        return None


class PeerlistScraper(BaseScraper):
    """
    Scraper for peerlist.io/layoffs-tracker
    
    Source: https://peerlist.io/layoffs-tracker/
    Uses HTML tables organized by month
    """
    
    BASE_URL = "https://peerlist.io/layoffs-tracker/{year}"
    
    def __init__(self, *args, years: List[int] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_name = "peerlist.io"
        current_year = date.today().year
        # Use current year -1, -2 since current year may not have much data at start
        self.years = years or [current_year - 1, current_year - 2]
    
    @property
    def base_url(self) -> str:
        return self.BASE_URL.format(year=date.today().year)
    
    def fetch_layoffs(self) -> List[LayoffCreate]:
        """Fetch layoffs from peerlist.io HTML tables"""
        all_layoffs = []
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                
                # Context options with proxy support
                context_options = {
                    'viewport': {'width': 1920, 'height': 1080},
                    'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
                if self.proxy_config:
                    context_options['proxy'] = self.proxy_config
                    logger.info(f"Using proxy: {self.proxy_config.get('server')}")
                
                context = browser.new_context(**context_options)
                page = context.new_page()
                
                for year in self.years:
                    url = self.BASE_URL.format(year=year)
                    logger.info(f"Loading {url}")
                    
                    try:
                        page.goto(url, wait_until="networkidle", timeout=60000)
                        page.wait_for_timeout(5000)  # Wait longer for tables to render
                        
                        # Scroll down to ensure all content loads
                        page.keyboard.press('End')
                        page.wait_for_timeout(2000)
                        page.keyboard.press('Home')
                        page.wait_for_timeout(1000)
                        
                        # Extract table data
                        layoffs = self._extract_table_data(page, year)
                        all_layoffs.extend(layoffs)
                        logger.info(f"Found {len(layoffs)} layoffs from {year}")
                        
                    except Exception as e:
                        logger.warning(f"Error loading {url}: {e}")
                        continue
                
                browser.close()
                logger.info(f"Found {len(all_layoffs)} total layoffs from {self.source_name}")
                
        except Exception as e:
            logger.error(f"Error scraping {self.source_name}: {e}")
            raise ScrapeError(f"Failed to scrape {self.source_name}: {e}")
        
        return all_layoffs
    
    def _extract_table_data(self, page, year: int) -> List[LayoffCreate]:
        """Extract data from HTML tables on peerlist.io"""
        layoffs = []
        
        try:
            # Extract all table rows
            table_data = page.evaluate('''
                () => {
                    const results = [];
                    const tables = document.querySelectorAll('table');
                    
                    tables.forEach(table => {
                        const rows = table.querySelectorAll('tr');
                        
                        rows.forEach((row, idx) => {
                            // Skip header row
                            if (idx === 0) return;
                            
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 4) {
                                const company = cells[0]?.textContent?.trim();
                                const employees = cells[1]?.textContent?.trim();
                                const dateStr = cells[2]?.textContent?.trim();
                                const industry = cells[3]?.textContent?.trim();
                                const location = cells[4]?.textContent?.trim();
                                const sourceUrl = cells[5]?.textContent?.trim();
                                
                                if (company && company.length > 1) {
                                    results.push({
                                        company: company,
                                        employees: employees,
                                        date: dateStr,
                                        industry: industry,
                                        location: location,
                                        source_url: sourceUrl
                                    });
                                }
                            }
                        });
                    });
                    
                    return results;
                }
            ''')
            
            seen = set()
            
            for row in table_data:
                company = row.get('company')
                if not company or company in seen:
                    continue
                    
                seen.add(company)
                
                # Parse employees - handle formats like "700 (15%)" or just "700"
                employees_str = row.get('employees', '')
                employees = None
                if employees_str:
                    match = re.search(r'(\d+)', employees_str.replace(',', ''))
                    if match:
                        employees = int(match.group(1))
                
                # Parse date - format is "28 Dec, 2025"
                layoff_date = self._parse_peerlist_date(row.get('date'), year)
                
                # Parse location for country
                location = row.get('location', '')
                country = "US"
                if location:
                    if ', US' in location or 'United States' in location:
                        country = "US"
                    elif ', IN' in location or 'India' in location:
                        country = "India"
                    elif ', IL' in location:
                        country = "Israel"
                    elif ', CA' in location and 'Canada' not in location:
                        country = "US"  # California
                    elif ', UK' in location or ', GB' in location:
                        country = "UK"
                    elif ', DE' in location:
                        country = "Germany"
                    elif ', JP' in location:
                        country = "Japan"
                    elif ', AU' in location:
                        country = "Australia"
                    elif ', SG' in location:
                        country = "Singapore"
                    elif ', CN' in location:
                        country = "China"
                
                layoff = LayoffCreate(
                    company_name=company,
                    industry=row.get('industry'),
                    layoff_date=layoff_date or date.today(),
                    employees_affected=employees,
                    source=self.source_name,
                    source_url=f"https://{row.get('source_url', '')}" if row.get('source_url') else self.base_url,
                    country=country,
                    description=f"Location: {location}" if location else None
                )
                layoffs.append(layoff)
                
        except Exception as e:
            logger.error(f"Error extracting table data: {e}")
        
        return layoffs
    
    def _parse_peerlist_date(self, date_str: Optional[str], year: int) -> Optional[date]:
        """Parse peerlist date format: '28 Dec, 2025' or '28 Dec'"""
        if not date_str:
            return None
        
        try:
            # Try full format with year
            if ',' in date_str:
                dt = datetime.strptime(date_str, "%d %b, %Y")
                return dt.date()
            else:
                # Just day and month, use provided year
                dt = datetime.strptime(f"{date_str}, {year}", "%d %b, %Y")
                return dt.date()
        except ValueError:
            pass
        
        # Fall back to base parser
        return self._parse_date(date_str)


class OfficePulseScraper(BaseScraper):
    """
    Scraper for officepulse.live - Indian Layoff Tracker
    
    Source: https://officepulse.live/
    Tracks layoffs with focus on India and global companies
    Uses WordPress Ninja Tables API for direct data access
    """
    
    BASE_URL = "https://officepulse.live/"
    API_URL = "https://officepulse.live/wp-admin/admin-ajax.php"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_name = "officepulse.live"
    
    @property
    def base_url(self) -> str:
        return self.BASE_URL
    
    def fetch_layoffs(self) -> List[LayoffCreate]:
        """Fetch layoffs from officepulse.live via Ninja Tables API"""
        layoffs = []
        
        try:
            logger.info(f"Fetching layoffs from {self.source_name} via API...")
            
            # API parameters
            params = {
                'action': 'wp_ajax_ninja_tables_public_action',
                'table_id': '15',
                'target_action': 'get-all-data',
                'default_sorting': 'old_first',
                'skip_rows': '0',
                'limit_rows': '0',
                'ninja_table_public_nonce': 'b2c5640fad'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': '*/*',
                'Referer': self.BASE_URL,
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            import requests
            response = requests.get(self.API_URL, params=params, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"API returned status {response.status_code}")
                raise ScrapeError(f"OfficePulse API returned {response.status_code}")
            
            data = response.json()
            logger.info(f"Retrieved {len(data)} records from API")
            
            # Process each record
            seen = set()
            for record in data:
                try:
                    value = record.get('value', {})
                    
                    company = value.get('company', '').strip()
                    if not company or company in seen:
                        continue
                    
                    seen.add(company)
                    
                    # Parse employees
                    employees = None
                    employees_str = value.get('laidoff', '')
                    if employees_str and employees_str not in ['Silent Firing', 'Silent firing', '']:
                        match = re.search(r'(\d+)', str(employees_str).replace(',', ''))
                        if match:
                            employees = int(match.group(1))
                    
                    # Parse timeline - format is "April-24" or "Nov-25"
                    layoff_date = self._parse_timeline(value.get('layofftimeline'))
                    
                    # Get country
                    country = value.get('laidoffcountry', 'India')
                    if country == 'Global':
                        country = value.get('headquarter', 'US')
                    
                    # Extract source URL from HTML
                    source_url = self.base_url
                    source_html = value.get('source', '')
                    if source_html:
                        url_match = re.search(r'href="([^"]+)"', source_html)
                        if url_match:
                            source_url = url_match.group(1)
                    
                    # Build description
                    status = value.get('status', '')
                    percentage = value.get('laidoff_1', '')
                    desc_parts = []
                    if status:
                        desc_parts.append(f"Status: {status}")
                    if percentage:
                        desc_parts.append(f"Percentage: {percentage}")
                    
                    layoff = LayoffCreate(
                        company_name=company[:200],
                        industry=value.get('industry'),
                        layoff_date=layoff_date or date.today(),
                        employees_affected=employees,
                        source=self.source_name,
                        source_url=source_url,
                        country=country,
                        description="; ".join(desc_parts) if desc_parts else None
                    )
                    layoffs.append(layoff)
                    
                except Exception as row_error:
                    logger.debug(f"Error processing record: {row_error}")
                    continue
            
            logger.info(f"Found {len(layoffs)} layoffs from {self.source_name}")
            
        except Exception as e:
            logger.error(f"Error scraping {self.source_name}: {e}")
            raise ScrapeError(f"Failed to scrape {self.source_name}: {e}")
        
        return layoffs
    
    def _parse_timeline(self, timeline_str: Optional[str]) -> Optional[date]:
        """Parse officepulse timeline format: 'April-24', 'Nov-25', 'December-24'"""
        if not timeline_str:
            return None
        
        try:
            # Format is "Month-YY" like "April-24" or "Nov-25"
            parts = timeline_str.split('-')
            if len(parts) == 2:
                month_str = parts[0].strip()
                year_str = parts[1].strip()
                
                # Convert to full year
                year = int(year_str)
                if year < 100:
                    year = 2000 + year
                
                # Parse month (handle both short and long names)
                month_map = {
                    'jan': 1, 'january': 1,
                    'feb': 2, 'february': 2,
                    'mar': 3, 'march': 3,
                    'apr': 4, 'april': 4,
                    'may': 5,
                    'jun': 6, 'june': 6,
                    'jul': 7, 'july': 7,
                    'aug': 8, 'august': 8,
                    'sep': 9, 'sept': 9, 'september': 9,
                    'oct': 10, 'october': 10,
                    'nov': 11, 'november': 11,
                    'dec': 12, 'december': 12
                }
                month = month_map.get(month_str.lower(), 1)
                
                return date(year, month, 1)
        except (ValueError, KeyError):
            pass
        
        return None
