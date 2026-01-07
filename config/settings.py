"""
Configuration management for the layoff tracker
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


class Settings:
    """Application settings loaded from environment variables"""

    # Paths
    BASE_DIR = BASE_DIR
    DATA_DIR = DATA_DIR
    LOGS_DIR = LOGS_DIR

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{DATA_DIR}/layoffs.db"
    )

    # Scraper Configuration
    SCRAPING_ENABLED: bool = os.getenv("SCRAPING_ENABLED", "true").lower() == "true"
    LAYOFFS_FYI_ENABLED: bool = os.getenv("LAYOFFS_FYI_ENABLED", "true").lower() == "true"
    LAYOFFSTRACKER_ENABLED: bool = os.getenv("LAYOFFSTRACKER_ENABLED", "true").lower() == "true"
    LAYOFFSTRACKER_NONTECH_ENABLED: bool = os.getenv("LAYOFFSTRACKER_NONTECH_ENABLED", "true").lower() == "true"
    PEERLIST_ENABLED: bool = os.getenv("PEERLIST_ENABLED", "true").lower() == "true"
    OFFICEPULSE_ENABLED: bool = os.getenv("OFFICEPULSE_ENABLED", "true").lower() == "true"

    # Scheduler
    SCHEDULER_ENABLED: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"

    # Rate Limiting
    REQUEST_DELAY_SECONDS: float = float(os.getenv("REQUEST_DELAY_SECONDS", "2"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

    # Dashboard
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8501"))
    DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "localhost")

    # API
    API_PORT: int = int(os.getenv("API_PORT", "5001"))
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = str(LOGS_DIR / os.getenv("LOG_FILE", "layoff_tracker.log"))

    # Scraping frequencies (in hours)
    LAYOFFS_FYI_FREQUENCY_HOURS: int = 6

    # Source URLs
    LAYOFFS_FYI_URL: str = "https://layoffs.fyi/"
    LAYOFFSTRACKER_URL: str = "https://layoffstracker.com/"
    LAYOFFSTRACKER_NONTECH_URL: str = "https://layoffstracker.com/non-tech-layoffs/"
    PEERLIST_URL: str = "https://peerlist.io/layoffs-tracker/"
    OFFICEPULSE_URL: str = "https://officepulse.live/"

    # User Agent
    USER_AGENT: str = "LayoffTracker/1.0"

    # Proxy Configuration
    HTTP_PROXY: Optional[str] = os.getenv("HTTP_PROXY")
    HTTPS_PROXY: Optional[str] = os.getenv("HTTPS_PROXY")
    PROXY_USERNAME: Optional[str] = os.getenv("PROXY_USERNAME")
    PROXY_PASSWORD: Optional[str] = os.getenv("PROXY_PASSWORD")
    USE_PROXY: bool = os.getenv("USE_PROXY", "false").lower() == "true"

    @classmethod
    def get_db_path(cls) -> Path:
        """Get the database file path"""
        if cls.DATABASE_URL.startswith("sqlite:///"):
            return Path(cls.DATABASE_URL.replace("sqlite:///", ""))
        return DATA_DIR / "layoffs.db"


settings = Settings()

# Clear proxy environment variables if USE_PROXY is False
# This prevents requests library from auto-detecting them
if not settings.USE_PROXY:
    for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if var in os.environ:
            del os.environ[var]
