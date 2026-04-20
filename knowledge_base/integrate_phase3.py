"""
Integrate Phase 3 Data into Knowledge Base

This script loads the 140,714 pre-embedded chunks from Phase 3 and adds them
to the knowledge_base ChromaDB with proper metadata for semantic search.

Usage:
    python knowledge_base/integrate_phase3.py
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import sqlite3
from tqdm import tqdm
import sys

sys.path.append(str(Path(__file__).parent.parent))

from knowledge_base.config import CHROMADB_PATH
from knowledge_base.storage.chromadb_handler import init_chromadb

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Phase 3 paths
PROJECT_ROOT = Path(__file__).parent.parent
PHASE3_DUCKDB = PROJECT_ROOT / "data" / "duckdb" / "financial_intelligence.db"

# ChromaDB collection mapping from Phase 3
COLLECTION_MAPPING = {
    "business_overview": "business_overview",
    "risk_factors": "risk_factors",
    "mda": "mda",
    "financial_statements": "financial_statements",
    "all_sections": "all_sections",
}


def load_phase3_chunks() -> Dict[str, List[Dict]]:
    """
    Load chunks from Phase 3 DuckDB.
    
    Returns:
        Dict with collection names as keys, list of chunks as values
    """
    logger.info(f"📂 Loading Phase 3 chunks from {PHASE3_DUCKDB}")
    
    if not PHASE3_DUCKDB.exists():
        logger.error(f"Phase 3 DuckDB not found: {PHASE3_DUCKDB}")
        return {}
    
    try:
        conn = sqlite3.connect(PHASE3_DUCKDB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get chunks grouped by section type
        chunks_by_collection = {name: [] for name in COLLECTION_MAPPING.values()}
        
        # Query all chunks with metadata
        cursor.execute("""
            SELECT 
                chunk_id,
                doc_id,
                company,
                fiscal_year,
                doc_type,
                section_type,
                page_start,
                page_end,
                chunk_text,
                embedding_vector
            FROM chunks
            ORDER BY doc_id, page_start
        """)
        
        rows = cursor.fetchall()
        logger.info(f"✅ Found {len(rows)} chunks in Phase 3 database")
        
        # Map chunks to collections
        for row in tqdm(rows, desc="Mapping chunks to collections"):
            section_type = row['section_type']
            
            # Determine which collection this chunk belongs to
            collection_name = "all_sections"  # default
            
            if section_type == "business_overview":
                collection_name = "business_overview"
            elif section_type == "risk_factors":
                collection_name = "risk_factors"
            elif section_type == "mda":
                collection_name = "mda"
            elif section_type in ["financial_statements", "footnotes"]:
                collection_name = "financial_statements"
            
            chunk = {
                'chunk_id': row['chunk_id'],
                'doc_id': row['doc_id'],
                'company': row['company'],
                'fiscal_year': row['fiscal_year'],
                'doc_type': row['doc_type'],
                'section_type': section_type,
                'page_start': row['page_start'],
                'page_end': row['page_end'],
                'text': row['chunk_text'],
                'embedding': row['embedding_vector'],  # Store if available
            }
            
            chunks_by_collection[collection_name].append(chunk)
        
        # Print summary
        logger.info("\n📊 Chunk Summary:")
        total = 0
        for collection_name, chunks in chunks_by_collection.items():
            count = len(chunks)
            total += count
            logger.info(f"   {collection_name}: {count} chunks")
        
        logger.info(f"   Total: {total} chunks")
        
        conn.close()
        return chunks_by_collection
        
    except Exception as e:
        logger.error(f"Error loading Phase 3 chunks: {e}")
        return {}


def add_chunks_to_chromadb(chunks_by_collection: Dict[str, List[Dict]]) -> None:
    """
    Add chunks to knowledge_base ChromaDB.
    
    Args:
        chunks_by_collection: Dict with collection names and chunks
    """
    import chromadb
    
    logger.info(f"\n🔄 Adding chunks to ChromaDB at {CHROMADB_PATH}")
    
    try:
        # Initialize client
        client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
        
        # Create or get collections
        for collection_name in chunks_by_collection.keys():
            logger.info(f"\n📚 Processing collection: {collection_name}")
            
            try:
                collection = client.get_collection(collection_name)
                logger.info(f"   ✓ Collection exists")
            except:
                # Create collection if it doesn't exist
                collection = client.create_collection(
                    name=collection_name,
                    metadata={"description": f"Phase 3 {collection_name} chunks"}
                )
                logger.info(f"   ✅ Created collection")
            
            # Add chunks
            chunks = chunks_by_collection[collection_name]
            if not chunks:
                logger.info(f"   ⚠️  No chunks to add")
                continue
            
            # Prepare data for insertion
            ids = []
            documents = []
            metadatas = []
            
            for chunk in chunks:
                ids.append(chunk['chunk_id'])
                documents.append(chunk['text'])
                
                metadata = {
                    'doc_id': chunk['doc_id'],
                    'company': chunk['company'],
                    'fiscal_year': str(chunk['fiscal_year']),
                    'doc_type': chunk['doc_type'],
                    'section_type': chunk['section_type'],
                    'page_start': str(chunk['page_start']) if chunk['page_start'] else '0',
                    'page_end': str(chunk['page_end']) if chunk['page_end'] else '0',
                    'source': 'phase3',
                }
                metadatas.append(metadata)
            
            # Batch insert
            batch_size = 100
            for i in tqdm(range(0, len(ids), batch_size), desc=f"Adding {collection_name}"):
                batch_ids = ids[i:i+batch_size]
                batch_docs = documents[i:i+batch_size]
                batch_metas = metadatas[i:i+batch_size]
                
                collection.add(
                    ids=batch_ids,
                    documents=batch_docs,
                    metadatas=batch_metas
                )
            
            logger.info(f"   ✅ Added {len(ids)} chunks")
        
        logger.info(f"\n✅ All chunks added to ChromaDB successfully!")
        
    except Exception as e:
        logger.error(f"Error adding chunks to ChromaDB: {e}")


def main():
    """Main integration workflow."""
    logger.info("="*80)
    logger.info("PHASE 3 → KNOWLEDGE BASE INTEGRATION")
    logger.info("="*80)
    
    # Check if Phase 3 data exists
    if not PHASE3_DUCKDB.exists():
        logger.warning(f"Phase 3 DuckDB not found: {PHASE3_DUCKDB}")
        logger.info("To use this script:")
        logger.info("  1. Run Phase 3: python phase3/chromadb_setup.py")
        logger.info("  2. Then run this: python knowledge_base/integrate_phase3.py")
        return
    
    # Step 1: Load Phase 3 chunks
    chunks_by_collection = load_phase3_chunks()
    
    if not chunks_by_collection or all(len(v) == 0 for v in chunks_by_collection.values()):
        logger.error("No chunks found to integrate")
        return
    
    # Step 2: Initialize knowledge_base ChromaDB
    logger.info("\n🔧 Initializing ChromaDB...")
    init_chromadb()
    logger.info("✅ ChromaDB initialized")
    
    # Step 3: Add chunks
    add_chunks_to_chromadb(chunks_by_collection)
    
    logger.info("\n" + "="*80)
    logger.info("✅ INTEGRATION COMPLETE")
    logger.info("="*80)
    logger.info("\nYou can now query the knowledge base with 140,000+ pre-embedded chunks!")


if __name__ == "__main__":
    main()
