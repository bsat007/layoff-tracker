"""
Flask REST API for Layoff Tracker

Provides endpoints for:
- Querying layoff data with filters
- Exporting data in various formats
- Getting statistics and metadata
- Triggering scraper runs
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, jsonify, request, send_file, Response
from flask_cors import CORS
from datetime import datetime, date, timedelta
import logging
import json
import io

from config.settings import settings
from src.storage.database import DatabaseManager
from src.storage.export import DataExporter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize database manager
db_manager = DatabaseManager()
exporter = DataExporter()


# ============================================================================
# Health Check
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


# ============================================================================
# Layoff Data Endpoints
# ============================================================================

@app.route('/api/layoffs', methods=['GET'])
def get_layoffs():
    """
    Get layoff records with optional filters
    
    Query Parameters:
        - start_date: Filter by start date (YYYY-MM-DD)
        - end_date: Filter by end date (YYYY-MM-DD)
        - source: Filter by data source
        - country: Filter by country
        - company: Filter by company name (partial match)
        - industry: Filter by industry
        - limit: Maximum number of records (default: 100)
        - offset: Offset for pagination (default: 0)
    
    Returns:
        JSON with layoff data
    """
    try:
        # Parse query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        source = request.args.get('source')
        country = request.args.get('country')
        company = request.args.get('company')
        industry = request.args.get('industry')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        # Parse dates
        start_date = None
        end_date = None
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Get layoffs from database
        if start_date and end_date:
            layoffs = db_manager.get_layoffs_by_date_range(start_date, end_date)
        else:
            layoffs = db_manager.get_all_layoffs()
        
        # Apply filters
        if source:
            layoffs = [l for l in layoffs if l.source and source.lower() in l.source.lower()]
        
        if country:
            layoffs = [l for l in layoffs if l.country and country.lower() in l.country.lower()]
        
        if company:
            layoffs = [l for l in layoffs if l.company_name and company.lower() in l.company_name.lower()]
        
        if industry:
            layoffs = [l for l in layoffs if l.industry and industry.lower() in l.industry.lower()]
        
        # Get total count before pagination
        total_count = len(layoffs)
        
        # Apply pagination
        layoffs = layoffs[offset:offset + limit]
        
        # Convert to dict
        data = [layoff.to_dict() for layoff in layoffs]
        
        return jsonify({
            'success': True,
            'count': len(data),
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'data': data
        })
        
    except Exception as e:
        logger.error(f"Error getting layoffs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/layoffs/<int:layoff_id>', methods=['GET'])
def get_layoff_by_id(layoff_id: int):
    """Get a specific layoff by ID"""
    try:
        layoff = db_manager.get_layoff_by_id(layoff_id)
        
        if not layoff:
            return jsonify({
                'success': False,
                'error': 'Layoff not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': layoff.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting layoff {layoff_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Statistics Endpoints
# ============================================================================

@app.route('/api/stats', methods=['GET'])
def get_statistics():
    """
    Get summary statistics
    
    Query Parameters:
        - start_date: Filter by start date (YYYY-MM-DD)
        - end_date: Filter by end date (YYYY-MM-DD)
        - source: Filter by data source
    
    Returns:
        JSON with statistics
    """
    try:
        # Parse query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        source = request.args.get('source')
        
        # Parse dates
        start_date = None
        end_date = None
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Get layoffs
        if start_date and end_date:
            layoffs = db_manager.get_layoffs_by_date_range(start_date, end_date)
        else:
            layoffs = db_manager.get_all_layoffs()
        
        # Apply source filter
        if source:
            layoffs = [l for l in layoffs if l.source and source.lower() in l.source.lower()]
        
        # Calculate statistics
        total_records = len(layoffs)
        total_employees = sum(l.employees_affected or 0 for l in layoffs)
        unique_companies = len(set(l.company_name for l in layoffs if l.company_name))
        
        # Count by source
        sources = {}
        for l in layoffs:
            src = l.source or 'Unknown'
            sources[src] = sources.get(src, 0) + 1
        
        # Count by country
        countries = {}
        for l in layoffs:
            c = l.country or 'Unknown'
            countries[c] = countries.get(c, 0) + 1
        
        # Count by industry
        industries = {}
        for l in layoffs:
            ind = l.industry or 'Unknown'
            industries[ind] = industries.get(ind, 0) + 1
        
        # Date range
        dates = [l.layoff_date for l in layoffs if l.layoff_date]
        min_date = min(dates).isoformat() if dates else None
        max_date = max(dates).isoformat() if dates else None
        
        return jsonify({
            'success': True,
            'stats': {
                'total_records': total_records,
                'total_employees_affected': total_employees,
                'unique_companies': unique_companies,
                'date_range': {
                    'min': min_date,
                    'max': max_date
                },
                'by_source': dict(sorted(sources.items(), key=lambda x: -x[1])),
                'by_country': dict(sorted(countries.items(), key=lambda x: -x[1])[:20]),
                'by_industry': dict(sorted(industries.items(), key=lambda x: -x[1])[:20])
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/sources', methods=['GET'])
def get_sources():
    """Get list of all data sources"""
    try:
        layoffs = db_manager.get_all_layoffs()
        sources = sorted(set(l.source for l in layoffs if l.source))
        
        return jsonify({
            'success': True,
            'sources': sources
        })
        
    except Exception as e:
        logger.error(f"Error getting sources: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/countries', methods=['GET'])
def get_countries():
    """Get list of all countries"""
    try:
        layoffs = db_manager.get_all_layoffs()
        countries = sorted(set(l.country for l in layoffs if l.country))
        
        return jsonify({
            'success': True,
            'countries': countries
        })
        
    except Exception as e:
        logger.error(f"Error getting countries: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/industries', methods=['GET'])
def get_industries():
    """Get list of all industries"""
    try:
        layoffs = db_manager.get_all_layoffs()
        industries = sorted(set(l.industry for l in layoffs if l.industry))
        
        return jsonify({
            'success': True,
            'industries': industries
        })
        
    except Exception as e:
        logger.error(f"Error getting industries: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Export Endpoints
# ============================================================================

@app.route('/api/export/<format>', methods=['GET'])
def export_data(format: str):
    """
    Export layoff data in various formats
    
    Path Parameters:
        - format: Export format (csv, json, excel)
    
    Query Parameters:
        - start_date: Filter by start date (YYYY-MM-DD)
        - end_date: Filter by end date (YYYY-MM-DD)
        - source: Filter by data source
        - country: Filter by country
    
    Returns:
        File download
    """
    try:
        if format not in ['csv', 'json', 'excel']:
            return jsonify({
                'success': False,
                'error': 'Invalid format. Use csv, json, or excel'
            }), 400
        
        # Parse query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        source = request.args.get('source')
        country = request.args.get('country')
        
        # Parse dates
        start_date = None
        end_date = None
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Get layoffs
        if start_date and end_date:
            layoffs = db_manager.get_layoffs_by_date_range(start_date, end_date)
        else:
            layoffs = db_manager.get_all_layoffs()
        
        # Apply filters
        if source:
            layoffs = [l for l in layoffs if l.source and source.lower() in l.source.lower()]
        
        if country:
            layoffs = [l for l in layoffs if l.country and country.lower() in l.country.lower()]
        
        # Export based on format
        if format == 'csv':
            filepath = exporter.to_csv(layoffs)
            return send_file(
                filepath,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'layoffs_{datetime.now().strftime("%Y%m%d")}.csv'
            )
        
        elif format == 'json':
            filepath = exporter.to_json(layoffs)
            return send_file(
                filepath,
                mimetype='application/json',
                as_attachment=True,
                download_name=f'layoffs_{datetime.now().strftime("%Y%m%d")}.json'
            )
        
        elif format == 'excel':
            filepath = exporter.to_excel(layoffs)
            return send_file(
                filepath,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'layoffs_{datetime.now().strftime("%Y%m%d")}.xlsx'
            )
        
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Scraper Control Endpoints
# ============================================================================

@app.route('/api/scrape', methods=['POST'])
def trigger_scrape():
    """
    Trigger a scraper run
    
    Request Body (optional):
        - scrapers: List of scraper names to run (default: all)
    
    Returns:
        JSON with scrape results
    """
    try:
        from src.scheduler import LayoffScheduler
        
        scheduler = LayoffScheduler(db_manager)
        
        # Check if specific scrapers requested
        data = request.get_json() or {}
        scrapers = data.get('scrapers')
        
        if scrapers:
            results = {}
            for scraper_name in scrapers:
                results[scraper_name] = scheduler.run_scraper(scraper_name)
        else:
            results = scheduler.run_all_scrapers()
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error running scrapers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the Flask API server"""
    port = int(os.getenv('API_PORT', 5000))
    host = os.getenv('API_HOST', '0.0.0.0')
    debug = os.getenv('API_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting Flask API on {host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    main()
