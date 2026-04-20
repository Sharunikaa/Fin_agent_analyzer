"""
Core PDF extraction functions.
Extracts text, tables, and metadata from financial PDFs.
"""

import pdfplumber
import subprocess
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_pdf_extractable(pdf_path: str) -> bool:
    """
    Check if PDF has extractable text using pdfinfo.
    Returns True if digital PDF, False if scanned.
    """
    try:
        result = subprocess.run(
            ['pdfinfo', pdf_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Check if encrypted
        if 'Encrypted: yes' in result.stdout:
            logger.warning(f"PDF is encrypted: {pdf_path}")
            return False
        
        # Quick test: try to extract text from first page
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) == 0:
                return False
            
            first_page_text = pdf.pages[0].extract_text() or ""
            # If first page has < 50 chars, likely scanned
            return len(first_page_text.strip()) > 50
            
    except Exception as e:
        logger.error(f"Error checking PDF extractability: {e}")
        return False


def extract_metadata_from_filename(filename: str) -> Dict[str, any]:
    """
    Extract company name and year from filename.
    Examples:
      - AMD_2021_10K.pdf → {company: AMD, year: 2021, doc_type: 10K}
      - APPLE_2022_annualreport.pdf → {company: APPLE, year: 2022, doc_type: annual_report}
    """
    filename = Path(filename).stem  # Remove .pdf extension
    
    # Extract year (4 digits)
    year_match = re.search(r'(\d{4})', filename)
    year = int(year_match.group(1)) if year_match else None
    
    # Extract company name (everything before first underscore or number)
    company_match = re.match(r'^([A-Za-z\s&]+)', filename.replace('_', ' '))
    company = company_match.group(1).strip().upper() if company_match else "UNKNOWN"
    
    # Extract document type
    doc_type = "unknown"
    filename_lower = filename.lower()
    if '10k' in filename_lower or '10-k' in filename_lower:
        doc_type = "10K"
    elif '10q' in filename_lower or '10-q' in filename_lower:
        doc_type = "10Q"
    elif '8k' in filename_lower or '8-k' in filename_lower:
        doc_type = "8K"
    elif 'annual' in filename_lower:
        doc_type = "annual_report"
    elif 'earnings' in filename_lower or 'quarter' in filename_lower:
        doc_type = "earnings"
    
    return {
        "company": company,
        "year": year,
        "doc_type": doc_type,
        "filename": filename
    }


def extract_text_from_page(pdf_path: str, page_num: int) -> Tuple[str, bool]:
    """
    Extract text from a single page.
    Returns: (text, is_chart_page)
    
    If text is too short (< 50 chars), marks as potential chart page.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num >= len(pdf.pages):
                return "", False
            
            page = pdf.pages[page_num]
            text = page.extract_text() or ""
            
            # If text is very short, it's likely a chart/image page
            is_chart_page = len(text.strip()) < 50
            
            return text, is_chart_page
            
    except Exception as e:
        logger.error(f"Error extracting text from page {page_num}: {e}")
        return "", False


def extract_tables_from_page(pdf_path: str, page_num: int) -> List[Dict]:
    """
    Extract tables from a single page using pdfplumber.
    Falls back to camelot if pdfplumber fails.
    
    Returns list of table dicts with:
      - table_id
      - page_num
      - headers
      - rows
      - raw_data (2D array)
    """
    tables_extracted = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num >= len(pdf.pages):
                return []
            
            page = pdf.pages[page_num]
            
            # Try multiple extraction strategies
            strategies = [
                # Strategy 1: Lines strict (for tables with explicit borders)
                {
                    "vertical_strategy": "lines_strict",
                    "horizontal_strategy": "lines_strict",
                    "intersection_tolerance": 3,
                },
                # Strategy 2: Lines (more lenient)
                {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                },
                # Strategy 3: Text-based (for tables without borders)
                {
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "intersection_tolerance": 5,
                },
            ]
            
            for strategy in strategies:
                tables = page.extract_tables(table_settings=strategy)
                
                if tables and len(tables) > 0:
                    for i, table in enumerate(tables):
                        if not table or len(table) < 2:  # Need at least header + 1 row
                            continue
                        
                        # First row is usually headers
                        headers = table[0]
                        rows = table[1:]
                        
                        # Clean headers (remove None, empty strings)
                        headers = [str(h).strip() if h else f"col_{j}" for j, h in enumerate(headers)]
                        
                        # Convert rows to list of dicts
                        rows_dicts = []
                        for row in rows:
                            if not any(row):  # Skip empty rows
                                continue
                            row_dict = {headers[j]: str(cell).strip() if cell else "" 
                                       for j, cell in enumerate(row) if j < len(headers)}
                            rows_dicts.append(row_dict)
                        
                        if len(rows_dicts) > 0:  # Only add if we have data rows
                            tables_extracted.append({
                                "table_id": f"page_{page_num}_table_{i}",
                                "page_num": page_num,
                                "headers": headers,
                                "rows": rows_dicts,
                                "raw_data": table,
                                "extraction_method": "pdfplumber"
                            })
                    
                    # If we found tables, stop trying other strategies
                    if len(tables_extracted) > 0:
                        break
    
    except Exception as e:
        logger.error(f"Error extracting tables from page {page_num}: {e}")
    
    # If pdfplumber found no tables, try camelot as fallback
    if len(tables_extracted) == 0:
        try:
            import camelot
            
            # Try both lattice and stream flavors
            for flavor in ['lattice', 'stream']:
                try:
                    camelot_tables = camelot.read_pdf(
                        pdf_path,
                        pages=str(page_num + 1),
                        flavor=flavor,
                        strip_text='\n'
                    )
                    
                    for i, table in enumerate(camelot_tables):
                        df = table.df
                        if df.empty or len(df) < 2:
                            continue
                        
                        # First row as headers
                        headers = df.iloc[0].tolist()
                        headers = [str(h).strip() if h else f"col_{j}" for j, h in enumerate(headers)]
                        
                        # Rest as rows
                        rows_dicts = df.iloc[1:].to_dict('records')
                        
                        if len(rows_dicts) > 0:
                            tables_extracted.append({
                                "table_id": f"page_{page_num}_table_{i}_camelot_{flavor}",
                                "page_num": page_num,
                                "headers": headers,
                                "rows": rows_dicts,
                                "raw_data": df.values.tolist(),
                                "extraction_method": f"camelot_{flavor}"
                            })
                    
                    if len(tables_extracted) > 0:
                        break
                        
                except Exception as e:
                    logger.debug(f"Camelot {flavor} failed for page {page_num}: {e}")
                    continue
        
        except Exception as e:
            logger.debug(f"Camelot fallback failed for page {page_num}: {e}")
    
    return tables_extracted


def extract_pdf_full(pdf_path: str) -> Dict:
    """
    Main extraction function.
    Extracts all text, tables, and metadata from a PDF.
    
    Returns:
    {
        "metadata": {...},
        "pages": [
            {
                "page_num": 0,
                "text": "...",
                "is_chart_page": False,
                "tables": [...]
            },
            ...
        ],
        "total_pages": 120,
        "total_tables": 45,
        "chart_pages": [5, 12, 23, ...]
    }
    """
    logger.info(f"Starting extraction for: {pdf_path}")
    
    # Extract metadata from filename
    metadata = extract_metadata_from_filename(Path(pdf_path).name)
    metadata["file_path"] = str(pdf_path)
    
    # Check if extractable
    is_extractable = is_pdf_extractable(pdf_path)
    metadata["is_extractable"] = is_extractable
    
    if not is_extractable:
        logger.warning(f"PDF is not extractable (scanned): {pdf_path}")
        # Will need to use Gemini for OCR
    
    # Extract all pages
    pages_data = []
    chart_pages = []
    total_tables = 0
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        logger.info(f"Processing {total_pages} pages...")
        
        for page_num in range(total_pages):
            # Extract text
            text, is_chart_page = extract_text_from_page(pdf_path, page_num)
            
            # Extract tables
            tables = extract_tables_from_page(pdf_path, page_num)
            total_tables += len(tables)
            
            if is_chart_page:
                chart_pages.append(page_num)
            
            pages_data.append({
                "page_num": page_num,
                "text": text,
                "is_chart_page": is_chart_page,
                "tables": tables,
                "has_tables": len(tables) > 0
            })
            
            if (page_num + 1) % 10 == 0:
                logger.info(f"  Processed {page_num + 1}/{total_pages} pages...")
    
    result = {
        "metadata": metadata,
        "pages": pages_data,
        "total_pages": total_pages,
        "total_tables": total_tables,
        "chart_pages": chart_pages,
        "num_chart_pages": len(chart_pages)
    }
    
    logger.info(f"Extraction complete: {total_pages} pages, {total_tables} tables, {len(chart_pages)} chart pages")
    
    return result


def save_extraction_results(results: Dict, output_dir: str):
    """
    Save extraction results to JSON file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    company = results["metadata"]["company"]
    year = results["metadata"]["year"]
    
    filename = f"{company}_{year}_extraction.json"
    filepath = output_path / filename
    
    with open(filepath, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Saved extraction results to: {filepath}")
    return str(filepath)


# Test function
if __name__ == "__main__":
    # Test on AMD 2021 10-K
    pdf_path = "/Users/Sharunikaa/Desktop/hyperverge/uploads/AMD_2021_10K.pdf"
    
    print("Testing PDF extraction...")
    print(f"PDF: {pdf_path}")
    print(f"Extractable: {is_pdf_extractable(pdf_path)}")
    
    # Extract metadata
    metadata = extract_metadata_from_filename(Path(pdf_path).name)
    print(f"Metadata: {json.dumps(metadata, indent=2)}")
    
    # Extract first 5 pages
    print("\nExtracting first 5 pages...")
    for page_num in range(5):
        text, is_chart = extract_text_from_page(pdf_path, page_num)
        tables = extract_tables_from_page(pdf_path, page_num)
        print(f"  Page {page_num}: {len(text)} chars, {len(tables)} tables, chart={is_chart}")
