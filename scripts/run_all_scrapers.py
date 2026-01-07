#!/usr/bin/env python3
"""
Utility script to run all scrapers once
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging
from src.storage.database import DatabaseManager
from src.scheduler import LayoffScheduler


def main():
    """Run all scrapers once"""
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("Running all scrapers...")
    logger.info("=" * 60)

    db_manager = DatabaseManager()
    db_manager.create_tables()

    scheduler = LayoffScheduler(db_manager)
    results = scheduler.run_once()

    # Exit with error code if any scraper failed
    failed = any(not r.get("success", False) for r in results.values())
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
