#!/usr/bin/env python3
"""
Meilisearch Search Script for Layoff Data

This script provides various search capabilities for the layoff data indexed in Meilisearch.
It demonstrates fuzzy search, filtering, sorting, and pagination.

Usage:
    python scripts/search_meilisearch.py --query "google"
    python scripts/search_meilisearch.py --query "amazon" --country "US"
    python scripts/search_meilisearch.py --industry "Technology" --min-affected 100
    python scripts/search_meilisearch.py --date-from "2025-01-01" --date-to "2025-12-31"
    python scripts/search_meilisearch.py --query "meta" --sort "employees_affected:desc"
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

try:
    import meilisearch
except ImportError:
    print("Error: meilisearch package not installed.")
    print("Install it with: pip install meilisearch")
    sys.exit(1)

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

# =============================================================================
# CONFIGURATION (from .env file)
# =============================================================================

MEILISEARCH_URL = os.getenv("MEILISEARCH_URL", "http://localhost:7700")
MEILISEARCH_API_KEY = os.getenv("MEILISEARCH_API_KEY", "")
INDEX_NAME = "layoffs"


# =============================================================================
# SEARCH PARAMETERS EXPLAINED
# =============================================================================
"""
SEARCH PARAMETERS REFERENCE
===========================

When performing a search, you can use the following parameters:

1. q (query string)
   - The text to search for
   - Searches in "searchable" attributes (company_name in our case)
   - Supports FUZZY MATCHING (typo tolerance):
     * "amazn" will find "Amazon"
     * "gogle" will find "Google"
     * "micorsoft" will find "Microsoft"
   - Empty string "" returns all documents (useful with filters)

2. filter
   - Filter results based on field values
   - Only works on "filterable" attributes: industry, layoff_date, 
     employees_affected, source, country
   - Syntax examples:
     * Equality: 'country = "US"'
     * Comparison: 'employees_affected > 100'
     * Range: 'employees_affected >= 100 AND employees_affected <= 500'
     * Date range: 'layoff_date >= "2025-01-01" AND layoff_date <= "2025-12-31"'
     * Multiple conditions: 'country = "US" AND industry = "Technology"'
     * OR conditions: 'country = "US" OR country = "UK"'
     * IN operator: 'country IN ["US", "UK", "India"]'
     * NOT: 'NOT country = "US"'
     * IS NULL: 'employees_affected IS NULL'
     * IS NOT NULL: 'employees_affected IS NOT NULL'

3. sort
   - Order results by field values
   - Only works on "sortable" attributes: layoff_date, employees_affected
   - Format: ["field:direction"]
   - Examples:
     * ["employees_affected:desc"] - Most affected first
     * ["layoff_date:desc"] - Most recent first
     * ["layoff_date:asc"] - Oldest first
     * ["employees_affected:desc", "layoff_date:desc"] - Multi-field sort

4. limit
   - Maximum number of results to return
   - Default: 20
   - Maximum: 1000

5. offset
   - Number of results to skip (for pagination)
   - Default: 0
   - Example: offset=20 with limit=20 gives page 2

6. attributesToRetrieve
   - Which fields to include in results
   - Default: all fields
   - Example: ["company_name", "employees_affected"]

7. attributesToHighlight
   - Fields where matching text should be highlighted
   - Returns with <em> tags around matches
   - Example: ["company_name"]

8. highlightPreTag / highlightPostTag
   - Custom tags for highlighting
   - Default: "<em>" and "</em>"

9. showMatchesPosition
   - If True, returns position of matches in each field
   - Useful for custom highlighting

10. matchingStrategy
    - How to match multi-word queries
    - "all": All words must match (more precise)
    - "last": Match as many words as possible (more lenient)
    - Default: "last"


INDEXED FIELDS IN OUR DATA
==========================

| Field              | Type    | Searchable | Filterable | Sortable | Description                          |
|--------------------|---------|------------|------------|----------|--------------------------------------|
| id                 | Integer | No         | No         | No       | Unique identifier (primary key)      |
| company_name       | String  | YES        | No         | No       | Company name (with fuzzy matching)   |
| industry           | String  | No         | YES        | No       | Industry/sector of the company       |
| layoff_date        | String  | No         | YES        | YES      | Date of layoff (YYYY-MM-DD format)   |
| employees_affected | Integer | No         | YES        | YES      | Number of employees laid off         |
| source             | String  | No         | YES        | No       | Data source (layoffs.fyi, etc.)      |
| country            | String  | No         | YES        | No       | Country where layoff occurred        |


FUZZY MATCHING (TYPO TOLERANCE)
===============================

Meilisearch automatically handles typos in search queries:

- Words with 4+ characters: 1 typo allowed
- Words with 8+ characters: 2 typos allowed

Examples:
- "amazn" → finds "Amazon"
- "gogle" → finds "Google"  
- "facebok" → finds "Facebook"
- "micorsoft" → finds "Microsoft"
- "twtter" → finds "Twitter"

This is enabled by default and works on the searchable field (company_name).
"""


# =============================================================================
# SEARCH FUNCTIONS
# =============================================================================

def create_client() -> meilisearch.Client:
    """Create and return a Meilisearch client."""
    return meilisearch.Client(MEILISEARCH_URL, MEILISEARCH_API_KEY)


def build_filter(
    industry: Optional[str] = None,
    country: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_affected: Optional[int] = None,
    max_affected: Optional[int] = None,
) -> Optional[str]:
    """
    Build a filter string from individual filter parameters.
    
    Args:
        industry: Filter by industry (e.g., "Technology")
        country: Filter by country (e.g., "US")
        source: Filter by data source (e.g., "layoffs.fyi")
        date_from: Minimum layoff date (YYYY-MM-DD)
        date_to: Maximum layoff date (YYYY-MM-DD)
        min_affected: Minimum employees affected
        max_affected: Maximum employees affected
    
    Returns:
        Filter string for Meilisearch query, or None if no filters
    """
    conditions = []
    
    if industry:
        conditions.append(f'industry = "{industry}"')
    
    if country:
        conditions.append(f'country = "{country}"')
    
    if source:
        conditions.append(f'source = "{source}"')
    
    if date_from:
        conditions.append(f'layoff_date >= "{date_from}"')
    
    if date_to:
        conditions.append(f'layoff_date <= "{date_to}"')
    
    if min_affected is not None:
        conditions.append(f'employees_affected >= {min_affected}')
    
    if max_affected is not None:
        conditions.append(f'employees_affected <= {max_affected}')
    
    return " AND ".join(conditions) if conditions else None


def search_layoffs(
    query: str = "",
    industry: Optional[str] = None,
    country: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_affected: Optional[int] = None,
    max_affected: Optional[int] = None,
    sort_by: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    highlight: bool = False,
) -> dict:
    """
    Search layoff data with various filters and options.
    
    Args:
        query: Search query (searches company_name with fuzzy matching)
        industry: Filter by industry
        country: Filter by country
        source: Filter by data source
        date_from: Filter by minimum date (YYYY-MM-DD)
        date_to: Filter by maximum date (YYYY-MM-DD)
        min_affected: Filter by minimum employees affected
        max_affected: Filter by maximum employees affected
        sort_by: Sort field and direction (e.g., "employees_affected:desc")
        limit: Maximum results to return (default: 20, max: 1000)
        offset: Results to skip for pagination (default: 0)
        highlight: Whether to highlight matching text (default: False)
    
    Returns:
        Search results dictionary with 'hits', 'estimatedTotalHits', etc.
    """
    client = create_client()
    index = client.index(INDEX_NAME)
    
    # Build search parameters
    search_params = {
        "limit": limit,
        "offset": offset,
    }
    
    # Add filter if any filter parameters provided
    filter_str = build_filter(
        industry=industry,
        country=country,
        source=source,
        date_from=date_from,
        date_to=date_to,
        min_affected=min_affected,
        max_affected=max_affected,
    )
    if filter_str:
        search_params["filter"] = filter_str
    
    # Add sorting
    if sort_by:
        search_params["sort"] = [sort_by]
    
    # Add highlighting
    if highlight:
        search_params["attributesToHighlight"] = ["company_name"]
        search_params["highlightPreTag"] = "**"
        search_params["highlightPostTag"] = "**"
    
    # Perform search
    results = index.search(query, search_params)
    
    return results


def safe_get(obj, key, default=None):
    """Safely get a value from either a dict or Pydantic model."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def format_results(results, show_json: bool = False) -> str:
    """Format search results for display."""
    output = []
    
    hits = safe_get(results, "hits", [])
    total = safe_get(results, "estimatedTotalHits", safe_get(results, "estimated_total_hits", 0))
    processing_time = safe_get(results, "processingTimeMs", safe_get(results, "processing_time_ms", 0))
    query = safe_get(results, "query", "")
    
    output.append("=" * 70)
    output.append(f"SEARCH RESULTS")
    output.append("=" * 70)
    output.append(f"Query: '{query}' | Found: {total} results | Time: {processing_time}ms")
    output.append("-" * 70)
    
    if not hits:
        output.append("No results found.")
    else:
        for i, hit in enumerate(hits, 1):
            output.append(f"\n[{i}] {safe_get(hit, 'company_name', 'N/A')}")
            output.append(f"    Industry: {safe_get(hit, 'industry', 'N/A')}")
            output.append(f"    Country: {safe_get(hit, 'country', 'N/A')}")
            output.append(f"    Date: {safe_get(hit, 'layoff_date', 'N/A')}")
            output.append(f"    Employees Affected: {safe_get(hit, 'employees_affected', 'N/A')}")
            output.append(f"    Source: {safe_get(hit, 'source', 'N/A')}")
            
            # Show highlighted version if available
            formatted = safe_get(hit, "_formatted")
            if formatted:
                formatted_name = safe_get(formatted, "company_name")
                if formatted_name and formatted_name != safe_get(hit, "company_name"):
                    output.append(f"    Matched: {formatted_name}")
    
    output.append("\n" + "-" * 70)
    
    if show_json:
        output.append("\nRAW JSON RESPONSE:")
        # Convert to dict if it's a Pydantic model
        if hasattr(results, "model_dump"):
            results = results.model_dump()
        elif hasattr(results, "dict"):
            results = results.dict()
        output.append(json.dumps(results, indent=2, default=str))
    
    return "\n".join(output)


def interactive_demo():
    """Run an interactive demo showing various search capabilities."""
    print("\n" + "=" * 70)
    print("MEILISEARCH LAYOFF DATA - INTERACTIVE DEMO")
    print("=" * 70)
    
    demos = [
        {
            "title": "1. Simple Search (Company Name)",
            "description": "Search for 'Google' - finds all Google layoffs",
            "params": {"query": "Google", "limit": 5}
        },
        {
            "title": "2. Fuzzy Search (Typo Tolerance)",
            "description": "Search for 'amazn' - finds 'Amazon' despite typo",
            "params": {"query": "amazn", "limit": 5}
        },
        {
            "title": "3. Another Fuzzy Search",
            "description": "Search for 'micorsoft' - finds 'Microsoft' with 2 typos",
            "params": {"query": "micorsoft", "limit": 5}
        },
        {
            "title": "4. Filter by Country",
            "description": "All layoffs in India",
            "params": {"query": "", "country": "India", "limit": 5}
        },
        {
            "title": "5. Filter by Industry",
            "description": "All layoffs in Technology industry",
            "params": {"query": "", "industry": "Technology", "limit": 5}
        },
        {
            "title": "6. Filter by Employee Count",
            "description": "Layoffs affecting 500+ employees",
            "params": {"query": "", "min_affected": 500, "limit": 5}
        },
        {
            "title": "7. Date Range Filter",
            "description": "Layoffs in December 2025",
            "params": {"query": "", "date_from": "2025-12-01", "date_to": "2025-12-31", "limit": 5}
        },
        {
            "title": "8. Combined Search + Filter",
            "description": "Search 'tech' in US with 100+ affected",
            "params": {"query": "tech", "country": "US", "min_affected": 100, "limit": 5}
        },
        {
            "title": "9. Sorted Results (Largest Layoffs)",
            "description": "All results sorted by employees_affected descending",
            "params": {"query": "", "sort_by": "employees_affected:desc", "limit": 5}
        },
        {
            "title": "10. Most Recent Layoffs",
            "description": "All results sorted by layoff_date descending",
            "params": {"query": "", "sort_by": "layoff_date:desc", "limit": 5}
        },
        {
            "title": "11. Search with Highlighting",
            "description": "Search 'meta' with matched text highlighted",
            "params": {"query": "meta", "highlight": True, "limit": 5}
        },
    ]
    
    for demo in demos:
        print(f"\n{'='*70}")
        print(f"DEMO: {demo['title']}")
        print(f"Description: {demo['description']}")
        print(f"Parameters: {demo['params']}")
        print("-" * 70)
        
        try:
            results = search_layoffs(**demo["params"])
            print(format_results(results))
        except Exception as e:
            print(f"Error: {e}")
        
        print()


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Search layoff data in Meilisearch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --query "google"
  %(prog)s --query "amazon" --country "US"
  %(prog)s --industry "Technology" --min-affected 100
  %(prog)s --date-from "2025-01-01" --date-to "2025-12-31"
  %(prog)s --query "meta" --sort "employees_affected:desc"
  %(prog)s --demo  # Run interactive demo
        """
    )
    
    # Search parameters
    parser.add_argument(
        "-q", "--query",
        default="",
        help="Search query (searches company_name with fuzzy matching)"
    )
    
    # Filter parameters
    parser.add_argument(
        "--industry",
        help="Filter by industry (e.g., 'Technology', 'Finance')"
    )
    parser.add_argument(
        "--country",
        help="Filter by country (e.g., 'US', 'India', 'UK')"
    )
    parser.add_argument(
        "--source",
        help="Filter by data source (e.g., 'layoffs.fyi')"
    )
    parser.add_argument(
        "--date-from",
        help="Filter by minimum date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--date-to",
        help="Filter by maximum date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--min-affected",
        type=int,
        help="Filter by minimum employees affected"
    )
    parser.add_argument(
        "--max-affected",
        type=int,
        help="Filter by maximum employees affected"
    )
    
    # Sort parameters
    parser.add_argument(
        "--sort",
        help="Sort by field (e.g., 'employees_affected:desc', 'layoff_date:asc')"
    )
    
    # Pagination
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum results to return (default: 20, max: 1000)"
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Results to skip for pagination (default: 0)"
    )
    
    # Display options
    parser.add_argument(
        "--highlight",
        action="store_true",
        help="Highlight matching text in results"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Show raw JSON response"
    )
    
    # Demo mode
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run interactive demo showing various search capabilities"
    )
    
    args = parser.parse_args()
    
    # Check connection first
    try:
        client = create_client()
        client.health()
    except Exception as e:
        print(f"Error: Cannot connect to Meilisearch at {MEILISEARCH_URL}")
        print(f"Details: {e}")
        sys.exit(1)
    
    # Run demo or search
    if args.demo:
        interactive_demo()
    else:
        try:
            results = search_layoffs(
                query=args.query,
                industry=args.industry,
                country=args.country,
                source=args.source,
                date_from=args.date_from,
                date_to=args.date_to,
                min_affected=args.min_affected,
                max_affected=args.max_affected,
                sort_by=args.sort,
                limit=args.limit,
                offset=args.offset,
                highlight=args.highlight,
            )
            print(format_results(results, show_json=args.json))
        except Exception as e:
            print(f"Search error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
