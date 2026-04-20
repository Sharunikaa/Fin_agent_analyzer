"""
Table Classification: Classify tables by financial statement type
"""

import re
from typing import Dict, List
from config import TABLE_TYPES


def classify_table(table: Dict) -> str:
    """
    Classify a table into one of 5 types.
    
    Args:
        table: Table dict with 'headers', 'rows', 'caption'
        
    Returns:
        table_type: One of income_statement, balance_sheet, cashflow_statement, segment_breakdown, other
    """
    # Combine headers and caption for classification
    headers = table.get('headers', [])
    caption = table.get('caption', '')
    rows = table.get('rows', [])
    
    # Convert to lowercase text
    headers_text = ' '.join([str(h).lower() for h in headers])
    caption_text = caption.lower() if caption else ''
    combined_text = f"{headers_text} {caption_text}"
    
    # Also check first column (row labels)
    row_labels = []
    if rows:
        for row in rows[:10]:  # Check first 10 rows
            if isinstance(row, dict):
                # Get first value (usually the label)
                first_key = list(row.keys())[0] if row.keys() else None
                if first_key:
                    row_labels.append(str(row[first_key]).lower())
    
    row_labels_text = ' '.join(row_labels)
    combined_text += ' ' + row_labels_text
    
    # Check each table type
    for table_type, config in TABLE_TYPES.items():
        if table_type == 'other':
            continue
        
        keywords = config.get('keywords', [])
        required_keywords = config.get('required_keywords', [])
        
        # Check required keywords
        if required_keywords:
            if all(kw in combined_text for kw in required_keywords):
                return table_type
        
        # Check regular keywords (at least 2 matches)
        matches = sum(1 for kw in keywords if kw in combined_text)
        if matches >= 2:
            return table_type
    
    return "other"


def classify_all_tables(tables: List[Dict]) -> List[Dict]:
    """
    Classify all tables in a document.
    
    Args:
        tables: List of table dicts
        
    Returns:
        classified_tables: Tables with 'table_type' and 'storage_destination' fields added
    """
    classified_tables = []
    
    for table in tables:
        table_type = classify_table(table)
        storage = TABLE_TYPES[table_type]['storage']
        
        table['table_type'] = table_type
        table['storage_destination'] = storage
        
        classified_tables.append(table)
    
    return classified_tables


def get_table_statistics(classified_tables: List[Dict]) -> Dict:
    """
    Get statistics on table classification.
    
    Args:
        classified_tables: Tables with 'table_type' field
        
    Returns:
        stats: Dict with counts and percentages
    """
    from collections import Counter
    
    table_types = [t['table_type'] for t in classified_tables]
    counts = Counter(table_types)
    total = len(table_types)
    
    stats = {
        'total_tables': total,
        'counts': dict(counts),
        'percentages': {k: (v / total) * 100 for k, v in counts.items()},
        'storage_routing': {
            'duckdb': sum(1 for t in classified_tables if t['storage_destination'] == 'duckdb'),
            'chromadb': sum(1 for t in classified_tables if t['storage_destination'] == 'chromadb'),
        }
    }
    
    return stats


def validate_table_classification(classified_tables: List[Dict]) -> Dict:
    """
    Validate that table classification makes sense.
    
    Args:
        classified_tables: Tables with 'table_type' field
        
    Returns:
        validation: Dict with warnings and issues
    """
    stats = get_table_statistics(classified_tables)
    counts = stats['counts']
    percentages = stats['percentages']
    
    warnings = []
    
    # Check if too many "other"
    if percentages.get('other', 0) > 80:
        warnings.append(f"⚠️  {percentages['other']:.1f}% tables classified as 'other' (>80%)")
    
    # Check if financial tables are present
    financial_types = ['income_statement', 'balance_sheet', 'cashflow_statement']
    for table_type in financial_types:
        if counts.get(table_type, 0) == 0:
            warnings.append(f"⚠️  No '{table_type}' tables found")
    
    return {
        'valid': len(warnings) == 0,
        'warnings': warnings,
        'stats': stats,
    }


if __name__ == "__main__":
    # Test classification
    test_tables = [
        {
            "headers": ["", "2021", "2020", "2019"],
            "caption": "Consolidated Statements of Income",
            "rows": [
                {"Metric": "Revenue", "2021": "16434", "2020": "9763", "2019": "6731"},
                {"Metric": "Cost of revenue", "2021": "8505", "2020": "5427", "2019": "4086"},
            ]
        },
        {
            "headers": ["", "2021", "2020"],
            "caption": "Consolidated Balance Sheets",
            "rows": [
                {"Item": "Total assets", "2021": "12533", "2020": "7675"},
                {"Item": "Total liabilities", "2021": "3920", "2020": "2721"},
            ]
        },
        {
            "headers": ["Segment", "Revenue", "Operating Income"],
            "rows": [
                {"Segment": "Data Center", "Revenue": "6500", "Operating Income": "1200"},
                {"Segment": "Client", "Revenue": "9000", "Operating Income": "1800"},
            ]
        },
    ]
    
    classified = classify_all_tables(test_tables)
    
    print("Table Classification Results:")
    for i, table in enumerate(classified):
        print(f"  Table {i+1}: {table['table_type']:20s} → {table['storage_destination']}")
        print(f"           Caption: {table.get('caption', 'N/A')}")
    
    validation = validate_table_classification(classified)
    print(f"\nValidation: {'✅ Valid' if validation['valid'] else '⚠️  Issues found'}")
    for warning in validation['warnings']:
        print(f"  {warning}")
