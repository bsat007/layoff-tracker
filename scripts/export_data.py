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
    """Export all data"""
    logger = setup_logging()

    logger.info("Exporting ALL layoff data...")

    db_manager = DatabaseManager()
    
    # Get ALL records from the database
    layoffs = db_manager.get_all_layoffs()

    logger.info(f"Found {len(layoffs)} total records")

    exporter = DataExporter()

    # Export to all formats
    csv_path = exporter.to_csv(layoffs, filename='layoffs_all.csv')
    logger.info(f"✓ CSV: {csv_path}")

    json_path = exporter.to_json(layoffs, filename='layoffs_all.json')
    logger.info(f"✓ JSON: {json_path}")

    excel_path = exporter.to_excel(layoffs, filename='layoffs_all.xlsx')
    logger.info(f"✓ Excel: {excel_path}")

    logger.info("Export complete!")


if __name__ == "__main__":
    main()
