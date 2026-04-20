"""
Phase 3 Setup: Run all setup steps (Neo4j + DuckDB + ChromaDB)
"""

import time
from duckdb_setup import setup_duckdb
from chromadb_setup import setup_chromadb
from neo4j_setup import setup_neo4j


def main():
    """
    Run complete Phase 3 setup.
    """
    print(f"\n{'='*80}")
    print(f"PHASE 3: STORAGE & RETRIEVAL SETUP")
    print(f"{'='*80}")
    
    start_time = time.time()
    
    # Step 1: Neo4j (graph — uses section_id/chunk_id, no embeddings needed)
    print(f"\n{'='*80}")
    print(f"STEP 1: NEO4J SETUP")
    print(f"{'='*80}")
    
    neo4j_stats = setup_neo4j()
    
    # Step 2: Setup DuckDB
    print(f"\n{'='*80}")
    print(f"STEP 2: DUCKDB SETUP")
    print(f"{'='*80}")
    
    duckdb_stats = setup_duckdb()
    
    # Step 3: Setup ChromaDB (embeddings — expensive step, runs last)
    print(f"\n{'='*80}")
    print(f"STEP 3: CHROMADB SETUP")
    print(f"{'='*80}")
    
    chromadb_stats = setup_chromadb()
    
    # Summary
    elapsed = time.time() - start_time
    
    print(f"\n{'='*80}")
    print(f"PHASE 3 SETUP COMPLETE")
    print(f"{'='*80}")
    
    print(f"\n✅ Neo4j Statistics:")
    print(f"   Documents: {neo4j_stats['documents']}")
    
    print(f"\n✅ DuckDB Statistics:")
    print(f"   Documents: {duckdb_stats['documents']}")
    print(f"   Sections: {duckdb_stats['sections']}")
    print(f"   Tables: {duckdb_stats['tables']}")
    print(f"   Signals: {duckdb_stats['signals']}")
    
    print(f"\n✅ ChromaDB Statistics:")
    total_chunks = sum(chromadb_stats.values())
    print(f"   Total Chunks: {total_chunks}")
    for collection_name, count in chromadb_stats.items():
        print(f"   {collection_name}: {count}")
    
    print(f"\n⏱️  Total Time: {elapsed:.1f}s")
    
    print(f"\n{'='*80}")
    print(f"✅ Phase 3 Ready!")
    print(f"{'='*80}")
    print(f"\nYou can now:")
    print(f"  1. Query DuckDB for structured data")
    print(f"  2. Query ChromaDB for semantic search")
    print(f"  3. Use the retrieval pipeline for unified queries")
    print(f"\nTest the system:")
    print(f"  python query_router.py    # Test query routing")
    print(f"  python retrieval.py       # Test retrieval pipeline")


if __name__ == "__main__":
    main()
