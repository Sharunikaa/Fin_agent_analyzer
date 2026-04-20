"""
Retrieval Pipeline: Retrieve and rerank results from DuckDB and ChromaDB
"""

import duckdb
import chromadb
from typing import Dict, List, Optional
from sentence_transformers import SentenceTransformer

from config import DUCKDB_PATH, CHROMADB_PATH, EMBEDDING_MODEL, RETRIEVAL_CONFIG, CHROMADB_COLLECTIONS
from query_router import route_query


class RetrievalPipeline:
    """
    Unified retrieval pipeline for structured and semantic queries.
    """
    
    def __init__(self):
        """Initialize retrieval pipeline."""
        print("🔧 Initializing retrieval pipeline...")
        
        # Connect to DuckDB
        self.duckdb_conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        print(f"   ✅ Connected to DuckDB: {DUCKDB_PATH}")
        
        # Connect to ChromaDB
        self.chromadb_client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
        print(f"   ✅ Connected to ChromaDB: {CHROMADB_PATH}")
        
        # Load embedding model
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"   ✅ Loaded embedding model: {EMBEDDING_MODEL}")
    
    def retrieve_from_duckdb(self, query: str, filters: Dict = None) -> List[Dict]:
        """
        Retrieve structured data from DuckDB.
        
        Args:
            query: User query
            filters: Optional filters (company, year, etc.)
            
        Returns:
            results: List of result dicts
        """
        results = []
        
        # Build SQL query based on filters
        if filters and 'company' in filters:
            company = filters['company']
            
            # Get document metadata
            docs = self.duckdb_conn.execute("""
                SELECT * FROM documents WHERE company = ? ORDER BY year DESC
            """, [company]).fetchall()
            
            if docs:
                results.append({
                    'type': 'documents',
                    'data': [dict(zip(['doc_id', 'company', 'ticker', 'full_name', 'sector', 'year', 'doc_type', 'filing_date', 'pages', 'source', 'ingestion_method', 'ingest_timestamp', 'phase2_timestamp'], row)) for row in docs],
                })
            
            # Get section statistics
            sections = self.duckdb_conn.execute("""
                SELECT section_type, COUNT(*) as count
                FROM sections_metadata
                WHERE company = ?
                GROUP BY section_type
                ORDER BY count DESC
            """, [company]).fetchall()
            
            if sections:
                results.append({
                    'type': 'section_statistics',
                    'data': [{'section_type': row[0], 'count': row[1]} for row in sections],
                })
            
            # Get table statistics
            tables = self.duckdb_conn.execute("""
                SELECT table_type, COUNT(*) as count
                FROM tables_metadata
                WHERE company = ?
                GROUP BY table_type
                ORDER BY count DESC
            """, [company]).fetchall()
            
            if tables:
                results.append({
                    'type': 'table_statistics',
                    'data': [{'table_type': row[0], 'count': row[1]} for row in tables],
                })
        
        return results
    
    def retrieve_from_chromadb(self, query: str, filters: Dict = None, top_k: int = None) -> List[Dict]:
        """
        Retrieve semantic results from ChromaDB.
        
        Args:
            query: User query
            filters: Optional filters (company, year, section_type, etc.)
            top_k: Number of results to retrieve
            
        Returns:
            results: List of result dicts with chunks and metadata
        """
        top_k = top_k or RETRIEVAL_CONFIG['top_k']
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode(query).tolist()
        
        # Determine which collection to query
        collection_name = 'all_sections'  # Default
        if filters and 'section_type' in filters:
            section_type = filters['section_type']
            # Find collection for this section type
            for coll_name, config in CHROMADB_COLLECTIONS.items():
                if section_type in config['section_types']:
                    collection_name = coll_name
                    break
        
        # Query collection
        collection = self.chromadb_client.get_collection(collection_name)
        
        # Build where filter
        where_filter = {}
        if filters:
            if 'company' in filters:
                where_filter['company'] = filters['company']
            if 'years' in filters and len(filters['years']) == 1:
                where_filter['year'] = str(filters['years'][0])
            if 'section_type' in filters:
                where_filter['section_type'] = filters['section_type']
        
        # Query
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter if where_filter else None,
        )
        
        # Format results
        formatted_results = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'chunk_id': results['ids'][0][i],
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None,
                    'similarity': 1 - results['distances'][0][i] if 'distances' in results else None,
                })
        
        return formatted_results
    
    def retrieve(self, query: str) -> Dict:
        """
        Main retrieval function that routes query and retrieves results.
        
        Args:
            query: User query
            
        Returns:
            results: Dict with routing info and results from all sources
        """
        # Route query
        routing = route_query(query)
        
        results = {
            'query': query,
            'routing': routing,
            'duckdb_results': [],
            'chromadb_results': [],
        }
        
        # Execute routing plan
        for step in routing['plan']:
            if step['storage'] == 'duckdb':
                duckdb_results = self.retrieve_from_duckdb(query, routing['filters'])
                results['duckdb_results'] = duckdb_results
            
            elif step['storage'] == 'chromadb':
                chromadb_results = self.retrieve_from_chromadb(query, routing['filters'])
                results['chromadb_results'] = chromadb_results
        
        return results
    
    def format_results(self, results: Dict) -> str:
        """
        Format results for display.
        
        Args:
            results: Results dict
            
        Returns:
            formatted: Formatted string
        """
        output = []
        
        output.append(f"Query: {results['query']}")
        output.append(f"Query Type: {results['routing']['query_type']}")
        output.append(f"Storage: {results['routing']['storage']}")
        output.append("")
        
        # DuckDB results
        if results['duckdb_results']:
            output.append("="*80)
            output.append("STRUCTURED DATA (DuckDB)")
            output.append("="*80)
            
            for result in results['duckdb_results']:
                output.append(f"\n{result['type'].upper()}:")
                for item in result['data'][:5]:  # Show first 5
                    output.append(f"  {item}")
        
        # ChromaDB results
        if results['chromadb_results']:
            output.append("\n" + "="*80)
            output.append("SEMANTIC SEARCH (ChromaDB)")
            output.append("="*80)
            
            for i, chunk in enumerate(results['chromadb_results'][:5], 1):  # Show top 5
                output.append(f"\n[{i}] Similarity: {chunk['similarity']:.3f}")
                output.append(f"    Company: {chunk['metadata']['company']}, Year: {chunk['metadata']['year']}")
                output.append(f"    Section: {chunk['metadata']['section_type']}")
                output.append(f"    Text: {chunk['text'][:200]}...")
        
        return "\n".join(output)
    
    def close(self):
        """Close connections."""
        self.duckdb_conn.close()


if __name__ == "__main__":
    # Test retrieval
    pipeline = RetrievalPipeline()
    
    test_queries = [
        "What is AMD's revenue in 2021?",
        "What are Apple's supply chain risks?",
        "Explain Microsoft's cloud strategy",
    ]
    
    print(f"\n{'='*80}")
    print(f"RETRIEVAL PIPELINE TEST")
    print(f"{'='*80}")
    
    for query in test_queries:
        print(f"\n{'─'*80}")
        results = pipeline.retrieve(query)
        formatted = pipeline.format_results(results)
        print(formatted)
    
    pipeline.close()
