#!/usr/bin/env python3
"""
Script to upload layoff data to Meilisearch.

Features:
- Deletes existing index and creates fresh one
- Indexes layoff data with searchable company_name field
- Enables filtering on industry, layoff_date, employees_affected, source, country
- Enables fuzzy matching (typo tolerance) for search

Usage:
    python scripts/upload_to_meilisearch.py
"""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

import meilisearch

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

# Meilisearch configuration (from .env file)
MEILISEARCH_URL = os.getenv("MEILISEARCH_URL", "http://localhost:7700")
MEILISEARCH_API_KEY = os.getenv("MEILISEARCH_API_KEY", "")

# Index configuration
INDEX_NAME = "layoffs"
PRIMARY_KEY = "id"

# Data file path
DATA_FILE = Path(__file__).parent.parent / "data" / "exports" / "layoffs_all.json"

# Batch size for uploading documents (Meilisearch recommends batches)
BATCH_SIZE = 1000


def load_layoff_data(filepath: Path) -> list[dict]:
    """Load layoff data from JSON file."""
    print(f"Loading data from: {filepath}")
    
    if not filepath.exists():
        print(f"Error: Data file not found: {filepath}")
        sys.exit(1)
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"Loaded {len(data)} records")
    return data


def prepare_documents(raw_data: list[dict]) -> list[dict]:
    """
    Prepare documents for Meilisearch indexing.
    
    Extracts only the required fields and ensures data consistency.
    """
    documents = []
    
    for record in raw_data:
        doc = {
            "id": record.get("id"),
            "company_name": record.get("company_name", ""),
            "industry": record.get("industry", ""),
            "layoff_date": record.get("layoff_date", ""),
            "employees_affected": record.get("employees_affected"),
            "source": record.get("source", ""),
            "country": record.get("country", ""),
        }
        
        # Ensure id is present (required for primary key)
        if doc["id"] is not None:
            documents.append(doc)
    
    return documents


def wait_for_task(client: meilisearch.Client, task_uid: int, timeout: int = 60):
    """Wait for a Meilisearch task to complete."""
    start_time = time.time()
    
    while True:
        task = client.get_task(task_uid)
        # Task is a Pydantic model, access attributes directly
        status = getattr(task, "status", "unknown")
        
        if status == "succeeded":
            return True
        elif status == "failed":
            error = getattr(task, "error", None)
            print(f"Task failed: {error if error else 'Unknown error'}")
            return False
        elif time.time() - start_time > timeout:
            print(f"Task timed out after {timeout} seconds")
            return False
        
        time.sleep(0.5)


def setup_index(client: meilisearch.Client) -> meilisearch.index.Index:
    """
    Delete existing index (if exists) and create a fresh one.
    Configure searchable and filterable attributes.
    """
    print(f"\n{'='*50}")
    print("Setting up Meilisearch index...")
    print(f"{'='*50}")
    
    # Delete existing index if it exists
    try:
        print(f"Checking for existing index '{INDEX_NAME}'...")
        existing_indexes = client.get_indexes()
        # Handle both dict and Pydantic model responses
        if hasattr(existing_indexes, 'results'):
            results_list = existing_indexes.results
        else:
            results_list = existing_indexes.get("results", [])
        index_exists = any(idx.uid == INDEX_NAME for idx in results_list)
        
        if index_exists:
            print(f"Deleting existing index '{INDEX_NAME}'...")
            task = client.delete_index(INDEX_NAME)
            wait_for_task(client, task.task_uid)
            print("Existing index deleted.")
    except Exception as e:
        print(f"Note: Could not check/delete existing index: {e}")
    
    # Create new index
    print(f"Creating new index '{INDEX_NAME}' with primary key '{PRIMARY_KEY}'...")
    task = client.create_index(INDEX_NAME, {"primaryKey": PRIMARY_KEY})
    wait_for_task(client, task.task_uid)
    print("Index created successfully.")
    
    # Get index reference
    index = client.index(INDEX_NAME)
    
    # Configure searchable attributes (fields that can be searched)
    print("\nConfiguring searchable attributes: ['company_name']")
    task = index.update_searchable_attributes(["company_name"])
    wait_for_task(client, task.task_uid)
    
    # Configure filterable attributes (fields that can be used in filters)
    filterable_attrs = ["industry", "layoff_date", "employees_affected", "source", "country"]
    print(f"Configuring filterable attributes: {filterable_attrs}")
    task = index.update_filterable_attributes(filterable_attrs)
    wait_for_task(client, task.task_uid)
    
    # Configure sortable attributes (for sorting results)
    sortable_attrs = ["layoff_date", "employees_affected"]
    print(f"Configuring sortable attributes: {sortable_attrs}")
    task = index.update_sortable_attributes(sortable_attrs)
    wait_for_task(client, task.task_uid)
    
    # Configure typo tolerance for fuzzy matching
    print("\nConfiguring typo tolerance (fuzzy matching)...")
    typo_config = {
        "enabled": True,
        "minWordSizeForTypos": {
            "oneTypo": 4,   # Allow 1 typo for words with 4+ characters
            "twoTypos": 8   # Allow 2 typos for words with 8+ characters
        },
        "disableOnAttributes": [],  # Don't disable on any attributes
        "disableOnWords": []        # Don't disable for any specific words
    }
    task = index.update_typo_tolerance(typo_config)
    wait_for_task(client, task.task_uid)
    print("Typo tolerance enabled - fuzzy matching is active!")
    
    return index


def upload_documents(index: meilisearch.index.Index, documents: list[dict], client: meilisearch.Client):
    """Upload documents to Meilisearch in batches."""
    total_docs = len(documents)
    total_batches = (total_docs + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"\n{'='*50}")
    print(f"Uploading {total_docs} documents in {total_batches} batches...")
    print(f"{'='*50}")
    
    for i in range(0, total_docs, BATCH_SIZE):
        batch = documents[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        
        print(f"Uploading batch {batch_num}/{total_batches} ({len(batch)} documents)...")
        task = index.add_documents(batch)
        
        # Wait for batch to complete
        if not wait_for_task(client, task.task_uid, timeout=120):
            print(f"Warning: Batch {batch_num} may not have completed successfully")
    
    print("\nAll documents uploaded successfully!")


def safe_get(obj, key, default=None):
    """Safely get a value from either a dict or Pydantic model."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def verify_upload(index: meilisearch.index.Index):
    """Verify the upload by getting stats and running a test search."""
    print(f"\n{'='*50}")
    print("Verifying upload...")
    print(f"{'='*50}")
    
    # Wait a moment for indexing to complete
    time.sleep(2)
    
    # Get index stats
    stats = index.get_stats()
    num_docs = safe_get(stats, 'numberOfDocuments', safe_get(stats, 'number_of_documents', 'unknown'))
    print(f"Total documents in index: {num_docs}")
    
    # Test search with fuzzy matching
    print("\n--- Test Search: 'amazn' (fuzzy match for 'Amazon') ---")
    results = index.search("amazn", {"limit": 3})
    hits = safe_get(results, 'hits', [])
    print(f"Found {len(hits)} results:")
    for hit in hits[:3]:
        print(f"  - {safe_get(hit, 'company_name')} | {safe_get(hit, 'industry')} | {safe_get(hit, 'layoff_date')}")
    
    # Test search with filter
    print("\n--- Test Search with Filter: 'tech' in industry='Technology' ---")
    results = index.search("", {
        "filter": "industry = 'Technology'",
        "limit": 3
    })
    hits = safe_get(results, 'hits', [])
    total = safe_get(results, 'estimatedTotalHits', safe_get(results, 'estimated_total_hits', 0))
    print(f"Found {total} total results (showing first 3):")
    for hit in hits[:3]:
        print(f"  - {safe_get(hit, 'company_name')} | {safe_get(hit, 'industry')} | {safe_get(hit, 'employees_affected')} affected")
    
    # Test filter by date range
    print("\n--- Test Filter: Layoffs in December 2025 ---")
    results = index.search("", {
        "filter": "layoff_date >= '2025-12-01' AND layoff_date <= '2025-12-31'",
        "limit": 5
    })
    hits = safe_get(results, 'hits', [])
    total = safe_get(results, 'estimatedTotalHits', safe_get(results, 'estimated_total_hits', 0))
    print(f"Found {total} layoffs in December 2025 (showing first 5):")
    for hit in hits[:5]:
        print(f"  - {safe_get(hit, 'company_name')} | {safe_get(hit, 'layoff_date')} | {safe_get(hit, 'employees_affected')} affected")


def print_usage_examples():
    """Print example queries for using the indexed data."""
    print(f"\n{'='*50}")
    print("USAGE EXAMPLES")
    print(f"{'='*50}")
    
    examples = """
# Python Example - Search by company name (with fuzzy matching):
from meilisearch import Client
client = Client("http://172.31.36.21:7700", "6418efb6dc144d4b")
index = client.index("layoffs")

# Simple search (supports typos like 'gogle' -> 'Google')
results = index.search("gogle")

# Search with filters
results = index.search("", {
    "filter": "industry = 'Technology' AND country = 'US'"
})

# Search with date range filter
results = index.search("", {
    "filter": "layoff_date >= '2025-01-01' AND employees_affected > 100"
})

# Combined search and filter
results = index.search("meta", {
    "filter": "country = 'US'",
    "sort": ["employees_affected:desc"]
})

# cURL Examples:
# Simple search
curl 'http://172.31.36.21:7700/indexes/layoffs/search' \\
  -H 'Authorization: Bearer 6418efb6dc144d4b' \\
  -H 'Content-Type: application/json' \\
  -d '{"q": "google"}'

# Search with filter
curl 'http://172.31.36.21:7700/indexes/layoffs/search' \\
  -H 'Authorization: Bearer 6418efb6dc144d4b' \\
  -H 'Content-Type: application/json' \\
  -d '{"q": "", "filter": "country = US AND employees_affected > 500"}'
"""
    print(examples)


def main():
    """Main function to orchestrate the upload process."""
    print("="*60)
    print("LAYOFF DATA -> MEILISEARCH UPLOAD SCRIPT")
    print("="*60)
    print(f"Meilisearch URL: {MEILISEARCH_URL}")
    print(f"Index Name: {INDEX_NAME}")
    print(f"Data File: {DATA_FILE}")
    
    # Initialize Meilisearch client
    print("\nConnecting to Meilisearch...")
    try:
        client = meilisearch.Client(MEILISEARCH_URL, MEILISEARCH_API_KEY)
        # Test connection
        health = client.health()
        # Handle both dict and Pydantic model responses
        status = health.get('status', 'unknown') if isinstance(health, dict) else getattr(health, 'status', 'unknown')
        print(f"Connection successful! Server status: {status}")
    except Exception as e:
        print(f"Error connecting to Meilisearch: {e}")
        sys.exit(1)
    
    # Load data
    raw_data = load_layoff_data(DATA_FILE)
    
    # Prepare documents
    documents = prepare_documents(raw_data)
    print(f"Prepared {len(documents)} documents for indexing")
    
    # Setup index (delete if exists, create fresh, configure)
    index = setup_index(client)
    
    # Upload documents
    upload_documents(index, documents, client)
    
    # Verify upload
    verify_upload(index)
    
    # Print usage examples
    print_usage_examples()
    
    print("\n" + "="*60)
    print("UPLOAD COMPLETE!")
    print("="*60)
    print(f"\nYour layoff data is now searchable at: {MEILISEARCH_URL}")
    print(f"Index: {INDEX_NAME}")
    print("\nFeatures enabled:")
    print("  ✓ Fuzzy search (typo tolerance) on company_name")
    print("  ✓ Filtering by: industry, layoff_date, employees_affected, source, country")
    print("  ✓ Sorting by: layoff_date, employees_affected")


if __name__ == "__main__":
    main()
