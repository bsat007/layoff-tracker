#!/usr/bin/env python3
"""
Utility script to export layoff data
"""
import sys
from pathlib import Path
from datetime import date, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging
from src.storage.database import DatabaseManager
from src.storage.export import DataExporter


def main():
    """Export data"""
    logger = setup_logging()

    # Default: last 30 days
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    logger.info(f"Exporting data from {start_date} to {end_date}")

    db_manager = DatabaseManager()
    layoffs = db_manager.get_layoffs_by_date_range(start_date, end_date)

    logger.info(f"Found {len(layoffs)} records")

    exporter = DataExporter()

    # Export to all formats
    csv_path = exporter.to_csv(layoffs)
    logger.info(f"✓ CSV: {csv_path}")

    json_path = exporter.to_json(layoffs)
    logger.info(f"✓ JSON: {json_path}")

    excel_path = exporter.to_excel(layoffs)
    logger.info(f"✓ Excel: {excel_path}")

    logger.info("Export complete!")


if __name__ == "__main__":
    main()
