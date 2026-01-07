"""
Scheduler for automated layoff data collection
"""
import logging
from typing import Dict, List
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import settings
from src.storage.database import DatabaseManager
from src.scrapers.layoffs_fyi import LayoffsFyiScraper
from src.scrapers.comprehensive_scraper import ComprehensiveLayoffScraper
from src.scrapers.additional_sources import LayoffsTrackerScraper, PeerlistScraper, OfficePulseScraper

logger = logging.getLogger(__name__)


class LayoffScheduler:
    """
    Scheduler for automated scraping of multiple sources

    Runs scrapers at different intervals:
    - Every 6 hours: Layoffs.fyi, TrueUp
    - Daily: WARNTracker, LayoffData
    """

    def __init__(self, db_manager: DatabaseManager = None):
        """
        Initialize scheduler

        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager or DatabaseManager()
        self.scheduler = BlockingScheduler()
        self.scrapers = self._initialize_scrapers()
        logger.info("Scheduler initialized")

    def _initialize_scrapers(self) -> Dict[str, object]:
        """
        Initialize all enabled scrapers

        Returns:
            Dictionary of scraper name -> scraper instance
        """
        scrapers = {}

        # Use comprehensive scraper with 200+ real 2024-2025 layoff events
        scrapers['comprehensive'] = ComprehensiveLayoffScraper(self.db_manager)

        # Tier 1: Primary sources - layoffs.fyi with Airtable embed
        if settings.LAYOFFS_FYI_ENABLED:
            scrapers['layoffs_fyi'] = LayoffsFyiScraper(self.db_manager)
            logger.info("Layoffs.fyi scraper enabled - using Airtable embed extraction")

        # layoffstracker.com - also uses Airtable embed
        if settings.LAYOFFSTRACKER_ENABLED:
            scrapers['layoffstracker'] = LayoffsTrackerScraper(self.db_manager)
            logger.info("LayoffsTracker.com scraper enabled - using Airtable embed extraction")

        # peerlist.io - uses HTML tables
        if settings.PEERLIST_ENABLED:
            scrapers['peerlist'] = PeerlistScraper(self.db_manager)
            logger.info("Peerlist.io scraper enabled - using HTML table extraction")

        # officepulse.live - India focused layoff tracker (uses API)
        if settings.OFFICEPULSE_ENABLED:
            scrapers['officepulse'] = OfficePulseScraper(self.db_manager)
            logger.info("OfficePulse.live scraper enabled - using Ninja Tables API")

        logger.info(f"Initialized {len(scrapers)} scrapers: {list(scrapers.keys())}")
        return scrapers

    def run_scraper(self, scraper_name: str) -> Dict:
        """
        Run a single scraper

        Args:
            scraper_name: Name of the scraper to run

        Returns:
            Results dictionary
        """
        if scraper_name not in self.scrapers:
            logger.error(f"Scraper '{scraper_name}' not found")
            return {"success": False, "error": f"Scraper '{scraper_name}' not found"}

        logger.info(f"Running scraper: {scraper_name}")
        scraper = self.scrapers[scraper_name]

        try:
            result = scraper.scrape_and_store()
            return result
        except Exception as e:
            logger.error(f"Error running {scraper_name}: {e}")
            return {"success": False, "error": str(e)}

    def run_all_scrapers(self) -> Dict[str, Dict]:
        """
        Run all enabled scrapers sequentially

        Returns:
            Dictionary of scraper results
        """
        results = {}

        for scraper_name in self.scrapers:
            logger.info(f"Running {scraper_name}...")
            results[scraper_name] = self.run_scraper(scraper_name)

        return results

    def schedule_jobs(self):
        """Schedule all scraping jobs"""
        # Every 6 hours for primary sources
        if settings.LAYOFFS_FYI_ENABLED:
            self.scheduler.add_job(
                self.run_scraper,
                trigger=IntervalTrigger(hours=settings.LAYOFFS_FYI_FREQUENCY_HOURS),
                args=['layoffs_fyi'],
                id='layoffs_fyi_scheduled',
                name='Layoffs.fyi Scraper',
                replace_existing=True
            )
            logger.info(f"Scheduled layoffs.fyi scraper every {settings.LAYOFFS_FYI_FREQUENCY_HOURS} hours")

        if settings.LAYOFFSTRACKER_ENABLED:
            self.scheduler.add_job(
                self.run_scraper,
                trigger=IntervalTrigger(hours=6),
                args=['layoffstracker'],
                id='layoffstracker_scheduled',
                name='LayoffsTracker Scraper',
                replace_existing=True
            )
            logger.info("Scheduled layoffstracker.com scraper every 6 hours")

        if settings.PEERLIST_ENABLED:
            self.scheduler.add_job(
                self.run_scraper,
                trigger=IntervalTrigger(hours=12),
                args=['peerlist'],
                id='peerlist_scheduled',
                name='Peerlist Scraper',
                replace_existing=True
            )
            logger.info("Scheduled peerlist.io scraper every 12 hours")

        if settings.OFFICEPULSE_ENABLED:
            self.scheduler.add_job(
                self.run_scraper,
                trigger=IntervalTrigger(hours=12),
                args=['officepulse'],
                id='officepulse_scheduled',
                name='OfficePulse Scraper',
                replace_existing=True
            )
            logger.info("Scheduled officepulse.live scraper every 12 hours")

        # Print scheduled jobs
        jobs = self.scheduler.get_jobs()
        logger.info(f"Total scheduled jobs: {len(jobs)}")
        for job in jobs:
            logger.info(f"  - {job.name} (next run: {job.next_run_time})")

    def start(self):
        """Start the scheduler (blocking)"""
        logger.info("Starting scheduler...")
        logger.info("Press Ctrl+C to stop")

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")
            self.scheduler.shutdown()

    def stop(self):
        """Stop the scheduler"""
        logger.info("Stopping scheduler...")
        self.scheduler.shutdown(wait=True)

    def run_once(self):
        """Run all scrapers once without scheduling"""
        logger.info("Running all scrapers once...")
        results = self.run_all_scrapers()

        # Print summary
        logger.info("\n" + "="*50)
        logger.info("SCRAPER RUN SUMMARY")
        logger.info("="*50)

        for scraper_name, result in results.items():
            status = "✓ SUCCESS" if result.get("success") else "✗ FAILED"
            logger.info(f"{scraper_name}: {status}")
            if result.get("success"):
                logger.info(f"  Records found: {result.get('records_found', 0)}")
                logger.info(f"  Records added: {result.get('records_added', 0)}")
                logger.info(f"  Duration: {result.get('duration_seconds', 0):.2f}s")
            else:
                logger.error(f"  Error: {result.get('error', 'Unknown error')}")

        logger.info("="*50 + "\n")

        return results


def main():
    """Main entry point for scheduler"""
    from src.utils.logging_config import setup_logging

    # Setup logging
    setup_logging()

    # Create database tables
    db_manager = DatabaseManager()
    db_manager.create_tables()

    # Create and start scheduler
    scheduler = LayoffScheduler(db_manager)

    if settings.SCHEDULER_ENABLED:
        scheduler.schedule_jobs()
        scheduler.start()
    else:
        # Run once and exit
        scheduler.run_once()


if __name__ == "__main__":
    main()
