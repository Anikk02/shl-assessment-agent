# scripts/build_catalog.py
"""Build catalog index from SHL JSON URL"""

import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.catalog.loader import CatalogLoader
from app.catalog.indexer import CatalogIndexer
from app.logger import get_logger

logger = get_logger(__name__)


def main():
    """Load catalog and build index"""
    parser = argparse.ArgumentParser(description='Build SHL catalog index')
    parser.add_argument('--force', action='store_true', help='Force refresh from URL')
    args = parser.parse_args()
    
    logger.info("Building catalog...")
    
    # Load catalog
    loader = CatalogLoader()
    products = loader.load(force_refresh=args.force)
    
    if not products:
        logger.error("No products loaded")
        sys.exit(1)
    
    logger.info(f"Loaded {len(products)} products")
    
    # Build index
    indexer = CatalogIndexer()
    indexer.build_index(products)
    indexer.save_index()
    
    logger.info("Catalog build complete")


if __name__ == "__main__":
    main()