"""
Base scraper class with common functionality for all scrapers
"""
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from ratelimit import limits, sleep_and_retry

from config.settings import settings
from src.models.layoff import LayoffCreate
from src.storage.database import DatabaseManager

# Setup logging
logger = logging.getLogger(__name__)


class ScrapeError(Exception):
    """Custom exception for scraping errors"""
    pass


class BaseScraper(ABC):
    """
    Abstract base class for all scrapers

    Provides common functionality:
    - HTTP requests with retry logic
    - Rate limiting
    - Error handling
    - Data validation
    - Database integration
    """

    def __init__(self, db_manager: DatabaseManager = None):
        """
        Initialize the base scraper

        Args:
            db_manager: Database manager instance. If None, creates a new one.
        """
        self.db_manager = db_manager or DatabaseManager()
        self.source_name = self.__class__.__name__
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': settings.USER_AGENT
        })

        # Configure proxy if enabled
        self.proxy_config = None
        if settings.USE_PROXY and settings.HTTP_PROXY:
            # Parse proxy host and port
            proxy_host = settings.HTTP_PROXY.replace('http://', '').replace('https://', '')
            proxy_port = settings.HTTPS_PROXY if settings.HTTPS_PROXY and settings.HTTPS_PROXY.isdigit() else '80'
            
            # Build proxy URL
            if settings.PROXY_USERNAME and settings.PROXY_PASSWORD:
                proxy_url = f"http://{settings.PROXY_USERNAME}:{settings.PROXY_PASSWORD}@{proxy_host}:{proxy_port}"
                self.session.proxies = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                # Store Playwright-compatible proxy config
                self.proxy_config = {
                    'server': f"http://{proxy_host}:{proxy_port}",
                    'username': settings.PROXY_USERNAME,
                    'password': settings.PROXY_PASSWORD
                }
            else:
                proxy_url = f"http://{proxy_host}:{proxy_port}"
                self.session.proxies = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                self.proxy_config = {
                    'server': proxy_url
                }

            logger.info(f"Proxy configured: {proxy_host}:{proxy_port}")
        else:
            logger.info("No proxy configured - using direct connection")

        logger.info(f"Initialized {self.source_name} scraper")

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL for the scraper"""
        pass

    @abstractmethod
    def fetch_layoffs(self) -> List[LayoffCreate]:
        """
        Fetch layoff data from the source

        Returns:
            List of LayoffCreate objects

        Raises:
            ScrapeError: If scraping fails
        """
        pass

    @sleep_and_retry
    @limits(calls=1, period=settings.REQUEST_DELAY_SECONDS)
    def _fetch_page(self, url: str, params: dict = None) -> requests.Response:
        """
        Fetch a web page with rate limiting

        Args:
            url: URL to fetch
            params: Query parameters

        Returns:
            Response object

        Raises:
            ScrapeError: If request fails after retries
        """
        max_retries = settings.MAX_RETRIES
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                logger.debug(f"Fetching {url} (attempt {attempt + 1}/{max_retries})")
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response

            except requests.exceptions.HTTPError as e:
                logger.warning(f"HTTP error on {url}: {e}")
                if attempt == max_retries - 1:
                    raise ScrapeError(f"Failed to fetch {url} after {max_retries} attempts: {e}")

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error on {url}: {e}")
                if attempt == max_retries - 1:
                    raise ScrapeError(f"Failed to fetch {url} after {max_retries} attempts: {e}")

            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                if attempt == max_retries - 1:
                    raise ScrapeError(f"Failed to fetch {url} after {max_retries} attempts: {e}")

            # Wait before retry with exponential backoff
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))

    def _parse_html(self, response: requests.Response) -> BeautifulSoup:
        """
        Parse HTML response

        Args:
            response: Response object

        Returns:
            BeautifulSoup object
        """
        return BeautifulSoup(response.content, 'lxml')

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string to datetime object

        Args:
            date_str: Date string to parse

        Returns:
            datetime object or None if parsing fails
        """
        if not date_str:
            return None

        # Try common date formats
        date_formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except (ValueError, AttributeError):
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove extra whitespace
        text = " ".join(text.split())

        # Remove common unwanted characters
        text = text.strip()

        return text

    def _parse_employees_affected(self, count_str: str) -> Optional[int]:
        """
        Parse employee count string to integer

        Args:
            count_str: String containing employee count

        Returns:
            Integer count or None if parsing fails
        """
        if not count_str:
            return None

        try:
            # Remove common separators and convert
            cleaned = count_str.replace(",", "").replace(" ", "").replace("+", "")
            # Extract digits
            digits = "".join(filter(str.isdigit, cleaned))

            if digits:
                return int(digits)

        except (ValueError, AttributeError) as e:
            logger.warning(f"Could not parse employee count '{count_str}': {e}")

        return None

    def scrape_and_store(self) -> dict:
        """
        Main method to scrape and store layoff data

        Returns:
            Dictionary with scrape results:
            {
                "success": bool,
                "records_found": int,
                "records_added": int,
                "errors": List[str],
                "duration_seconds": float
            }
        """
        start_time = datetime.now()
        result = {
            "success": False,
            "records_found": 0,
            "records_added": 0,
            "errors": [],
            "duration_seconds": 0
        }

        try:
            logger.info(f"Starting scrape for {self.source_name}")

            # Fetch layoff data
            layoffs = self.fetch_layoffs()
            result["records_found"] = len(layoffs)

            if not layoffs:
                logger.warning(f"No layoffs found for {self.source_name}")
                result["success"] = True
                return result

            # Store in database
            added_count = 0
            for layoff in layoffs:
                try:
                    created = self.db_manager.add_layoff(layoff)
                    if created:
                        added_count += 1
                except Exception as e:
                    error_msg = f"Error storing layoff for {layoff.company_name}: {e}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)

            result["records_added"] = added_count
            result["success"] = True

            logger.info(f"Scrape completed for {self.source_name}: "
                       f"{added_count}/{len(layoffs)} records added")

        except ScrapeError as e:
            error_msg = f"Scraping error for {self.source_name}: {e}"
            logger.error(error_msg)
            result["errors"].append(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error for {self.source_name}: {e}"
            logger.error(error_msg)
            result["errors"].append(error_msg)

        finally:
            result["duration_seconds"] = (datetime.now() - start_time).total_seconds()

        return result

    def get_recent_scrapes(self, days: int = 7) -> List[LayoffCreate]:
        """
        Get recent layoff records scraped by this source

        Args:
            days: Number of days to look back

        Returns:
            List of recent layoff records
        """
        from datetime import date, timedelta

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        layoffs = self.db_manager.get_layoffs_by_date_range(start_date, end_date)

        # Filter by this source
        source_layoffs = [l for l in layoffs if l.source == self.source_name]

        return source_layoffs

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(base_url='{self.base_url}')"
