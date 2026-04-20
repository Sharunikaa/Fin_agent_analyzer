"""
Section classification for financial documents.
Classifies pages/text into canonical section types.
"""

import re
from typing import Dict, List, Optional
from rapidfuzz import fuzz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Canonical section types
SECTION_TYPES = [
    "cover_page",
    "table_of_contents",
    "ceo_letter",
    "business_overview",
    "risk_factors",
    "mda",  # Management Discussion & Analysis
    "income_statement",
    "balance_sheet",
    "cashflow_statement",
    "segment_breakdown",
    "footnotes",
    "esg",
    "other"
]


# Section detection patterns (regex + keywords)
SECTION_PATTERNS = {
    "cover_page": [
        r"^(united states|securities and exchange commission)",
        r"(form 10-k|form 10-q|annual report)",
        r"(commission file number)",
    ],
    
    "table_of_contents": [
        r"(table of contents|index)",
        r"(part i\s+item|part ii\s+item)",
    ],
    
    "ceo_letter": [
        r"(letter|message).{0,30}(shareholder|stockholder|investor)",
        r"(dear shareholder|dear stockholder)",
        r"(chairman.{0,20}message|ceo.{0,20}letter)",
        r"(to our shareholder|fellow shareholder)",
    ],
    
    "business_overview": [
        r"(item\s*1[^a-z0-9]|item\s*1\s*\.|item\s*1\s*$)",
        r"(business\s*$|our business|business overview)",
        r"(company overview|about.{0,20}company)",
    ],
    
    "risk_factors": [
        r"(item\s*1a|item\s*1\.a)",
        r"(risk factor|principal risk|key risk)",
        r"(risks and uncertainties)",
    ],
    
    "mda": [
        r"(item\s*7[^a-z0-9]|item\s*7\s*\.|item\s*7\s*$)",
        r"(management.{0,30}discussion.{0,30}analysis)",
        r"(md&a|md\s*&\s*a)",
        r"(financial condition and results)",
    ],
    
    "income_statement": [
        r"(consolidated.{0,30}statement.{0,30}(income|operation|earning))",
        r"(statement.{0,30}(income|operation|earning))",
        r"(income statement|statement of income)",
    ],
    
    "balance_sheet": [
        r"(consolidated.{0,30}balance.{0,30}sheet)",
        r"(balance sheet|statement.{0,30}financial position)",
        r"(assets and liabilities)",
    ],
    
    "cashflow_statement": [
        r"(consolidated.{0,30}statement.{0,30}cash flow)",
        r"(cash flow statement|statement.{0,30}cash flow)",
        r"(statement of cash flows)",
    ],
    
    "segment_breakdown": [
        r"(segment.{0,30}(information|result|revenue|breakdown))",
        r"(business segment|reportable segment)",
        r"(geographic.{0,30}information)",
    ],
    
    "footnotes": [
        r"(note\s+\d+|notes to|footnote)",
        r"(consolidated financial statement.{0,30}note)",
        r"(summary of significant accounting)",
    ],
    
    "esg": [
        r"(esg|environmental.{0,30}social.{0,30}governance)",
        r"(sustainability|corporate responsibility)",
        r"(carbon emission|climate change|greenhouse gas)",
        r"(diversity.{0,30}inclusion|dei\s)",
    ],
}


def classify_section_by_text(text: str, page_num: int = None) -> str:
    """
    Classify a text chunk into a section type using regex patterns.
    
    Args:
        text: Text content to classify
        page_num: Optional page number (helps with cover page detection)
    
    Returns:
        section_type: One of SECTION_TYPES
    """
    if not text or len(text.strip()) < 10:
        return "other"
    
    # Normalize text for matching
    text_lower = text.lower()
    text_normalized = re.sub(r'\s+', ' ', text_lower)
    
    # Special case: first few pages are usually cover page
    if page_num is not None and page_num <= 2:
        for pattern in SECTION_PATTERNS["cover_page"]:
            if re.search(pattern, text_normalized, re.IGNORECASE):
                return "cover_page"
    
    # Try each section type
    section_scores = {}
    
    for section_type, patterns in SECTION_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, text_normalized, re.IGNORECASE):
                score += 1
        
        if score > 0:
            section_scores[section_type] = score
    
    # Return section with highest score
    if section_scores:
        best_section = max(section_scores.items(), key=lambda x: x[1])
        return best_section[0]
    
    return "other"


def classify_section_fuzzy(text: str, threshold: int = 70) -> Optional[str]:
    """
    Fallback classifier using fuzzy string matching.
    Useful when regex patterns don't match but text is similar.
    
    Args:
        text: Text to classify
        threshold: Minimum fuzzy match score (0-100)
    
    Returns:
        section_type or None
    """
    if not text or len(text.strip()) < 10:
        return None
    
    # Extract first 200 chars for matching
    text_sample = text[:200].lower()
    
    # Known section headers
    known_headers = {
        "ceo_letter": ["letter to shareholders", "dear shareholders", "message from ceo"],
        "risk_factors": ["risk factors", "item 1a risk factors"],
        "mda": ["management's discussion and analysis", "item 7 md&a"],
        "income_statement": ["consolidated statements of income", "income statement"],
        "balance_sheet": ["consolidated balance sheets", "balance sheet"],
        "cashflow_statement": ["consolidated statements of cash flows", "cash flow statement"],
    }
    
    best_match = None
    best_score = 0
    
    for section_type, headers in known_headers.items():
        for header in headers:
            score = fuzz.partial_ratio(text_sample, header)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = section_type
    
    return best_match


def classify_pages(pages_data: List[Dict]) -> List[Dict]:
    """
    Classify all pages in a document.
    
    Args:
        pages_data: List of page dicts from extract_pdf_full()
    
    Returns:
        pages_data with added "section_type" field
    """
    logger.info(f"Classifying {len(pages_data)} pages...")
    
    for page in pages_data:
        page_num = page["page_num"]
        text = page["text"]
        
        # Primary classification
        section_type = classify_section_by_text(text, page_num)
        
        # Fallback to fuzzy matching if "other"
        if section_type == "other":
            fuzzy_match = classify_section_fuzzy(text)
            if fuzzy_match:
                section_type = fuzzy_match
        
        page["section_type"] = section_type
    
    # Log section distribution
    section_counts = {}
    for page in pages_data:
        section_type = page["section_type"]
        section_counts[section_type] = section_counts.get(section_type, 0) + 1
    
    logger.info("Section distribution:")
    for section_type, count in sorted(section_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {section_type}: {count} pages")
    
    return pages_data


def extract_section_text(pages_data: List[Dict], section_type: str) -> str:
    """
    Extract all text from pages of a specific section type.
    
    Args:
        pages_data: Classified pages
        section_type: Section to extract
    
    Returns:
        Combined text from all pages of that section
    """
    section_pages = [p for p in pages_data if p.get("section_type") == section_type]
    
    if not section_pages:
        return ""
    
    combined_text = "\n\n".join([p["text"] for p in section_pages])
    return combined_text


def extract_all_sections(pages_data: List[Dict]) -> Dict[str, str]:
    """
    Extract text for all section types.
    
    Returns:
        {
            "ceo_letter": "...",
            "risk_factors": "...",
            "mda": "...",
            ...
        }
    """
    sections = {}
    
    for section_type in SECTION_TYPES:
        text = extract_section_text(pages_data, section_type)
        if text:
            sections[section_type] = text
    
    return sections


def detect_financial_tables(pages_data: List[Dict]) -> List[Dict]:
    """
    Identify which tables are financial statements (income, balance, cashflow).
    
    Returns:
        List of table dicts with added "table_type" field
    """
    financial_tables = []
    
    for page in pages_data:
        section_type = page.get("section_type", "other")
        
        # Only look at pages classified as financial statements
        if section_type not in ["income_statement", "balance_sheet", "cashflow_statement"]:
            continue
        
        for table in page.get("tables", []):
            table["table_type"] = section_type
            table["section_type"] = section_type
            financial_tables.append(table)
    
    logger.info(f"Found {len(financial_tables)} financial statement tables")
    
    return financial_tables


def classify_table_by_headers(table: Dict) -> str:
    """
    Classify a table by analyzing its headers.
    Useful for tables on pages that aren't clearly classified.
    
    Returns:
        table_type: income_statement | balance_sheet | cashflow_statement | segment_breakdown | other
    """
    headers = table.get("headers", [])
    headers_lower = [str(h).lower() for h in headers]
    headers_text = " ".join(headers_lower)
    
    # Income statement indicators
    if any(keyword in headers_text for keyword in ["revenue", "net income", "operating income", "gross profit", "earnings"]):
        return "income_statement"
    
    # Balance sheet indicators
    if any(keyword in headers_text for keyword in ["assets", "liabilities", "equity", "stockholders"]):
        return "balance_sheet"
    
    # Cash flow indicators
    if any(keyword in headers_text for keyword in ["cash flow", "operating activities", "investing activities", "financing activities"]):
        return "cashflow_statement"
    
    # Segment breakdown indicators
    if any(keyword in headers_text for keyword in ["segment", "geographic", "region", "product line"]):
        return "segment_breakdown"
    
    return "other"


# Test function
if __name__ == "__main__":
    # Test section classification
    test_texts = [
        ("UNITED STATES SECURITIES AND EXCHANGE COMMISSION Form 10-K", "cover_page"),
        ("Letter to Shareholders\nDear Fellow Shareholders,", "ceo_letter"),
        ("ITEM 1A. RISK FACTORS\nThe following risk factors", "risk_factors"),
        ("ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS", "mda"),
        ("CONSOLIDATED STATEMENTS OF INCOME", "income_statement"),
        ("Environmental, Social and Governance", "esg"),
    ]
    
    print("Testing section classifier...\n")
    for text, expected in test_texts:
        result = classify_section_by_text(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} Expected: {expected:20s} Got: {result:20s}")
        print(f"   Text: {text[:60]}...")
        print()
