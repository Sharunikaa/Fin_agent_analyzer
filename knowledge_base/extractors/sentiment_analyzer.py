"""
Sentiment Analyzer: Analyze tone and sentiment of documents
"""

import logging
from typing import Dict, Optional
from pathlib import Path
import sys
import time
import json

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


def analyze_sentiment(document_text: str, company_name: str, fiscal_year: int, phase1_kpis: Dict = None) -> Dict:
    """
    Analyze overall sentiment and tone of document.
    
    Args:
        document_text: Full document text
        company_name: Company name
        fiscal_year: Fiscal year
        phase1_kpis: Pre-extracted KPIs from Phase 1 for context
        
    Returns:
        Dict with sentiment analysis
    """
    
    if phase1_kpis is None:
        phase1_kpis = {}
    
    system_prompt = """Analyze the overall tone and sentiment of this financial document. Consider:
- Business outlook (optimistic, neutral, cautious, alarming)
- Risk discussion intensity (minimal, measured, prominent, alarming)
- Growth narrative (expansionary, stable, contracting)
- Management confidence (high, moderate, low)

Be objective and data-driven."""
    
    # Build context from Phase 1 KPIs
    phase1_context = ""
    if phase1_kpis:
        revenue = phase1_kpis.get('total_revenue', 0)
        net_income = phase1_kpis.get('net_income', 0)
        net_margin = (net_income / revenue * 100) if revenue else 0
        phase1_context = f"""\n\nCompany Financial Context:
- Revenue: ${revenue}M | Net Margin: {net_margin:.1f}%
- Total Assets: ${phase1_kpis.get('total_assets', 'N/A')}M | Total Debt: ${phase1_kpis.get('total_debt', 'N/A')}M
Consider the financial health when assessing tone."""
    
    user_prompt = f"""Analyze the sentiment and tone of this {company_name} {fiscal_year} document.{phase1_context}

Return ONLY a JSON object:
{{
  "company": "{company_name}",
  "fiscal_year": {fiscal_year},
  "overall_sentiment": "optimistic|neutral|cautious|alarming",
  "confidence": 0.85,
  "sections": {{
    "business_overview": "optimistic|neutral|cautious",
    "risks": "minimal|measured|prominent|alarming",
    "growth": "expansionary|stable|contracting",
    "management_confidence": "high|moderate|low"
  }},
  "key_themes": [
    "Theme 1",
    "Theme 2"
  ],
  "tone_summary": "Brief description of overall tone"
}}

DOCUMENT:
{document_text[:50000]}
"""
    
    try:
        time.sleep(RATE_LIMIT_DELAY)
        
        # Get response based on backend
        if LLM_CONFIG.get("backend") == "groq" and groq_client:
            response_text = _call_groq(system_prompt, user_prompt)
        else:
            response_text = _call_gemini(system_prompt, user_prompt)
        
        if not response_text:
            logger.error(f"❌ No response from LLM")
            return None
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_text = response_text[json_start:json_end]
            sentiment = json.loads(json_text)
            
            sentiment['extraction_metadata'] = {
                'model': LLM_CONFIG["text_model"],
                'backend': LLM_CONFIG.get("backend", "gemini"),
                'timestamp': time.time(),
                'success': True
            }
            
            logger.info(f"✅ Analyzed sentiment for {company_name} {fiscal_year}: {sentiment['overall_sentiment']}")
            return sentiment
        else:
            logger.error("Failed to parse JSON from response")
            return {
                'company': company_name,
                'fiscal_year': fiscal_year,
                'overall_sentiment': 'neutral',
                'sections': {},
                'extraction_metadata': {'success': False, 'error': 'JSON parsing failed'}
            }
            
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        return {
            'company': company_name,
            'fiscal_year': fiscal_year,
            'overall_sentiment': 'neutral',
            'sections': {},
            'extraction_metadata': {'success': False, 'error': str(e)}
        }


def _call_gemini(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call Gemini API."""
    try:
        import google.generativeai as genai
        model = genai.GenerativeModel(LLM_CONFIG["text_model"])
        response = model.generate_content(
            f"{system_prompt}\n\n{user_prompt}",
            generation_config=genai.types.GenerationConfig(
                temperature=LLM_CONFIG["temperature"],
                max_output_tokens=LLM_CONFIG["max_tokens"],
            )
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return None


def _call_groq(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call Groq API."""
    try:
        if not groq_client:
            logger.error("Groq client not initialized")
            return None
        
        response = groq_client.chat.completions.create(
            model=LLM_CONFIG["text_model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=LLM_CONFIG["temperature"],
            max_tokens=LLM_CONFIG["max_tokens"],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return None


if __name__ == "__main__":
    # Test
    test_doc = """We are well-positioned for growth. However, we face intense competition and regulatory challenges."""
    result = analyze_sentiment(test_doc, "AMD", 2021)
    print(json.dumps(result, indent=2))
