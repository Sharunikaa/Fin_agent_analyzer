"""
Query Router: Route queries to appropriate storage (DuckDB, ChromaDB, or both)
"""

import re
from typing import Dict, List, Tuple
from config import QUERY_PATTERNS


def classify_query(query: str) -> Dict:
    """
    Classify a query as structured, semantic, or hybrid.
    
    Args:
        query: User query
        
    Returns:
        classification: Dict with query_type, storage, and matched_keywords
    """
    query_lower = query.lower()
    
    # Count keyword matches for each type
    scores = {}
    matched_keywords = {}
    
    for query_type, config in QUERY_PATTERNS.items():
        keywords = config['keywords']
        matches = [kw for kw in keywords if kw in query_lower]
        scores[query_type] = len(matches)
        matched_keywords[query_type] = matches
    
    # Determine query type based on highest score
    if scores['structured'] > 0 and scores['semantic'] > 0:
        query_type = 'hybrid'
    elif scores['structured'] > scores['semantic']:
        query_type = 'structured'
    elif scores['semantic'] > 0:
        query_type = 'semantic'
    else:
        # Default to semantic if no keywords match
        query_type = 'semantic'
    
    storage = QUERY_PATTERNS[query_type]['storage']
    
    return {
        'query_type': query_type,
        'storage': storage,
        'scores': scores,
        'matched_keywords': matched_keywords[query_type],
    }


def extract_filters(query: str) -> Dict:
    """
    Extract filters from query (company, year, section type, etc.).
    
    Args:
        query: User query
        
    Returns:
        filters: Dict with extracted filters
    """
    filters = {}
    
    # Extract company names (simple pattern)
    companies = ['AMD', 'APPLE', 'MICROSOFT', 'NETFLIX', 'INTEL', 'NVIDIA']
    for company in companies:
        if company.lower() in query.lower():
            filters['company'] = company
            break
    
    # Extract years
    year_pattern = r'\b(20\d{2})\b'
    years = re.findall(year_pattern, query)
    if years:
        filters['years'] = [int(y) for y in years]
    
    # Extract year ranges
    range_pattern = r'\b(20\d{2})\s*-\s*(20\d{2})\b'
    year_ranges = re.findall(range_pattern, query)
    if year_ranges:
        start_year, end_year = year_ranges[0]
        filters['year_range'] = (int(start_year), int(end_year))
    
    # Extract section types
    section_keywords = {
        'risk': 'risk_factors',
        'business': 'business_overview',
        'md&a': 'mda',
        'management discussion': 'mda',
        'financial statement': 'financial_statements',
        'segment': 'segment_breakdown',
    }
    
    for keyword, section_type in section_keywords.items():
        if keyword in query.lower():
            filters['section_type'] = section_type
            break
    
    return filters


def route_query(query: str) -> Dict:
    """
    Route a query to appropriate storage with filters.
    
    Args:
        query: User query
        
    Returns:
        routing: Dict with query_type, storage, filters, and routing plan
    """
    # Classify query
    classification = classify_query(query)
    
    # Extract filters
    filters = extract_filters(query)
    
    # Create routing plan
    routing = {
        'query': query,
        'query_type': classification['query_type'],
        'storage': classification['storage'],
        'filters': filters,
        'matched_keywords': classification['matched_keywords'],
        'plan': [],
    }
    
    # Generate routing plan
    if classification['storage'] == 'duckdb':
        routing['plan'].append({
            'step': 1,
            'action': 'Query DuckDB for structured data',
            'storage': 'duckdb',
            'filters': filters,
        })
    
    elif classification['storage'] == 'chromadb':
        routing['plan'].append({
            'step': 1,
            'action': 'Query ChromaDB for semantic search',
            'storage': 'chromadb',
            'filters': filters,
        })
    
    elif classification['storage'] == 'both':
        routing['plan'].append({
            'step': 1,
            'action': 'Query DuckDB for structured data',
            'storage': 'duckdb',
            'filters': filters,
        })
        routing['plan'].append({
            'step': 2,
            'action': 'Query ChromaDB for narrative context',
            'storage': 'chromadb',
            'filters': filters,
        })
    
    return routing


def explain_routing(routing: Dict) -> str:
    """
    Generate human-readable explanation of routing decision.
    
    Args:
        routing: Routing dict
        
    Returns:
        explanation: Human-readable explanation
    """
    query_type = routing['query_type']
    storage = routing['storage']
    matched_keywords = routing['matched_keywords']
    filters = routing['filters']
    
    explanation = f"Query Type: {query_type.upper()}\n"
    explanation += f"Storage: {storage.upper()}\n"
    
    if matched_keywords:
        explanation += f"Matched Keywords: {', '.join(matched_keywords)}\n"
    
    if filters:
        explanation += f"Filters:\n"
        for key, value in filters.items():
            explanation += f"  - {key}: {value}\n"
    
    explanation += f"\nRouting Plan:\n"
    for step in routing['plan']:
        explanation += f"  {step['step']}. {step['action']} ({step['storage']})\n"
    
    return explanation


if __name__ == "__main__":
    # Test queries
    test_queries = [
        "What is AMD's revenue in 2021?",
        "Show me AMD revenue trend from 2019 to 2023",
        "What are Apple's supply chain risks?",
        "Explain Microsoft's cloud strategy",
        "Compare AMD vs Intel gross margin",
        "How did Netflix's revenue growth impact their market position?",
    ]
    
    print(f"\n{'='*80}")
    print(f"QUERY ROUTER TEST")
    print(f"{'='*80}")
    
    for query in test_queries:
        print(f"\n{'─'*80}")
        print(f"Query: {query}")
        print(f"{'─'*80}")
        
        routing = route_query(query)
        explanation = explain_routing(routing)
        
        print(explanation)
