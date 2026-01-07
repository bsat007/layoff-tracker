# 📊 Layoff Tracker

A comprehensive Python-based layoff tracker that scrapes multiple websites to collect data about companies that have recently laid off employees. Features automated scraping, REST API, data export, and an interactive Streamlit dashboard.

## 🌟 Features

- **Multi-Source Scraping**: Collects data from 5+ live sources
  - **Layoffs.fyi**: Tech layoffs (4,200+ records via Airtable API)
  - **LayoffsTracker.com**: Tech layoffs (3,700+ records via Airtable API)
  - **LayoffsTracker.com (Non-Tech)**: Non-tech layoffs across various industries (via Airtable API)
  - **Peerlist.io**: Startup layoffs (HTML parsing)
  - **OfficePulse.live**: India-focused layoffs (API-based)

- **Data Export**: Export to CSV, JSON, or Excel with flexible options

- **REST API**: Flask-based API for programmatic access

- **Interactive Dashboard**: Streamlit-based dashboard with:
  - Layoff trends over time
  - Top companies analysis
  - Industry breakdown
  - Country filtering
  - Searchable data table

- **Automated Scheduling**: Runs scrapers at optimal intervals

## 📋 Prerequisites

- Python 3.11 or higher
- Conda (recommended) or pip

## 🚀 Quick Start

### 1. Set up environment

```bash
# Create conda environment
conda create -n layoff_tracker python=3.11
conda activate layoff_tracker

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Initialize and run

```bash
# Initialize database
python -m src.main init

# Run all scrapers
python -m src.main scrape

# Launch dashboard
python -m src.main dashboard
```

Dashboard: http://localhost:8501

## 📖 Commands

```bash
# Database operations
python -m src.main init              # Initialize database
python -m src.main scrape            # Run all scrapers once
python -m src.main schedule          # Run continuous scheduler

# Dashboard
python -m src.main dashboard         # Launch Streamlit dashboard
python -m src.main dashboard --port 8502  # Custom port

# Data export (last N days)
python -m src.main export --format csv --days 30
python -m src.main export --format json --days 7
python -m src.main export --format excel --days 365

# Export all data
python scripts/export_data.py
```

## 📤 Data Export Options

### CLI Export

```bash
# Export last 30 days (default) in different formats
python -m src.main export --format csv --days 30
python -m src.main export --format json --days 7
python -m src.main export --format excel --days 365
```

### Export All Data

```python
from src.storage.database import DatabaseManager
from src.storage.export import DataExporter

db = DatabaseManager()
exporter = DataExporter()

# Get all records
layoffs = db.get_all_layoffs()

# Export to all formats
exporter.to_csv(layoffs, filename='layoffs_all.csv')
exporter.to_json(layoffs, filename='layoffs_all.json')
exporter.to_excel(layoffs, filename='layoffs_all.xlsx')
```

### Export with Date Range

```python
from datetime import date, timedelta
from src.storage.database import DatabaseManager
from src.storage.export import DataExporter

db = DatabaseManager()
exporter = DataExporter()

# Get records from date range
start = date(2025, 1, 1)
end = date(2025, 12, 31)
layoffs = db.get_layoffs_by_date_range(start, end)

exporter.to_csv(layoffs, filename='layoffs_2025.csv')
```

### Export by Company

```python
from src.storage.database import DatabaseManager
from src.storage.export import DataExporter

db = DatabaseManager()
exporter = DataExporter()

# Search for specific company
layoffs = db.get_layoffs_by_company("Google")
exporter.to_csv(layoffs, filename='google_layoffs.csv')
```

### Export Formats

| Format | File | Features |
|--------|------|----------|
| **CSV** | `.csv` | Simple, works with Excel/Google Sheets |
| **JSON** | `.json` | Structured data for APIs/apps |
| **Excel** | `.xlsx` | Multiple sheets with summary, top companies, and industry breakdown |

### Excel Export Details

The Excel export includes 4 sheets:
1. **All Layoffs** - Complete dataset
2. **Summary** - Total companies, records, employees affected, date range
3. **Top Companies** - Top 20 companies by layoffs
4. **By Industry** - Breakdown by industry

### API Export

```bash
# Export via REST API
curl http://localhost:5000/api/export/csv > layoffs.csv
curl http://localhost:5000/api/export/json > layoffs.json
curl http://localhost:5000/api/export/excel > layoffs.xlsx
```

### Export Location

All exports are saved to: `data/exports/`

## 🔌 REST API

Start the Flask API server:

```bash
python -m src.api.app
```

API runs at http://localhost:5000

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/layoffs` | Get all layoffs (with filters) |
| GET | `/api/layoffs/<id>` | Get specific layoff by ID |
| GET | `/api/stats` | Get summary statistics |
| GET | `/api/sources` | List available data sources |
| GET | `/api/countries` | List all countries |
| GET | `/api/export/<format>` | Export data (csv/json/excel) |
| POST | `/api/scrape` | Trigger a scrape run |

### Query Parameters

```bash
# Filter by date range
GET /api/layoffs?start_date=2025-01-01&end_date=2025-12-31

# Filter by source
GET /api/layoffs?source=layoffs.fyi

# Filter by country
GET /api/layoffs?country=India

# Filter by company
GET /api/layoffs?company=Google

# Pagination
GET /api/layoffs?limit=100&offset=0

# Combined filters
GET /api/layoffs?source=layoffs.fyi&country=US&limit=50
```

### Example Response

```json
{
  "success": true,
  "count": 100,
  "total": 6639,
  "data": [
    {
      "id": 1,
      "company_name": "Sapiens",
      "industry": "Finance",
      "layoff_date": "2025-12-28",
      "employees_affected": 700,
      "source": "layoffs.fyi",
      "country": "Israel"
    }
  ]
}
```

## 🗄️ Database

SQLite database at `data/layoffs.db`

### Schema

```sql
LayoffModel:
  - id: Integer (Primary Key)
  - company_name: String
  - industry: String (nullable)
  - layoff_date: Date
  - employees_affected: Integer (nullable)
  - employees_remaining: Integer (nullable)
  - source: String
  - source_url: String
  - country: String (default: "US")
  - description: Text (nullable)
  - unique_id: String (unique hash)
  - scraped_at: DateTime
```

## ⚙️ Configuration

Edit `.env` file:

```bash
# Database
DATABASE_URL=sqlite:///data/layoffs.db

# Scraping
LAYOFFS_FYI_ENABLED=true
LAYOFFSTRACKER_ENABLED=true
LAYOFFSTRACKER_NONTECH_ENABLED=true
PEERLIST_ENABLED=true
OFFICEPULSE_ENABLED=true

# Dashboard
DASHBOARD_PORT=8501
DASHBOARD_HOST=localhost

# API
API_PORT=5000
API_HOST=0.0.0.0

# Proxy (optional)
USE_PROXY=false
HTTP_PROXY=http://proxy.example.com
HTTPS_PROXY=80
PROXY_USERNAME=username
PROXY_PASSWORD=password
```

## 📁 Project Structure

```
layoff-tracker/
├── src/
│   ├── api/               # Flask REST API
│   │   └── app.py
│   ├── scrapers/          # Web scrapers
│   │   ├── base.py
│   │   ├── layoffs_fyi.py
│   │   ├── additional_sources.py
│   │   └── comprehensive_scraper.py
│   ├── models/            # Data models
│   ├── storage/           # Database and export
│   ├── dashboard/         # Streamlit app
│   ├── utils/             # Utilities
│   ├── scheduler.py       # Job scheduler
│   └── main.py            # Entry point
├── config/                # Configuration
├── data/                  # Database files
├── logs/                  # Log files
├── lib/                   # Local packages
│   └── airtable-scraper/  # Fixed for Python 3.11
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🐳 Docker

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## 📊 Current Data

| Source | Records | Method |
|--------|---------|--------|
| layoffs.fyi | 2,891 | Airtable API |
| layoffs.fyi (Federal) | 94 | Airtable API |
| layoffstracker.com | 2,796 | Airtable API |
| layoffstracker.com (Non-Tech) | TBD | Airtable API |
| peerlist.io | 283 | Playwright |
| officepulse.live | 241 | Ninja Tables API |
| **Total** | **6,400+** | |

## 🔧 Adding a New Scraper

1. Create a new file in `src/scrapers/`
2. Inherit from `BaseScraper`
3. Implement the `fetch_layoffs()` method
4. Register in `src/scheduler.py`

Example:

```python
from src.scrapers.base import BaseScraper
from src.models.layoff import LayoffCreate

class MyScraper(BaseScraper):
    @property
    def base_url(self) -> str:
        return "https://example.com"

    def fetch_layoffs(self) -> List[LayoffCreate]:
        # Your scraping logic here
        pass
```

## 📝 License

MIT License

## 🙏 Data Sources

- [Layoffs.fyi](https://layoffs.fyi/) - Tech Layoff Tracker
- [LayoffsTracker.com](https://layoffstracker.com/) - Tech Layoffs
- [LayoffsTracker.com Non-Tech](https://layoffstracker.com/non-tech-layoffs/) - Non-Tech Layoffs
- [Peerlist.io](https://peerlist.io/layoffs-tracker/) - Startup Layoffs
- [OfficePulse.live](https://officepulse.live/) - India Layoffs

---

**Built with Python, Flask, Streamlit, and Playwright**
