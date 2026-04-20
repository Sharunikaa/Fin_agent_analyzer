"""
Chart extraction using Gemini Flash API.
Handles both chart data extraction and OCR for scanned pages.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import logging
from pdf2image import convert_from_path
import google.generativeai as genai
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API configured successfully")
else:
    logger.warning("GEMINI_API_KEY not found in .env file")


# Rate limiting (free tier: 15 requests/min)
RATE_LIMIT_DELAY = 4.5  # seconds between requests (safe margin)
last_request_time = 0


def wait_for_rate_limit():
    """Enforce rate limiting for Gemini API."""
    global last_request_time
    current_time = time.time()
    time_since_last = current_time - last_request_time
    
    if time_since_last < RATE_LIMIT_DELAY:
        sleep_time = RATE_LIMIT_DELAY - time_since_last
        logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
        time.sleep(sleep_time)
    
    last_request_time = time.time()


def rasterize_pdf_page(pdf_path: str, page_num: int, dpi: int = 150) -> Optional[object]:
    """
    Convert a PDF page to an image.
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0-indexed)
        dpi: Resolution (150 is good balance of quality/speed)
    
    Returns:
        PIL Image object or None
    """
    try:
        # pdf2image uses 1-indexed pages
        images = convert_from_path(
            pdf_path,
            first_page=page_num + 1,
            last_page=page_num + 1,
            dpi=dpi
        )
        
        if images:
            return images[0]
        return None
        
    except Exception as e:
        logger.error(f"Error rasterizing page {page_num}: {e}")
        return None


CHART_EXTRACTION_PROMPT = """You are analyzing a page from a financial document (10-K, annual report, or earnings deck).

This page contains a chart, graph, or visual data representation.

Your task:
1. Identify the chart type (bar, line, pie, area, combo, table, or other)
2. Extract the chart title
3. Extract axis labels (if applicable)
4. Extract ALL data points as structured data

Return ONLY valid JSON in this exact format:
{
  "chart_type": "bar|line|pie|area|combo|table|other",
  "title": "chart title here",
  "x_axis_label": "x-axis label or null",
  "y_axis_label": "y-axis label or null",
  "data_series": [
    {
      "series_name": "series name (e.g., Revenue, 2021, etc.)",
      "data_points": [
        {"label": "Q1 2021", "value": 5.2},
        {"label": "Q2 2021", "value": 5.8}
      ]
    }
  ],
  "notes": "any footnotes or annotations",
  "units": "millions, billions, percentage, etc."
}

If the page is NOT a chart (e.g., pure text page), return:
{
  "chart_type": "none",
  "reason": "This page contains only text"
}

Important:
- Extract EXACT numbers from the chart
- If values have units like $M or %, include them in "units" field
- For multi-series charts, create separate entries in data_series
- Return ONLY the JSON, no markdown formatting, no explanations
"""


OCR_EXTRACTION_PROMPT = """You are performing OCR on a scanned page from a financial document.

Extract ALL text from this page, maintaining the original structure and formatting as much as possible.

Return ONLY valid JSON in this format:
{
  "text": "extracted text here",
  "has_tables": true/false,
  "tables": [
    {
      "headers": ["col1", "col2"],
      "rows": [["val1", "val2"], ["val3", "val4"]]
    }
  ]
}

If the page contains tables, extract them in structured format.
Return ONLY the JSON, no markdown formatting.
"""


def extract_chart_with_gemini(image, prompt: str = CHART_EXTRACTION_PROMPT) -> Optional[Dict]:
    """
    Extract chart data using Gemini Flash vision model.
    
    Args:
        image: PIL Image object
        prompt: Extraction prompt
    
    Returns:
        Extracted data as dict, or None if failed
    """
    if not GEMINI_API_KEY:
        logger.error("Cannot extract chart: GEMINI_API_KEY not configured")
        return None
    
    try:
        # Rate limiting
        wait_for_rate_limit()
        
        # Use Gemini 1.5 Flash (fast, free tier)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Generate content
        response = model.generate_content([prompt, image])
        
        # Parse response
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        
        # Parse JSON
        data = json.loads(response_text)
        
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        logger.debug(f"Response text: {response_text[:500]}")
        return None
        
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        return None


def extract_ocr_with_gemini(image) -> Optional[Dict]:
    """
    Perform OCR on scanned page using Gemini.
    """
    return extract_chart_with_gemini(image, prompt=OCR_EXTRACTION_PROMPT)


def process_chart_pages(pdf_path: str, chart_page_nums: List[int], output_dir: str) -> List[Dict]:
    """
    Process all chart pages in a PDF.
    
    Args:
        pdf_path: Path to PDF
        chart_page_nums: List of page numbers that contain charts
        output_dir: Directory to save extracted chart JSONs
    
    Returns:
        List of extracted chart data dicts
    """
    if not chart_page_nums:
        logger.info("No chart pages to process")
        return []
    
    logger.info(f"Processing {len(chart_page_nums)} chart pages...")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    extracted_charts = []
    
    for i, page_num in enumerate(chart_page_nums):
        logger.info(f"  Processing chart page {page_num} ({i+1}/{len(chart_page_nums)})...")
        
        # Rasterize page
        image = rasterize_pdf_page(pdf_path, page_num)
        if not image:
            logger.warning(f"  Failed to rasterize page {page_num}")
            continue
        
        # Extract chart data
        chart_data = extract_chart_with_gemini(image)
        
        if chart_data:
            # Add metadata
            chart_data["page_num"] = page_num
            chart_data["source_pdf"] = str(pdf_path)
            
            # Skip if not actually a chart
            if chart_data.get("chart_type") == "none":
                logger.info(f"  Page {page_num} is not a chart, skipping")
                continue
            
            extracted_charts.append(chart_data)
            
            # Save individual chart JSON
            chart_filename = f"page_{page_num}_chart.json"
            chart_filepath = output_path / chart_filename
            with open(chart_filepath, 'w') as f:
                json.dump(chart_data, f, indent=2)
            
            logger.info(f"  ✅ Extracted {chart_data.get('chart_type')} chart: {chart_data.get('title', 'Untitled')[:50]}")
        else:
            logger.warning(f"  ❌ Failed to extract chart from page {page_num}")
    
    logger.info(f"Successfully extracted {len(extracted_charts)} charts")
    
    return extracted_charts


def process_scanned_pages(pdf_path: str, scanned_page_nums: List[int]) -> Dict[int, Dict]:
    """
    Perform OCR on scanned pages using Gemini.
    
    Returns:
        {page_num: {text: "...", has_tables: bool, tables: [...]}}
    """
    if not scanned_page_nums:
        return {}
    
    logger.info(f"Performing OCR on {len(scanned_page_nums)} scanned pages...")
    
    ocr_results = {}
    
    for i, page_num in enumerate(scanned_page_nums):
        logger.info(f"  OCR page {page_num} ({i+1}/{len(scanned_page_nums)})...")
        
        # Rasterize at higher DPI for OCR
        image = rasterize_pdf_page(pdf_path, page_num, dpi=300)
        if not image:
            continue
        
        # Extract text
        ocr_data = extract_ocr_with_gemini(image)
        
        if ocr_data:
            ocr_results[page_num] = ocr_data
            logger.info(f"  ✅ OCR successful: {len(ocr_data.get('text', ''))} chars")
        else:
            logger.warning(f"  ❌ OCR failed for page {page_num}")
    
    return ocr_results


def validate_chart_data(chart_data: Dict) -> bool:
    """
    Validate extracted chart data.
    Returns True if data looks valid, False otherwise.
    """
    if not chart_data:
        return False
    
    # Must have chart_type
    if "chart_type" not in chart_data or chart_data["chart_type"] == "none":
        return False
    
    # Must have data_series with at least one series
    if "data_series" not in chart_data or not chart_data["data_series"]:
        return False
    
    # Each series must have data_points
    for series in chart_data["data_series"]:
        if "data_points" not in series or not series["data_points"]:
            return False
    
    return True


# Test function
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python chart_extractor.py <pdf_path> [page_num]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    page_num = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    
    print(f"Testing chart extraction on {pdf_path}, page {page_num}")
    
    # Rasterize page
    print("Rasterizing page...")
    image = rasterize_pdf_page(pdf_path, page_num)
    
    if image:
        print(f"Image size: {image.size}")
        
        # Extract chart
        print("Extracting chart data with Gemini...")
        chart_data = extract_chart_with_gemini(image)
        
        if chart_data:
            print("\n✅ Extraction successful!")
            print(json.dumps(chart_data, indent=2))
            
            if validate_chart_data(chart_data):
                print("\n✅ Chart data is valid")
            else:
                print("\n⚠️ Chart data validation failed")
        else:
            print("\n❌ Extraction failed")
    else:
        print("❌ Failed to rasterize page")
