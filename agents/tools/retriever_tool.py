"""
Retriever Tool: Fetch data from Neo4j → ChromaDB + DuckDB with citations
Enhanced workflow:
1. Neo4j: Determine company, year, available sections (metadata)
2. ChromaDB: Semantic search within identified sections
3. DuckDB: Numerical financial data
4. Citations: Track document source, section type, year for each result
"""

import duckdb
import chromadb
import json
import os
from typing import Dict, List, Optional
from langchain_core.tools import Tool
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from agents.config import DUCKDB_PATH, CHROMADB_PATH, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE


class EnhancedRetrieverTool:
    """Enhanced retriever with Neo4j → ChromaDB → DuckDB workflow."""
    
    def __init__(self):
        """Initialize all three backends."""
        # Neo4j connection
        self.neo4j_driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        
        # DuckDB connection
        self.duckdb_conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        
        # ChromaDB connection
        self.chromadb_client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
        
        # Embedding model
        self.embedding_model = SentenceTransformer("BAAI/bge-large-en-v1.5")
    
    def __del__(self):
        """Cleanup connections."""
        if hasattr(self, 'neo4j_driver'):
            self.neo4j_driver.close()
        if hasattr(self, 'duckdb_conn'):
            self.duckdb_conn.close()
    
    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 1: NEO4J METADATA LOOKUP
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_toc_from_neo4j(self, company: str, year: int) -> Dict:
        """
        Get table of contents from Neo4j.
        Returns available sections and their metadata for a company/year.
        
        Args:
            company: Company name
            year: Year
            
        Returns:
            TOC dict with sections by type
        """
        with self.neo4j_driver.session(database=NEO4J_DATABASE) as session:
            # Get document info
            doc_result = session.run(
                """
                MATCH (c:Company {name: $company})-[:FILED]->(d:Document {year: $year})
                RETURN d.doc_id AS doc_id, d.doc_type AS doc_type
                LIMIT 1
                """,
                company=company, year=year
            )
            doc_record = doc_result.single()
            
            if not doc_record:
                return {
                    'success': False,
                    'message': f"No document found for {company} {year}",
                }
            
            doc_id = doc_record['doc_id']
            
            # Get all sections
            sections_result = session.run(
                """
                MATCH (d:Document {doc_id: $doc_id})-[:CONTAINS]->(s:Section)
                OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(s)
                RETURN 
                    s.section_id AS section_id,
                    s.section_type AS section_type,
                    s.text_length AS text_length,
                    COUNT(c) AS chunk_count
                ORDER BY s.section_type
                """,
                doc_id=doc_id
            )
            
            sections_by_type = {}
            for record in sections_result:
                section_type = record['section_type']
                if section_type not in sections_by_type:
                    sections_by_type[section_type] = []
                sections_by_type[section_type].append({
                    'section_id': record['section_id'],
                    'chunk_count': record['chunk_count'],
                })
        
        return {
            'success': True,
            'doc_id': doc_id,
            'company': company,
            'year': year,
            'sections_by_type': sections_by_type,
        }
    
    def find_relevant_sections_neo4j(
        self,
        company: str,
        year: int,
        query: str
    ) -> List[Dict]:
        """
        Use Neo4j to find which sections are relevant for this query.
        Maps query keywords to section types.
        
        Args:
            company: Company name
            year: Year
            query: Search query
            
        Returns:
            List of relevant section IDs with types
        """
        # Keyword to section type mapping
        keyword_section_map = {
            'revenue': ['financial_statements', 'mda'],
            'profit': ['financial_statements', 'mda'],
            'margin': ['financial_statements', 'mda'],
            'earnings': ['financial_statements', 'mda'],
            'income': ['financial_statements', 'mda'],
            'cash': ['financial_statements', 'mda'],
            'balance': ['financial_statements'],
            'risk': ['risk_factors'],
            'strategy': ['business_overview', 'mda'],
            'business': ['business_overview', 'mda'],
            'segment': ['financial_statements', 'mda'],
            'product': ['business_overview'],
            'growth': ['mda', 'financial_statements'],
        }
        
        # Find matching section types
        target_sections = set()
        query_lower = query.lower()
        
        for keyword, sections in keyword_section_map.items():
            if keyword in query_lower:
                target_sections.update(sections)
        
        # If no keywords matched, search all sections
        if not target_sections:
            target_sections = {'financial_statements', 'mda', 'business_overview', 'risk_factors'}
        
        # Query sections from Neo4j
        with self.neo4j_driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (co:Company {name: $company})-[:FILED]->(d:Document {year: $year})-[:CONTAINS]->(s:Section)
                WHERE s.section_type IN $section_types
                OPTIONAL MATCH (ch:Chunk)-[:PART_OF]->(s)
                RETURN 
                    d.doc_id AS doc_id,
                    d.doc_type AS doc_type,
                    s.section_id AS section_id,
                    s.section_type AS section_type,
                    COUNT(ch) AS chunk_count
                ORDER BY s.section_type
                """,
                company=company,
                year=year,
                section_types=list(target_sections)
            )
            
            sections = []
            for record in result:
                sections.append({
                    'section_id': record['section_id'],
                    'section_type': record['section_type'],
                    'doc_id': record['doc_id'],
                    'doc_type': record['doc_type'],
                    'chunk_count': record['chunk_count'],
                })
        
        return sections
    
    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 2: CHROMADB SEMANTIC SEARCH (within Neo4j-identified sections)
    # ─────────────────────────────────────────────────────────────────────────
    
    def retrieve_semantic_data(
        self,
        query: str,
        section_ids: List[str],
        top_k: int = 5
    ) -> List[Dict]:
        """
        Search ChromaDB within specific sections (identified by Neo4j).
        Searches across all relevant collections for comprehensive citations.
        """
        query_embedding = self.embedding_model.encode(query).tolist()
        
        # Search across multiple collections for better coverage
        target_collections = ['all_sections', 'financial_statements', 'mda', 'business_overview', 'risk_factors']
        all_results = []
        seen_ids = set()
        
        for col_name in target_collections:
            try:
                collection = self.chromadb_client.get_collection(col_name)
            except:
                continue
            
            if collection.count() == 0:
                continue
            
            # Try filtering by section_id first, fall back to company/year
            try:
                where_filter = {"section_id": {"$in": section_ids}} if section_ids else None
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(top_k, collection.count()),
                    where=where_filter,
                )
            except:
                # If section_id filter fails, skip
                continue
            
            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    chunk_id = results['ids'][0][i]
                    if chunk_id in seen_ids:
                        continue
                    seen_ids.add(chunk_id)
                    metadata = results['metadatas'][0][i]
                    all_results.append({
                        'chunk_id': chunk_id,
                        'text': results['documents'][0][i],
                        'similarity': 1 - results['distances'][0][i] if 'distances' in results else None,
                        'collection': col_name,
                        'citation': {
                            'company': metadata.get('company'),
                            'year': metadata.get('year'),
                            'doc_id': metadata.get('doc_id'),
                            'section_type': metadata.get('section_type'),
                            'section_id': metadata.get('section_id'),
                            'chunk_index': metadata.get('chunk_index'),
                        }
                    })
        
        # Sort by similarity and return top_k
        all_results.sort(key=lambda x: x.get('similarity', 0) or 0, reverse=True)
        return all_results[:top_k]
    
    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 3: DUCKDB NUMERICAL METRICS
    # ─────────────────────────────────────────────────────────────────────────
    
    def retrieve_numerical_data(
        self,
        company: str,
        year: int
    ) -> Dict:
        """
        Get numerical financial data from DuckDB.
        
        Args:
            company: Company name
            year: Year
            
        Returns:
            Financial metrics with proper formatting
        """
        results = {}
        
        try:
            # Try to get metrics from DuckDB
            if hasattr(self.duckdb_conn, 'execute'):
                # Check if tables exist first
                table_info = self.duckdb_conn.execute(
                    "PRAGMA table_info(financial_metrics)"
                ).fetchall()
                
                if table_info:
                    metrics = self.duckdb_conn.execute(
                        """
                        SELECT * FROM financial_metrics 
                        WHERE company = ? AND year = ?
                        """,
                        [company, year]
                    ).fetchall()
                    
                    if metrics:
                        # Format as dict
                        results['financial_metrics'] = metrics
        except:
            # If DuckDB is not available or tables don't exist, return empty
            pass
        
        return results
    
    # ─────────────────────────────────────────────────────────────────────────
    # MAIN RETRIEVAL WORKFLOW
    # ─────────────────────────────────────────────────────────────────────────
    
    def retrieve(self, query: str, company: str, year: int) -> Dict:
        """
        Main retrieval function: Neo4j → ChromaDB → DuckDB with citations.
        
        Args:
            query: User query
            company: Company name
            year: Year
            
        Returns:
            Complete retrieval result with metadata, semantic data, numerical data, and citations
        """
        result = {
            'query': query,
            'company': company,
            'year': year,
            'success': False,
            'message': '',
            'metadata': {},
            'semantic_data': [],
            'numerical_data': {},
            'sources': [],
        }
        
        # STEP 1: Verify company/year in Neo4j and get TOC
        print(f"\n📌 Step 1: Querying Neo4j for {company} {year}...")
        toc = self.get_toc_from_neo4j(company, year)
        
        if not toc.get('success'):
            result['message'] = toc.get('message', 'Neo4j lookup failed')
            return result
        
        result['metadata'] = {
            'doc_id': toc['doc_id'],
            'sections_available': toc['sections_by_type'],
        }
        print(f"   ✅ Found document: {toc['doc_id']}")
        print(f"   ✅ Available sections: {list(toc['sections_by_type'].keys())}")
        
        # STEP 2: Find relevant sections for this query
        print(f"\n📌 Step 2: Finding relevant sections...")
        relevant_sections = self.find_relevant_sections_neo4j(company, year, query)
        section_ids = [s['section_id'] for s in relevant_sections]
        
        # Also get sections from adjacent years (prior-year comparisons)
        for adj_year in [year - 1, year + 1]:
            try:
                adj_sections = self.find_relevant_sections_neo4j(company, adj_year, query)
                for s in adj_sections[:5]:  # Limit to 5 from adjacent years
                    section_ids.append(s['section_id'])
                    relevant_sections.append(s)
            except:
                pass
        
        result['metadata']['relevant_sections'] = relevant_sections
        print(f"   ✅ Found {len(relevant_sections)} relevant sections (including adjacent years)")
        for section in relevant_sections[:3]:
            print(f"      - {section['section_type']}: {section['section_id']}")
        
        # STEP 3: Search ChromaDB — both filtered by section_ids AND broad company search
        if section_ids:
            print(f"\n📌 Step 3: Semantic search in ChromaDB...")
            # Use auto-tuned params if available
            try:
                from evals.feedback_tuner import get_params
                tp = get_params()
                tuned_top_k = tp.get("rerank_top_k", 5)
            except Exception:
                tuned_top_k = 5
            semantic_data = self.retrieve_semantic_data(query, section_ids, top_k=tuned_top_k)
            
            # Also do a broad search by company (catches cross-references in other docs)
            broad_data = self.retrieve_semantic_data(query, [], top_k=3)
            seen = {c['chunk_id'] for c in semantic_data}
            for chunk in broad_data:
                if chunk['chunk_id'] not in seen and chunk['citation'].get('company') == company:
                    semantic_data.append(chunk)
            
            result['semantic_data'] = semantic_data[:8]
            print(f"   ✅ Found {len(result['semantic_data'])} relevant chunks")
            
            # Collect sources with doc_id for proper multi-file citations
            for chunk in result['semantic_data']:
                source = chunk['citation']
                doc_id = source.get('doc_id', 'unknown')
                source_str = f"{source.get('company')} {source.get('year')} - {source.get('section_type')} [{doc_id}]"
                if source_str not in result['sources']:
                    result['sources'].append(source_str)
        
        # STEP 4: Get numerical data
        print(f"\n📌 Step 4: Fetching numerical data from DuckDB...")
        numerical_data = self.retrieve_numerical_data(company, year)
        result['numerical_data'] = numerical_data
        if numerical_data:
            print(f"   ✅ Found financial metrics")
        else:
            print(f"   ℹ️  No numerical data available in DuckDB")
        
        result['success'] = True
        result['message'] = f"Successfully retrieved data for {company} {year}"
        
        return result


def create_retriever_tool() -> Tool:
    """Create LangChain tool for enhanced retriever."""
    retriever = EnhancedRetrieverTool()
    
    def retrieve_wrapper(input_str: str) -> str:
        """
        Wrapper for LangChain tool.
        Input: JSON string with query, company, year
        """
        try:
            input_dict = json.loads(input_str)
        except:
            input_dict = {}
        
        query = input_dict.get('query', input_str)
        company = input_dict.get('company')
        year = input_dict.get('year')
        
        if not company or not year:
            return "❌ Error: 'company' and 'year' are required parameters"
        
        # Retrieve
        results = retriever.retrieve(query, company, year)
        
        # Format output
        output = f"Query: {results['query']}\n"
        output += f"Company: {results['company']}, Year: {results['year']}\n\n"
        
        if not results['success']:
            output += f"❌ {results['message']}\n"
            return output
        
        output += f"✅ {results['message']}\n\n"
        
        # Metadata
        if results['metadata']:
            output += "📋 METADATA (from Neo4j):\n"
            output += f"  Document ID: {results['metadata'].get('doc_id')}\n"
            output += f"  Available Sections: {list(results['metadata'].get('sections_available', {}).keys())}\n"
            output += f"  Relevant Sections: {len(results['metadata'].get('relevant_sections', []))}\n\n"
        
        # Semantic data
        if results['semantic_data']:
            output += f"📄 SEMANTIC DATA (from ChromaDB):\n"
            for i, chunk in enumerate(results['semantic_data'][:3], 1):
                citation = chunk['citation']
                output += f"\n  [{i}] Similarity: {chunk['similarity']:.3f}\n"
                output += f"      Section: {citation['section_type']} ({citation['section_id']})\n"
                output += f"      Text: {chunk['text'][:150]}...\n"
        
        # Numerical data
        if results['numerical_data']:
            output += f"\n💰 NUMERICAL DATA (from DuckDB):\n"
            output += f"  {json.dumps(results['numerical_data'], indent=2)}\n"
        
        # Sources
        if results['sources']:
            output += f"\n📌 SOURCES:\n"
            for source in results['sources']:
                output += f"  - {source}\n"
        
        return output
    
    return Tool(
        name="financial_data_retriever",
        description="""Enhanced retrieval tool using Neo4j → ChromaDB → DuckDB workflow.
        
Input should be a JSON string with:
- 'query': The search query (required)
- 'company': Company name (required) 
- 'year': Year (required)

Example: {"query": "What is AMD revenue?", "company": "AMD", "year": 2021}

Workflow:
1. Neo4j: Verify company/year and get available sections (TOC)
2. Identify relevant sections based on query keywords
3. ChromaDB: Semantic search within identified sections
4. DuckDB: Retrieve numerical financial data
5. Return all results with proper citations and source tracking
        """,
        func=retrieve_wrapper,
    )


if __name__ == "__main__":
    # Test the enhanced retriever
    print("\n" + "="*80)
    print("ENHANCED RETRIEVER TEST")
    print("="*80)
    
    tool = create_retriever_tool()
    
    test_input = '{"query": "What is AMD revenue and profit?", "company": "AMD", "year": 2021}'
    result = tool.run(test_input)
    
    print("\n" + result)



if __name__ == "__main__":
    # Test retriever
    tool = create_retriever_tool()
    
    test_input = '{"query": "What is AMD revenue?", "filters": {"company": "AMD", "year": 2021}}'
    result = tool.run(test_input)
    
    print(result)
