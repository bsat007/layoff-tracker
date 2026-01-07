#!/usr/bin/env python3
"""
Test the TechCrunch RSS scraper
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging
from src.storage.database import DatabaseManager
from src.scrapers.techcrunch_rss import TechCrunchRSSScraper

logger = setup_logging()


def main():
    logger.info("=" * 60)
    logger.info("Testing TechCrunch RSS Scraper")
    logger.info("=" * 60)

    db_manager = DatabaseManager()
    db_manager.create_tables()

    scraper = TechCrunchRSSScraper(db_manager)

    logger.info("Running scraper...")
    result = scraper.scrape_and_store()

    logger.info("\n" + "=" * 60)
    logger.info("SCRAPER RESULTS")
    logger.info("=" * 60)
    logger.info(f"Success: {result['success']}")
    logger.info(f"Records Found: {result['records_found']}")
    logger.info(f"Records Added: {result['records_added']}")
    logger.info(f"Duration: {result['duration_seconds']:.2f}s")

    if result.get('errors'):
        logger.error("\nErrors:")
        for error in result['errors']:
            logger.error(f"  - {error}")

    # Get updated statistics
    stats = db_manager.get_statistics()
    logger.info("\n" + "=" * 60)
    logger.info("DATABASE STATISTICS")
    logger.info("=" * 60)
    logger.info(f"Total Companies: {stats['total_companies']}")
    logger.info(f"Total Records: {stats['total_records']}")
    logger.info(f"Total Affected: {stats['total_affected']}")
    logger.info(f"Date Range: {stats['date_range']['earliest']} to {stats['date_range']['latest']}")

    logger.info("\n✅ Test complete!")
    return result['success']


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
