"""
Data export functionality for layoff data
"""
import logging
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.models.layoff import Layoff

logger = logging.getLogger(__name__)


class DataExporter:
    """Export layoff data to various formats"""

    def __init__(self, data_dir: Path = None):
        """
        Initialize data exporter

        Args:
            data_dir: Directory to save exported files. Defaults to data/exports
        """
        if data_dir is None:
            from config.settings import settings
            data_dir = settings.DATA_DIR / "exports"

        self.export_dir = Path(data_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Data exporter initialized with export directory: {self.export_dir}")

    def to_csv(
        self,
        layoffs: List[Layoff],
        filename: str = None,
        date_range: tuple = None
    ) -> str:
        """
        Export layoff data to CSV

        Args:
            layoffs: List of layoff records
            filename: Output filename. If None, generates timestamp-based name
            date_range: Optional tuple of (start_date, end_date) to filter

        Returns:
            Path to exported file
        """
        try:
            # Filter by date range if provided
            if date_range:
                start_date, end_date = date_range
                layoffs = [
                    l for l in layoffs
                    if start_date <= l.layoff_date <= end_date
                ]

            # Convert to DataFrame
            df = pd.DataFrame([layoff.to_dict() for layoff in layoffs])

            # Generate filename if not provided
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"layoffs_{timestamp}.csv"

            filepath = self.export_dir / filename

            # Save to CSV
            df.to_csv(filepath, index=False)
            logger.info(f"Exported {len(layoffs)} records to CSV: {filepath}")

            return str(filepath)

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            raise

    def to_json(
        self,
        layoffs: List[Layoff],
        filename: str = None,
        date_range: tuple = None,
        indent: int = 2
    ) -> str:
        """
        Export layoff data to JSON

        Args:
            layoffs: List of layoff records
            filename: Output filename
            date_range: Optional date range filter
            indent: JSON indentation

        Returns:
            Path to exported file
        """
        try:
            # Filter by date range if provided
            if date_range:
                start_date, end_date = date_range
                layoffs = [
                    l for l in layoffs
                    if start_date <= l.layoff_date <= end_date
                ]

            # Convert to list of dicts
            data = [layoff.to_dict() for layoff in layoffs]

            # Generate filename if not provided
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"layoffs_{timestamp}.json"

            filepath = self.export_dir / filename

            # Save to JSON
            import json
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=indent, default=str)

            logger.info(f"Exported {len(layoffs)} records to JSON: {filepath}")

            return str(filepath)

        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            raise

    def to_excel(
        self,
        layoffs: List[Layoff],
        filename: str = None,
        date_range: tuple = None,
        include_summary: bool = True
    ) -> str:
        """
        Export layoff data to Excel with multiple sheets

        Args:
            layoffs: List of layoff records
            filename: Output filename
            date_range: Optional date range filter
            include_summary: Whether to include summary sheet

        Returns:
            Path to exported file
        """
        try:
            # Filter by date range if provided
            if date_range:
                start_date, end_date = date_range
                layoffs = [
                    l for l in layoffs
                    if start_date <= l.layoff_date <= end_date
                ]

            # Generate filename if not provided
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"layoffs_{timestamp}.xlsx"

            filepath = self.export_dir / filename

            # Create Excel writer
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Main data sheet
                df = pd.DataFrame([layoff.to_dict() for layoff in layoffs])
                df.to_excel(writer, sheet_name='All Layoffs', index=False)

                # Summary sheet
                if include_summary and layoffs:
                    summary_data = self._generate_summary(layoffs)
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)

                    # Top companies sheet
                    top_companies = self._get_top_companies(layoffs, n=20)
                    top_companies_df = pd.DataFrame(top_companies)
                    top_companies_df.to_excel(writer, sheet_name='Top Companies', index=False)

                    # Industry breakdown sheet
                    industry_breakdown = self._get_industry_breakdown(layoffs)
                    industry_df = pd.DataFrame(industry_breakdown)
                    industry_df.to_excel(writer, sheet_name='By Industry', index=False)

            logger.info(f"Exported {len(layoffs)} records to Excel: {filepath}")

            return str(filepath)

        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")
            raise

    def _generate_summary(self, layoffs: List[Layoff]) -> dict:
        """Generate summary statistics"""
        total_companies = len(set(l.company_name for l in layoffs))
        total_records = len(layoffs)
        total_affected = sum(l.employees_affected for l in layoffs if l.employees_affected)

        # Get date range
        dates = [l.layoff_date for l in layoffs if l.layoff_date]
        date_range = {
            "earliest": min(dates) if dates else None,
            "latest": max(dates) if dates else None
        }

        return {
            "Metric": [
                "Total Companies",
                "Total Records",
                "Total Employees Affected",
                "Date Range (Earliest)",
                "Date Range (Latest)"
            ],
            "Value": [
                total_companies,
                total_records,
                total_affected,
                date_range["earliest"],
                date_range["latest"]
            ]
        }

    def _get_top_companies(self, layoffs: List[Layoff], n: int = 20) -> dict:
        """Get top companies by layoffs"""
        from collections import defaultdict

        company_totals = defaultdict(int)
        for layoff in layoffs:
            if layoff.employees_affected:
                company_totals[layoff.company_name] += layoff.employees_affected

        # Sort by total affected
        sorted_companies = sorted(
            company_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )[:n]

        return {
            "Company": [c[0] for c in sorted_companies],
            "Total Layoffs": [c[1] for c in sorted_companies]
        }

    def _get_industry_breakdown(self, layoffs: List[Layoff]) -> dict:
        """Get breakdown by industry"""
        from collections import defaultdict

        industry_totals = defaultdict(int)
        industry_counts = defaultdict(int)

        for layoff in layoffs:
            if layoff.industry:
                industry_totals[layoff.industry] += layoff.employees_affected or 0
                industry_counts[layoff.industry] += 1

        return {
            "Industry": list(industry_totals.keys()),
            "Total Layoffs": list(industry_totals.values()),
            "Number of Events": list(industry_counts.values())
        }
