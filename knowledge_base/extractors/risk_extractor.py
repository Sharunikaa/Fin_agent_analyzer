"""
Risk Extractor: Extract risk signals from documents
Uses LLM to identify and classify operational, financial, regulatory, and competitive risks
"""

import json
import time
import logging
from typing import Dict, List, Optional
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


def extract_risks(document_text: str, company_name: str, fiscal_year: int, phase1_kpis: Dict = None) -> Dict:
    """
    Extract risk signals from document using LLM.
    
    Args:
        document_text: Full document text
        company_name: Company name
        fiscal_year: Fiscal year
        phase1_kpis: Pre-extracted KPIs from Phase 1 for context
        
    Returns:
        Dict with extracted risks
    """
    
    if phase1_kpis is None:
        phase1_kpis = {}
    
    system_prompt = """You are a senior risk analyst. Extract all material risks from the document. Focus on:
- Operational risks (supply chain, competition, tech changes)
- Financial risks (credit, market, currency)
- Regulatory risks (compliance, legal, antitrust)
- Geopolitical risks (trade, sanctions, regulations)
- ESG risks (environmental, social, governance)

Be concise but thorough. Only extract risks explicitly discussed."""
    
    # Build context from Phase 1 KPIs
    phase1_context = ""
    if phase1_kpis:
        phase1_context = f"""\n\nCompany Financial Context (Phase 1 Pre-extracted KPIs):
- Revenue: ${phase1_kpis.get('total_revenue', 'N/A')}M
- Net Income: ${phase1_kpis.get('net_income', 'N/A')}M
- Total Assets: ${phase1_kpis.get('total_assets', 'N/A')}M
- Total Debt: ${phase1_kpis.get('total_debt', 'N/A')}M
Use this context to understand the company's financial position when assessing risks."""
    
    user_prompt = f"""Extract all material risks from this {company_name} {fiscal_year} document.{phase1_context}

Return ONLY a JSON object:
{{
  "company": "{company_name}",
  "fiscal_year": {fiscal_year},
  "risks": [
    {{
      "category": "competitive|operational|financial|regulatory|geopolitical|esg|governance",
      "description": "Brief description",
      "severity": "low|medium|high|critical",
      "language_intensity": "mild|moderate|strong|alarming",
      "quote": "Exact quote from document",
      "page_ref": "page X",
      "is_new_vs_prior_year": true/false
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
            risks = json.loads(json_text)
            
            risks['extraction_metadata'] = {
                'model': LLM_CONFIG["text_model"],
                'timestamp': time.time(),
                'success': True
            }
            
            logger.info(f"✅ Extracted {len(risks.get('risks', []))} risks from {company_name} {fiscal_year}")
            return risks
        else:
            logger.error("Failed to parse JSON from response")
            return {
                'company': company_name,
                'fiscal_year': fiscal_year,
                'risks': [],
                'extraction_metadata': {'success': False, 'error': 'JSON parsing failed'}
            }
            
    except Exception as e:
        logger.error(f"Error extracting risks: {e}")
        return {
            'company': company_name,
            'fiscal_year': fiscal_year,
            'risks': [],
            'extraction_metadata': {'success': False, 'error': str(e)}
        }


if __name__ == "__main__":
    # Test
    test_doc = "Risk Factors: We face intense competition from Intel and NVIDIA. Supply chain disruptions could impact production."
    result = extract_risks(test_doc, "AMD", 2021)
    print(json.dumps(result, indent=2))
