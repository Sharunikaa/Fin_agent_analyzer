"""
KPI Extractor: Extract structured financial KPIs from documents
Uses LLM to extract exact numbers with page references
"""

import json
import time
import logging
from typing import Dict, Optional
import google.generativeai as genai
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from knowledge_base.config import GEMINI_API_KEY, LLM_CONFIG, RATE_LIMIT_DELAY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not found")


def extract_kpis(document_text: str, company_name: str, fiscal_year: int, doc_type: str = "10-K") -> Dict:
    """
    Extract financial KPIs from document using LLM.
    
    Args:
        document_text: Full document text
        company_name: Company name
        fiscal_year: Fiscal year
        doc_type: Document type (10-K, Annual Report, etc.)
        
    Returns:
        Dict with extracted KPIs
    """
    
    system_prompt = """You are a senior financial analyst with CFA credentials. Your task is to extract structured KPI data from a financial document. Be precise — only extract numbers explicitly stated in the document. Do not infer or calculate unless the document provides the calculation. If a value is not present, write "not disclosed"."""
    
    user_prompt = f"""Extract all financial KPIs from the following document.

Document metadata:
- Company: {company_name}
- Year: {fiscal_year}
- Document type: {doc_type}

Return ONLY a JSON object with this exact structure:
{{
  "company": "",
  "fiscal_year": "",
  "revenue": {{"value": null, "unit": "USD_millions", "page_ref": ""}},
  "gross_profit": {{"value": null, "unit": "USD_millions", "page_ref": ""}},
  "gross_margin_pct": {{"value": null, "page_ref": ""}},
  "ebitda": {{"value": null, "unit": "USD_millions", "page_ref": ""}},
  "net_income": {{"value": null, "unit": "USD_millions", "page_ref": ""}},
  "free_cash_flow": {{"value": null, "unit": "USD_millions", "page_ref": ""}},
  "total_debt": {{"value": null, "unit": "USD_millions", "page_ref": ""}},
  "cash_and_equivalents": {{"value": null, "unit": "USD_millions", "page_ref": ""}},
  "capex": {{"value": null, "unit": "USD_millions", "page_ref": ""}},
  "rd_expense": {{"value": null, "unit": "USD_millions", "page_ref": ""}},
  "employee_count": {{"value": null, "page_ref": ""}},
  "other_material_kpis": []
}}

DOCUMENT:
{document_text[:50000]}
"""  # Limit to first 50k chars to avoid token limits
    
    try:
        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)
        
        # Call LLM
        model = genai.GenerativeModel(LLM_CONFIG["model"])
        response = model.generate_content(
            f"{system_prompt}\n\n{user_prompt}",
            generation_config=genai.types.GenerationConfig(
                temperature=LLM_CONFIG["temperature"],
                max_output_tokens=LLM_CONFIG["max_tokens"],
            )
        )
        
        # Parse response
        response_text = response.text.strip()
        
        # Extract JSON from response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_text = response_text[json_start:json_end]
            kpis = json.loads(json_text)
            
            # Add metadata
            kpis['extraction_metadata'] = {
                'model': LLM_CONFIG["model"],
                'extraction_timestamp': time.time(),
                'document_length_chars': len(document_text),
            }
            
            logger.info(f"✅ Extracted KPIs for {company_name} {fiscal_year}")
            return kpis
        else:
            logger.error(f"❌ No JSON found in response")
            return None
            
    except Exception as e:
        logger.error(f"❌ KPI extraction failed: {e}")
        return None


def save_kpis(kpis: Dict, output_path: str):
    """Save extracted KPIs to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(kpis, f, indent=2)
    logger.info(f"💾 Saved KPIs to {output_path}")


if __name__ == "__main__":
    # Test with sample text
    sample_text = """
    AMD Annual Report 2021
    
    Consolidated Statements of Operations
    
    Year Ended December 25, 2021:
    - Net revenue: $16,434 million
    - Gross profit: $7,929 million
    - Gross margin: 48.3%
    - Net income: $3,162 million
    - Free cash flow: $3,520 million
    
    Balance Sheet:
    - Total debt: $313 million
    - Cash and cash equivalents: $3,557 million
    
    Research and Development:
    - R&D expense: $2,845 million
    
    Employees: 15,500 as of December 25, 2021
    """
    
    kpis = extract_kpis(sample_text, "AMD", 2021, "10-K")
    
    if kpis:
        print("\n" + "="*80)
        print("EXTRACTED KPIs")
        print("="*80)
        print(json.dumps(kpis, indent=2))
