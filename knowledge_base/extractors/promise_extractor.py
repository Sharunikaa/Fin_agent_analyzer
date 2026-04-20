"""
Promise Extractor: Extract forward-looking statements and guidance
"""

import json
import time
import logging
from typing import Dict, Optional
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

from knowledge_base.config import GEMINI_API_KEY, GROQ_API_KEY, LLM_CONFIG, RATE_LIMIT_DELAY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure based on backend
if LLM_CONFIG.get("backend") == "groq":
    try:
        from groq import Groq
        if GROQ_API_KEY:
            groq_client = Groq(api_key=GROQ_API_KEY)
        else:
            groq_client = None
    except ImportError:
        groq_client = None
else:
    import google.generativeai as genai
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)



def extract_promises(document_text: str, company_name: str, fiscal_year: int, phase1_kpis: Dict = None) -> Dict:
    """
    Extract forward-looking statements, guidance, and promises.
    
    Args:
        document_text: Full document text
        company_name: Company name
        fiscal_year: Fiscal year
        phase1_kpis: Pre-extracted KPIs from Phase 1 for context
        
    Returns:
        Dict with extracted promises
    """
    
    if phase1_kpis is None:
        phase1_kpis = {}
    
    system_prompt = """You are a financial analyst specializing in forward-looking statements. Extract all management guidance, targets, and promises about:
- Revenue growth targets
- Margin expansion/compression goals
- CapEx plans
- R&D investments
- Geographic expansion
- Product launches
- ESG commitments
- Capital returns (dividends, buybacks)

Include both quantified and qualitative statements."""
    
    # Build context from Phase 1 KPIs
    phase1_context = ""
    if phase1_kpis:
        phase1_context = f"""\n\nCurrent Financial Position (Phase 1 Pre-extracted KPIs):
- Current Revenue: ${phase1_kpis.get('total_revenue', 'N/A')}M
- Current Net Income: ${phase1_kpis.get('net_income', 'N/A')}M
- Current R&D: ${phase1_kpis.get('r_and_d', 'N/A')}M
- Gross Margin: {phase1_kpis.get('gross_margin_pct', 'N/A')}%
Use this as baseline for evaluating management targets and guidance."""
    
    user_prompt = f"""Extract all forward-looking statements and guidance from this {company_name} {fiscal_year} document.{phase1_context}

Return ONLY a JSON object:
{{
  "company": "{company_name}",
  "fiscal_year": {fiscal_year},
  "promises": [
    {{
      "text": "Brief description of promise",
      "category": "financial_target|operational|esg|capital_return|product|geographic|other",
      "exact_quote": "Exact quote from document",
      "target_year": 2025,
      "is_quantified": true,
      "page_ref": "page X",
      "delivery_status": "pending|delivered|missed"
    }}
  ]
}}

DOCUMENT:
{document_text[:50000]}
"""
    
    try:
        time.sleep(RATE_LIMIT_DELAY)
        
        model = genai.GenerativeModel(LLM_CONFIG["text_model"])
        response = model.generate_content(
            f"{system_prompt}\n\n{user_prompt}",
            generation_config=genai.types.GenerationConfig(
                temperature=LLM_CONFIG["temperature"],
                max_output_tokens=LLM_CONFIG["max_tokens"],
            )
        )
        
        response_text = response.text.strip()
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_text = response_text[json_start:json_end]
            promises = json.loads(json_text)
            
            promises['extraction_metadata'] = {
                'model': LLM_CONFIG["text_model"],
                'timestamp': time.time(),
                'success': True
            }
            
            logger.info(f"✅ Extracted {len(promises.get('promises', []))} promises from {company_name} {fiscal_year}")
            return promises
        else:
            logger.error("Failed to parse JSON from response")
            return {
                'company': company_name,
                'fiscal_year': fiscal_year,
                'promises': [],
                'extraction_metadata': {'success': False, 'error': 'JSON parsing failed'}
            }
            
    except Exception as e:
        logger.error(f"Error extracting promises: {e}")
        return {
            'company': company_name,
            'fiscal_year': fiscal_year,
            'promises': [],
            'extraction_metadata': {'success': False, 'error': str(e)}
        }


if __name__ == "__main__":
    # Test
    test_doc = "We expect to achieve 50% gross margin by 2025. We plan to invest $10B in R&D over the next 3 years."
    result = extract_promises(test_doc, "AMD", 2021)
    print(json.dumps(result, indent=2))
