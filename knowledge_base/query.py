"""
Knowledge Base Status & Query

Check what's in the knowledge base and run test queries.

Usage:
    python knowledge_base/query.py --status              # Show stats
    python knowledge_base/query.py --search "query"      # Search documents
"""

import json
import logging
from pathlib import Path
import sys
import argparse
from typing import List

sys.path.append(str(Path(__file__).parent.parent))

from knowledge_base.config import PER_PDF_DIR, CHROMADB_PATH
from knowledge_base.storage.chromadb_handler import init_chromadb
import chromadb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_kb_status() -> None:
    """Display knowledge base status."""
    logger.info("="*80)
    logger.info("KNOWLEDGE BASE STATUS")
    logger.info("="*80)
    
    # Check per-PDF files
    per_pdf_files = list(PER_PDF_DIR.glob("*.json"))
    logger.info(f"\n📄 Per-PDF Extractions: {len(per_pdf_files)} files")
    
    if per_pdf_files:
        # Sample first file
        with open(per_pdf_files[0]) as f:
            sample = json.load(f)
            logger.info(f"   Sample: {sample['company']} {sample['fiscal_year']}")
    
    # Check ChromaDB
    try:
        client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
        collections = client.list_collections()
        logger.info(f"\n🗄️  ChromaDB Collections: {len(collections)}")
        
        total_chunks = 0
        for collection in collections:
            coll = client.get_collection(collection.name)
            count = coll.count()
            total_chunks += count
            logger.info(f"   {collection.name}: {count} chunks")
        
        logger.info(f"   Total: {total_chunks} chunks")
    except Exception as e:
        logger.error(f"Error accessing ChromaDB: {e}")
    
    logger.info("\n" + "="*80)


def search_kb(query: str, collection: str = "knowledge_insights", n_results: int = 5) -> None:
    """Search knowledge base."""
    logger.info(f"\n🔍 Searching for: {query}")
    logger.info(f"   Collection: {collection}")
    logger.info(f"   Results: {n_results}\n")
    
    try:
        client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
        
        # Get all collections if specified collection doesn't exist
        all_collections = [c.name for c in client.list_collections()]
        
        if collection not in all_collections:
            logger.warning(f"Collection '{collection}' not found")
            logger.info(f"Available collections: {', '.join(all_collections)}")
            
            if not all_collections:
                logger.error("No collections exist")
                return
            
            collection = all_collections[0]
            logger.info(f"Using collection '{collection}' instead")
        
        coll = client.get_collection(collection)
        
        results = coll.query(
            query_texts=[query],
            n_results=n_results
        )
        
        if not results['documents'] or not results['documents'][0]:
            logger.info("No results found")
            return
        
        for i, (doc, distance, metadata) in enumerate(zip(
            results['documents'][0],
            results['distances'][0],
            results['metadatas'][0]
        ), 1):
            logger.info(f"\n{i}. (distance: {distance:.3f})")
            logger.info(f"   {doc[:200]}...")
            if metadata:
                if 'company' in metadata:
                    logger.info(f"   Company: {metadata.get('company')}")
                if 'fiscal_year' in metadata:
                    logger.info(f"   Year: {metadata.get('fiscal_year')}")
    
    except Exception as e:
        logger.error(f"Search error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Knowledge Base Query Tool")
    parser.add_argument("--status", action="store_true", help="Show KB status")
    parser.add_argument("--search", type=str, help="Search query")
    parser.add_argument("--collection", type=str, default="knowledge_insights", help="Collection to search")
    parser.add_argument("--results", type=int, default=5, help="Number of results")
    
    args = parser.parse_args()
    
    if args.status or (not args.search and not args.status):
        get_kb_status()
    
    if args.search:
        search_kb(args.search, args.collection, args.results)


if __name__ == "__main__":
    main()
