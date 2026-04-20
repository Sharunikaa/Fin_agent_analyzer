"""
Financial KPI extraction from tables.
Extracts revenue, profit, margins, R&D, etc. from financial statement tables.
"""

import re
from typing import Dict, List, Optional, Tuple
from rapidfuzz import fuzz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# KPI field mappings (fuzzy matching)
KPI_MAPPINGS = {
    "total_revenue": [
        "total revenue", "total net revenue", "net revenue", "revenues", "total revenues",
        "net sales", "total net sales", "sales"
    ],
    "gross_profit": [
        "gross profit", "gross income", "gross margin dollars"
    ],
    "operating_income": [
        "operating income", "income from operations", "operating profit",
        "operating earnings"
    ],
    "net_income": [
        "net income", "net earnings", "net profit", "net income attributable",
        "income attributable to"
    ],
    "r_and_d": [
        "research and development", "r&d", "r & d", "research & development",
        "r and d expenses"
    ],
    "total_assets": [
        "total assets", "total consolidated assets"
    ],
    "total_liabilities": [
        "total liabilities", "total consolidated liabilities"
    ],
    "total_equity": [
        "total equity", "total stockholders' equity", "shareholders' equity",
        "total shareholders equity", "stockholders equity"
    ],
    "cash_and_equivalents": [
        "cash and cash equivalents", "cash and equivalents", "cash & cash equivalents"
    ],
    "total_debt": [
        "total debt", "long-term debt", "total borrowings"
    ],
}


def normalize_financial_value(value_str: str) -> Optional[float]:
    """
    Convert financial string to float.
    Handles formats like: "$5,234", "(123)", "5.2B", "1,234M", etc.
    
    Returns:
        Float value in millions, or None if can't parse
    """
    if not value_str or not isinstance(value_str, str):
        return None
    
    # Remove whitespace
    value_str = value_str.strip()
    
    if not value_str or value_str in ["-", "—", "n/a", "N/A", ""]:
        return None
    
    # Check for parentheses (negative number)
    is_negative = False
    if value_str.startswith("(") and value_str.endswith(")"):
        is_negative = True
        value_str = value_str[1:-1]
    
    # Remove currency symbols and commas
    value_str = re.sub(r'[$€£¥,]', '', value_str)
    
    # Check for multipliers (B = billions, M = millions)
    multiplier = 1
    if value_str.endswith('B') or value_str.endswith('b'):
        multiplier = 1000  # Convert to millions
        value_str = value_str[:-1]
    elif value_str.endswith('M') or value_str.endswith('m'):
        multiplier = 1
        value_str = value_str[:-1]
    
    # Try to parse as float
    try:
        value = float(value_str) * multiplier
        if is_negative:
            value = -value
        return value
    except ValueError:
        return None


def fuzzy_match_column(column_name: str, target_keywords: List[str], threshold: int = 75) -> bool:
    """
    Check if column name matches any of the target keywords using fuzzy matching.
    """
    column_lower = column_name.lower().strip()
    
    for keyword in target_keywords:
        score = fuzz.partial_ratio(column_lower, keyword.lower())
        if score >= threshold:
            return True
    
    return False


def find_kpi_in_table(table: Dict, kpi_name: str, kpi_keywords: List[str]) -> Optional[float]:
    """
    Find a KPI value in a table by searching rows.
    
    Args:
        table: Table dict with headers and rows
        kpi_name: Name of KPI (e.g., "total_revenue")
        kpi_keywords: List of possible row labels
    
    Returns:
        KPI value (in millions) or None
    """
    rows = table.get("rows", [])
    if not rows:
        return None
    
    # Get the first column name (usually the label column)
    headers = table.get("headers", [])
    if not headers:
        return None
    
    label_column = headers[0]
    
    # Find the most recent year column (usually last numeric column)
    value_columns = [h for h in headers[1:] if h and not h.lower().startswith("note")]
    if not value_columns:
        return None
    
    # Use the last column (most recent year)
    value_column = value_columns[-1]
    
    # Search for KPI in rows
    for row in rows:
        label = str(row.get(label_column, "")).lower().strip()
        
        # Check if this row matches any keyword
        for keyword in kpi_keywords:
            if fuzz.partial_ratio(label, keyword.lower()) >= 75:
                # Found matching row, extract value
                value_str = row.get(value_column, "")
                value = normalize_financial_value(str(value_str))
                
                if value is not None:
                    logger.debug(f"Found {kpi_name}: {value}M (matched '{label}' with '{keyword}')")
                    return value
    
    return None


def extract_kpis_from_tables(tables: List[Dict], table_type: str = None) -> Dict[str, Optional[float]]:
    """
    Extract all KPIs from a list of tables.
    
    Args:
        tables: List of table dicts
        table_type: Optional filter (income_statement, balance_sheet, etc.)
    
    Returns:
        {
            "total_revenue": 16400.0,  # in millions
            "gross_profit": 10300.0,
            "net_income": 3200.0,
            ...
        }
    """
    kpis = {kpi: None for kpi in KPI_MAPPINGS.keys()}
    
    # Filter tables by type if specified
    if table_type:
        tables = [t for t in tables if t.get("table_type") == table_type or t.get("section_type") == table_type]
    
    if not tables:
        logger.warning(f"No tables found for type: {table_type}")
        return kpis
    
    logger.info(f"Extracting KPIs from {len(tables)} tables...")
    
    # Try to find each KPI
    for kpi_name, keywords in KPI_MAPPINGS.items():
        for table in tables:
            value = find_kpi_in_table(table, kpi_name, keywords)
            if value is not None:
                kpis[kpi_name] = value
                break  # Found it, move to next KPI
    
    # Calculate derived metrics
    if kpis["total_revenue"] and kpis["gross_profit"]:
        kpis["gross_margin_pct"] = (kpis["gross_profit"] / kpis["total_revenue"]) * 100
    else:
        kpis["gross_margin_pct"] = None
    
    if kpis["total_revenue"] and kpis["operating_income"]:
        kpis["operating_margin_pct"] = (kpis["operating_income"] / kpis["total_revenue"]) * 100
    else:
        kpis["operating_margin_pct"] = None
    
    if kpis["total_revenue"] and kpis["net_income"]:
        kpis["net_margin_pct"] = (kpis["net_income"] / kpis["total_revenue"]) * 100
    else:
        kpis["net_margin_pct"] = None
    
    # Log found KPIs
    found_kpis = {k: v for k, v in kpis.items() if v is not None}
    logger.info(f"Extracted {len(found_kpis)} KPIs: {list(found_kpis.keys())}")
    
    return kpis


def extract_segment_revenue(tables: List[Dict]) -> Dict[str, float]:
    """
    Extract revenue by segment (e.g., Data Center, Client, Gaming, Embedded).
    
    Returns:
        {
            "Data Center": 5200.0,
            "Client": 3800.0,
            "Gaming": 2100.0,
            ...
        }
    """
    segment_revenue = {}
    
    # Look for segment tables
    segment_tables = [t for t in tables if t.get("table_type") == "segment_breakdown"]
    
    if not segment_tables:
        # Try to find by keywords in any table
        for table in tables:
            headers = table.get("headers", [])
            headers_text = " ".join([str(h).lower() for h in headers])
            
            if "segment" in headers_text or "product" in headers_text:
                segment_tables.append(table)
    
    if not segment_tables:
        logger.warning("No segment breakdown tables found")
        return segment_revenue
    
    logger.info(f"Extracting segment revenue from {len(segment_tables)} tables...")
    
    for table in segment_tables:
        rows = table.get("rows", [])
        headers = table.get("headers", [])
        
        if not rows or not headers:
            continue
        
        label_column = headers[0]
        value_columns = [h for h in headers[1:] if h]
        
        if not value_columns:
            continue
        
        # Use last column (most recent year)
        value_column = value_columns[-1]
        
        for row in rows:
            label = str(row.get(label_column, "")).strip()
            
            # Skip total/summary rows
            if any(word in label.lower() for word in ["total", "consolidated", "eliminations"]):
                continue
            
            value_str = row.get(value_column, "")
            value = normalize_financial_value(str(value_str))
            
            if value is not None and label:
                segment_revenue[label] = value
    
    logger.info(f"Found {len(segment_revenue)} segments: {list(segment_revenue.keys())}")
    
    return segment_revenue


def extract_all_kpis(extraction_results: Dict) -> Dict:
    """
    Extract all KPIs from full extraction results.
    
    Args:
        extraction_results: Output from extract_pdf.extract_pdf_full()
    
    Returns:
        {
            "metadata": {...},
            "kpis": {
                "total_revenue": 16400.0,
                ...
            },
            "segment_revenue": {
                "Data Center": 5200.0,
                ...
            }
        }
    """
    # Collect all tables
    all_tables = []
    for page in extraction_results.get("pages", []):
        all_tables.extend(page.get("tables", []))
    
    # Extract KPIs
    kpis = extract_kpis_from_tables(all_tables)
    
    # Extract segment revenue
    segment_revenue = extract_segment_revenue(all_tables)
    
    return {
        "metadata": extraction_results["metadata"],
        "kpis": kpis,
        "segment_revenue": segment_revenue,
        "num_tables_analyzed": len(all_tables)
    }


# Test function
if __name__ == "__main__":
    # Test value normalization
    test_values = [
        ("$5,234", 5234.0),
        ("(123)", -123.0),
        ("5.2B", 5200.0),
        ("1,234M", 1234.0),
        ("$16,434", 16434.0),
        ("-", None),
    ]
    
    print("Testing value normalization...\n")
    for input_val, expected in test_values:
        result = normalize_financial_value(input_val)
        status = "✅" if result == expected else "❌"
        print(f"{status} Input: {input_val:15s} Expected: {expected} Got: {result}")
