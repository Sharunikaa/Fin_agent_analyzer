"""
Neo4j Tool: Query knowledge graph for metadata and relationships
- Companies, years, documents
- Table of contents (sections)
- Section hierarchies and references
"""

import os
from typing import Dict, List, Optional
from neo4j import GraphDatabase
from langchain_core.tools import Tool
from dotenv import load_dotenv
from pathlib import Path

# Load env vars
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "asdfghjkl")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "hyperverge-base")


class Neo4jMetadataTool:
    """Tool for querying Neo4j knowledge graph."""
    
    def __init__(self):
        """Initialize Neo4j connection."""
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
    
    def __del__(self):
        """Close driver on cleanup."""
        if hasattr(self, 'driver'):
            self.driver.close()
    
    def get_companies(self) -> List[str]:
        """
        Get all companies in the knowledge graph.
        
        Returns:
            List of company names
        """
        with self.driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (c:Company)
                RETURN DISTINCT c.name AS company
                ORDER BY c.name
                """
            )
            companies = [record['company'] for record in result]
        return companies
    
    def get_years_for_company(self, company: str) -> List[int]:
        """
        Get all available years for a company.
        
        Args:
            company: Company name (e.g., "AMD")
            
        Returns:
            Sorted list of years
        """
        with self.driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (:Company {name: $company})-[:FILED]->(d:Document)
                RETURN DISTINCT d.year AS year
                ORDER BY d.year DESC
                """,
                company=company
            )
            years = sorted([record['year'] for record in result], reverse=True)
        return years
    
    def get_toc(self, company: str, year: int) -> Dict:
        """
        Get table of contents: sections available for a company/year.
        
        This is the metadata lookup before search. Returns:
        - Document info
        - Sections (categorized by type)
        - Section relationships
        
        Args:
            company: Company name
            year: Year
            
        Returns:
            Table of contents dict
        """
        with self.driver.session(database=NEO4J_DATABASE) as session:
            # Get document
            doc_result = session.run(
                """
                MATCH (c:Company {name: $company})-[:FILED]->(d:Document {year: $year})
                RETURN d.doc_id AS doc_id, d.doc_type AS doc_type, d.year AS year, d.company AS company
                LIMIT 1
                """,
                company=company, year=year
            )
            doc_record = doc_result.single()
            
            if not doc_record:
                return {
                    'success': False,
                    'message': f"No document found for {company} in {year}"
                }
            
            doc_id = doc_record['doc_id']
            
            # Get sections grouped by type
            sections_result = session.run(
                """
                MATCH (d:Document {doc_id: $doc_id})-[:CONTAINS]->(s:Section)
                OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(s)
                RETURN 
                    s.section_type AS section_type,
                    s.section_id AS section_id,
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
                    'section_type': section_type,
                    'text_length': record['text_length'],
                    'chunk_count': record['chunk_count'],
                })
        
        return {
            'success': True,
            'document': {
                'doc_id': doc_id,
                'company': company,
                'year': year,
                'doc_type': doc_record['doc_type'],
            },
            'sections_by_type': sections_by_type,
            'total_sections': sum(len(v) for v in sections_by_type.values()),
        }
    
    def find_relevant_sections(
        self,
        company: str,
        year: int,
        query: str,
        section_keywords: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Find sections relevant to a query for a company/year.
        
        Matches on section_type keywords or section_id patterns.
        Examples:
        - "revenue" → financial_statements
        - "risk" → risk_factors
        - "management discussion" → mda
        - "business overview" → business_overview
        
        Args:
            company: Company name
            year: Year
            query: Search query to understand context
            section_keywords: Optional list of section types to focus on
            
        Returns:
            List of relevant sections with doc_id and metadata
        """
        # Map query keywords to section types
        keyword_map = {
            'revenue': ['financial_statements', 'mda'],
            'profit': ['financial_statements', 'mda'],
            'margin': ['financial_statements', 'mda'],
            'earnings': ['financial_statements', 'mda'],
            'income': ['financial_statements', 'mda'],
            'cash flow': ['financial_statements', 'mda'],
            'balance sheet': ['financial_statements'],
            'risk': ['risk_factors'],
            'strategy': ['business_overview', 'mda'],
            'business': ['business_overview', 'mda'],
            'segment': ['financial_statements', 'mda'],
            'product': ['business_overview'],
            'competitive': ['business_overview'],
            'management': ['mda'],
            'outlook': ['mda'],
            'growth': ['mda', 'financial_statements'],
        }
        
        # Determine relevant section types
        target_sections = set()
        query_lower = query.lower()
        
        for keyword, sections in keyword_map.items():
            if keyword in query_lower:
                target_sections.update(sections)
        
        # If no keywords match, use all sections
        if not target_sections:
            target_sections = {'financial_statements', 'mda', 'business_overview', 'risk_factors'}
        
        # Override with explicit keywords if provided
        if section_keywords:
            target_sections = set(section_keywords)
        
        with self.driver.session(database=NEO4J_DATABASE) as session:
            # Get document and its sections
            result = session.run(
                """
                MATCH (co:Company {name: $company})-[:FILED]->(d:Document {year: $year})-[:CONTAINS]->(s:Section)
                WHERE s.section_type IN $section_types
                OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(s)
                RETURN 
                    d.doc_id AS doc_id,
                    d.doc_type AS doc_type,
                    s.section_id AS section_id,
                    s.section_type AS section_type,
                    s.text_length AS text_length,
                    COUNT(c) AS chunk_count
                ORDER BY s.section_type, s.section_id
                """,
                company=company,
                year=year,
                section_types=list(target_sections)
            )
            
            sections = []
            for record in result:
                sections.append({
                    'doc_id': record['doc_id'],
                    'doc_type': record['doc_type'],
                    'section_id': record['section_id'],
                    'section_type': record['section_type'],
                    'text_length': record['text_length'],
                    'chunk_count': record['chunk_count'],
                })
        
        return {
            'company': company,
            'year': year,
            'target_sections': list(target_sections),
            'sections_found': sections,
            'count': len(sections),
        }
    
    def get_section_chunks(
        self,
        section_id: str,
        limit: int = 100
    ) -> Dict:
        """
        Get chunk IDs for a section (for ChromaDB lookup).
        
        Args:
            section_id: Section ID
            limit: Max chunks to return
            
        Returns:
            Section metadata + chunk IDs
        """
        with self.driver.session(database=NEO4J_DATABASE) as session:
            # Get section metadata
            section_result = session.run(
                """
                MATCH (s:Section {section_id: $section_id})
                RETURN 
                    s.company AS company,
                    s.year AS year,
                    s.section_type AS section_type,
                    s.text_length AS text_length
                LIMIT 1
                """,
                section_id=section_id
            )
            section_record = section_result.single()
            
            if not section_record:
                return {'success': False, 'message': f"Section not found: {section_id}"}
            
            # Get chunks
            chunks_result = session.run(
                """
                MATCH (c:Chunk)-[:PART_OF]->(s:Section {section_id: $section_id})
                RETURN c.chunk_id AS chunk_id, c.chunk_index AS chunk_index
                ORDER BY c.chunk_index
                LIMIT $limit
                """,
                section_id=section_id,
                limit=limit
            )
            
            chunks = [record['chunk_id'] for record in chunks_result]
        
        return {
            'success': True,
            'section_metadata': {
                'section_id': section_id,
                'company': section_record['company'],
                'year': section_record['year'],
                'section_type': section_record['section_type'],
                'text_length': section_record['text_length'],
            },
            'chunk_ids': chunks,
            'chunk_count': len(chunks),
        }
    
    def get_multi_year_sections(
        self,
        company: str,
        start_year: int,
        end_year: int,
        section_type: Optional[str] = None
    ) -> Dict:
        """
        Get sections across multiple years for trend analysis.
        
        Args:
            company: Company name
            start_year: Start year
            end_year: End year
            section_type: Optional section type filter (e.g., "financial_statements")
            
        Returns:
            Sections organized by year
        """
        with self.driver.session(database=NEO4J_DATABASE) as session:
            query = """
            MATCH (co:Company {name: $company})-[:FILED]->(d:Document)-[:CONTAINS]->(s:Section)
            WHERE d.year >= $start_year AND d.year <= $end_year
            """
            
            if section_type:
                query += "AND s.section_type = $section_type "
            
            query += """
            OPTIONAL MATCH (c:Chunk)-[:PART_OF]->(s)
            RETURN 
                d.year AS year,
                d.doc_id AS doc_id,
                d.doc_type AS doc_type,
                s.section_id AS section_id,
                s.section_type AS section_type,
                COUNT(c) AS chunk_count
            ORDER BY d.year DESC, s.section_type
            """
            
            params = {
                'company': company,
                'start_year': start_year,
                'end_year': end_year,
            }
            if section_type:
                params['section_type'] = section_type
            
            result = session.run(query, params)
            
            sections_by_year = {}
            for record in result:
                year = record['year']
                if year not in sections_by_year:
                    sections_by_year[year] = {
                        'doc_id': record['doc_id'],
                        'doc_type': record['doc_type'],
                        'sections': []
                    }
                
                sections_by_year[year]['sections'].append({
                    'section_id': record['section_id'],
                    'section_type': record['section_type'],
                    'chunk_count': record['chunk_count'],
                })
        
        return {
            'company': company,
            'year_range': f"{start_year} - {end_year}",
            'section_type': section_type or 'all',
            'sections_by_year': sections_by_year,
            'years_found': len(sections_by_year),
        }


def create_neo4j_tool() -> Tool:
    """Create a LangChain tool for Neo4j queries."""
    neo4j_tool = Neo4jMetadataTool()

    def _truncate(s, max_chars=3000):
        s = str(s)
        return s[:max_chars] + f"\n...[truncated, {len(s)} chars total]" if len(s) > max_chars else s

    def run(input_str: str) -> str:
        """Run Neo4j queries. Input is JSON with 'action' and params."""
        import json as _json
        try:
            params = _json.loads(input_str)
        except:
            params = {"action": input_str.strip()}

        action = params.get("action", "")

        if action == "get_companies":
            return _truncate(neo4j_tool.get_companies())
        elif action == "get_years":
            return _truncate(neo4j_tool.get_years_for_company(params.get("company")))
        elif action == "get_toc":
            result = neo4j_tool.get_toc(params.get("company"), params.get("year"))
            if isinstance(result, dict) and 'sections_by_type' in result:
                summary = {k: len(v) for k, v in result['sections_by_type'].items()}
                return _truncate({'doc_id': result.get('document', {}).get('doc_id'),
                                  'total_sections': result.get('total_sections'),
                                  'sections_count_by_type': summary})
            return _truncate(result)
        elif action == "find_sections":
            result = neo4j_tool.find_relevant_sections(
                params.get("company"), params.get("year"),
                params.get("query"), params.get("section_keywords"))
            if isinstance(result, dict) and 'sections_found' in result:
                result['sections_found'] = result['sections_found'][:10]
                result['note'] = f"Showing first 10 of {result.get('count', '?')} sections"
            return _truncate(result)
        elif action == "get_chunks":
            return _truncate(neo4j_tool.get_section_chunks(
                params.get("section_id"), params.get("limit", 20)))
        elif action == "get_multi_year":
            result = neo4j_tool.get_multi_year_sections(
                params.get("company"), params.get("start_year"),
                params.get("end_year"), params.get("section_type"))
            if isinstance(result, dict) and 'sections_by_year' in result:
                summary = {}
                for yr, info in result['sections_by_year'].items():
                    types = {}
                    for s in info.get('sections', []):
                        types[s.get('section_type', 'unknown')] = types.get(s.get('section_type', 'unknown'), 0) + 1
                    summary[yr] = {'doc_id': info.get('doc_id'), 'section_counts': types}
                result['sections_by_year'] = summary
            return _truncate(result)
        else:
            return f"Error: Unknown action '{action}'. Use: get_companies, get_years, get_toc, find_sections, get_chunks, get_multi_year"

    return Tool(
        name="neo4j_metadata",
        description="""Query Neo4j knowledge graph. Input must be JSON with 'action' and parameters.

Actions:
- {"action": "get_companies"}
- {"action": "get_years", "company": "AMD"}
- {"action": "get_toc", "company": "AMD", "year": 2021}
- {"action": "find_sections", "company": "AMD", "year": 2021, "query": "revenue"}
- {"action": "get_chunks", "section_id": "..."}
- {"action": "get_multi_year", "company": "AMD", "start_year": 2019, "end_year": 2022}""",
        func=run,
    )


if __name__ == "__main__":
    # Test the tool
    print("\n" + "="*80)
    print("NEO4J METADATA TOOL TEST")
    print("="*80 + "\n")
    
    tool = Neo4jMetadataTool()
    
    # Test 1: Get companies
    print("📌 Test 1: Available Companies")
    companies = tool.get_companies()
    print(f"   Companies: {companies}\n")
    
    if companies:
        company = companies[0]
        
        # Test 2: Get years
        print(f"📌 Test 2: Years for {company}")
        years = tool.get_years_for_company(company)
        print(f"   Years: {years}\n")
        
        if years:
            year = years[0]
            
            # Test 3: Get TOC
            print(f"📌 Test 3: Table of Contents for {company} {year}")
            toc = tool.get_toc(company, year)
            print(f"   Result: {toc}\n")
            
            # Test 4: Find sections
            print(f"📌 Test 4: Find Sections (query='revenue')")
            sections = tool.find_relevant_sections(company, year, "What is revenue?")
            print(f"   Found {sections['count']} sections: {sections}\n")
