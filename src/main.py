"""
Main entry point for the Layoff Tracker
"""
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.utils.logging_config import setup_logging
from src.storage.database import DatabaseManager
from src.scheduler import LayoffScheduler


def init_db():
    """Initialize database and create tables"""
    logger = setup_logging()
    logger.info("Initializing database...")

    db_manager = DatabaseManager()
    db_manager.create_tables()

    logger.info("Database initialized successfully!")


def scrape():
    """Run all scrapers once"""
    logger = setup_logging()

    db_manager = DatabaseManager()
    db_manager.create_tables()

    scheduler = LayoffScheduler(db_manager)
    scheduler.run_once()


def run_scheduler():
    """Run the continuous scheduler"""
    logger = setup_logging()

    db_manager = DatabaseManager()
    db_manager.create_tables()

    scheduler = LayoffScheduler(db_manager)
    scheduler.schedule_jobs()
    scheduler.start()


def run_dashboard(port: int = None):
    """Run the Streamlit dashboard"""
    import subprocess
    import webbrowser

    # Use provided port or fall back to settings
    dashboard_port = port or settings.DASHBOARD_PORT
    dashboard_host = settings.DASHBOARD_HOST

    # Open browser after a short delay
    import threading
    import time

    def open_browser():
        time.sleep(2)
        webbrowser.open(f"http://{dashboard_host}:{dashboard_port}")

    threading.Thread(target=open_browser, daemon=True).start()

    # Run streamlit
    dashboard_path = Path(__file__).parent / "dashboard" / "app.py"
    subprocess.run([
        "streamlit", "run", str(dashboard_path),
        "--server.port", str(dashboard_port),
        "--server.address", dashboard_host
    ])


def export_data(format: str = "csv", days: int = 30):
    """Export data to specified format"""
    logger = setup_logging()

    from datetime import date, timedelta
    from src.storage.export import DataExporter

    db_manager = DatabaseManager()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    logger.info(f"Exporting data from {start_date} to {end_date}...")

    layoffs = db_manager.get_layoffs_by_date_range(start_date, end_date)
    exporter = DataExporter()

    if format == "csv":
        filepath = exporter.to_csv(layoffs)
    elif format == "json":
        filepath = exporter.to_json(layoffs)
    elif format == "excel":
        filepath = exporter.to_excel(layoffs)
    else:
        logger.error(f"Unknown format: {format}")
        sys.exit(1)

    logger.info(f"Data exported to: {filepath}")


def run_api(port: int = 5000, host: str = "0.0.0.0"):
    """Run the Flask REST API server"""
    logger = setup_logging()
    logger.info(f"Starting Flask API on {host}:{port}...")

    from src.api.app import app
    app.run(host=host, port=port, debug=False)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Layoff Tracker - Collect and visualize layoff data")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Init command
    subparsers.add_parser("init", help="Initialize database")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Run all scrapers once")
    scrape_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # Schedule command
    subparsers.add_parser("schedule", help="Run continuous scheduler")

    # Dashboard command
    dashboard_parser = subparsers.add_parser("dashboard", help="Launch Streamlit dashboard")
    dashboard_parser.add_argument("--port", "-p", type=int, default=None, help="Port to run on")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export data")
    export_parser.add_argument("--format", "-f", choices=["csv", "json", "excel"], default="csv", help="Export format")
    export_parser.add_argument("--days", "-d", type=int, default=30, help="Number of days to export")

    # API command
    api_parser = subparsers.add_parser("api", help="Run Flask REST API server")
    api_parser.add_argument("--port", "-p", type=int, default=5000, help="Port to run on")
    api_parser.add_argument("--host", "-H", type=str, default="0.0.0.0", help="Host to bind to")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "init":
        init_db()
    elif args.command == "scrape":
        scrape()
    elif args.command == "schedule":
        run_scheduler()
    elif args.command == "dashboard":
        run_dashboard(args.port)
    elif args.command == "export":
        export_data(args.format, args.days)
    elif args.command == "api":
        run_api(args.port, args.host)


if __name__ == "__main__":
    main()
