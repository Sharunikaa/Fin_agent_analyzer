"""
Groq API Configuration & Verification

Verifies Groq API key is set and working.

Usage:
    python knowledge_base/verify_groq.py      # Check configuration
    python knowledge_base/verify_groq.py --test  # Run test extraction
"""

import os
import sys
import logging
import argparse
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_groq_config():
    """Check if Groq is properly configured."""
    logger.info("="*80)
    logger.info("🔧 GROQ CONFIGURATION CHECK")
    logger.info("="*80 + "\n")
    
    # Check environment variable
    groq_key = os.getenv("GROQ_API_KEY")
    
    if not groq_key:
        logger.error("❌ GROQ_API_KEY not found in environment")
        logger.info("\n📝 SET UP GROQ:\n")
        logger.info("1. Get free API key from: https://console.groq.com")
        logger.info("2. Set in shell:")
        logger.info("   export GROQ_API_KEY='your-key-here'")
        logger.info("\n3. Or add to .env file:")
        logger.info("   GROQ_API_KEY=your-key-here")
        logger.info("\n4. Or set directly in Python:")
        logger.info("   import os")
        logger.info("   os.environ['GROQ_API_KEY'] = 'your-key'")
        return False
    
    logger.info(f"✅ GROQ_API_KEY found: {groq_key[:10]}...")
    
    # Check LLM config
    from knowledge_base.config import LLM_CONFIG
    
    logger.info(f"\n📊 LLM Configuration:")
    logger.info(f"   Backend: {LLM_CONFIG.get('backend')}")
    logger.info(f"   Model: {LLM_CONFIG.get('text_model')}")
    logger.info(f"   Temperature: {LLM_CONFIG.get('temperature')}")
    logger.info(f"   Max tokens: {LLM_CONFIG.get('max_tokens')}")
    
    if LLM_CONFIG.get('backend') != 'groq':
        logger.warning(f"\n⚠️  Backend is {LLM_CONFIG.get('backend')}, not groq")
        logger.info("   To use Groq, either:")
        logger.info("   - Upgrade config.py default")
        logger.info("   - Set: export LLM_BACKEND=groq")
        return False
    
    logger.info("\n✅ Configuration looks good!")
    return True


def test_groq_connection():
    """Test Groq API connection with a real extraction."""
    logger.info("\n" + "="*80)
    logger.info("🧪 GROQ API CONNECTION TEST")
    logger.info("="*80 + "\n")
    
    try:
        from groq import Groq
        
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            logger.error("GROQ_API_KEY not set")
            return False
        
        client = Groq(api_key=groq_key)
        logger.info("✅ Groq client initialized")
        
        # Test with a simple extraction
        logger.info("\n🔍 Testing KPI extraction...")
        
        test_prompt = """Extract revenue and net income from this financial statement:
        
        FINANCIAL SUMMARY
        - Net Revenue: $45,327 million
        - Operating Income: $12,104 million  
        - Net Income: $8,934 million
        
        Return ONLY JSON:
        {
          "revenue": {"value": null, "unit": "USD_millions"},
          "net_income": {"value": null, "unit": "USD_millions"}
        }
        """
        
        response = client.chat.completions.create(
            model="llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": test_prompt}],
            temperature=0.1,
            max_tokens=500
        )
        
        result = response.choices[0].message.content
        logger.info(f"✅ Response received: {len(result)} chars\n")
        logger.info("Sample output:")
        logger.info(result[:200])
        
        return True
    
    except ImportError:
        logger.error("❌ groq library not installed")
        logger.info("\nInstall with: pip install groq")
        return False
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
        return False


def test_knowledge_base():
    """Test knowledge base with Groq."""
    logger.info("\n" + "="*80)
    logger.info("📚 KNOWLEDGE BASE EXTRACTION TEST")
    logger.info("="*80 + "\n")
    
    try:
        from knowledge_base.extractors.kpi_extractor import extract_kpis
        
        test_text = """
        AMD Annual Report 2021
        
        Consolidated Statements of Operations
        
        Year Ended December 25, 2021:
        - Net revenue: $16,434 million
        - Gross profit: $7,929 million
        - Gross margin: 48.3%
        - Net income: $3,162 million
        """
        
        phase1_context = {
            'total_revenue': 16434,
            'net_income': 3162,
            'gross_margin_pct': 48.3,
        }
        
        logger.info("Testing extract_kpis with Groq...")
        kpis = extract_kpis(test_text, "AMD", 2021, "10-K", phase1_kpis=phase1_context)
        
        if kpis:
            logger.info("✅ KPI extraction successful!")
            logger.info(f"\n📊 Extracted KPIs:")
            for key, value in kpis.items():
                if key not in ['company', 'fiscal_year', 'extraction_metadata']:
                    if isinstance(value, dict) and 'value' in value:
                        logger.info(f"   {key}: {value.get('value')} {value.get('unit', '')}")
            
            backend = kpis.get('extraction_metadata', {}).get('backend', 'unknown')
            logger.info(f"\n✅ Using backend: {backend}")
            return True
        else:
            logger.error("❌ KPI extraction returned None")
            return False
    
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Groq Configuration Verification")
    parser.add_argument("--test", action="store_true", help="Test Groq API connection")
    parser.add_argument("--kb-test", action="store_true", help="Test knowledge base extraction")
    
    args = parser.parse_args()
    
    # Check configuration
    config_ok = check_groq_config()
    
    if not config_ok:
        logger.info("\n" + "="*80)
        return
    
    # Optional: test connection
    if args.test:
        connection_ok = test_groq_connection()
        if not connection_ok:
            logger.info("\n" + "="*80)
            return
    
    # Optional: test knowledge base
    if args.kb_test:
        kb_ok = test_knowledge_base()
    
    logger.info("\n" + "="*80)
    logger.info("✅ GROQ SETUP COMPLETE")
    logger.info("="*80)
    logger.info("\nYou can now run:")
    logger.info("   python knowledge_base/test_query.py --query 'revenue growth'")
    logger.info("   python knowledge_base/process.py")
    logger.info("")


if __name__ == "__main__":
    main()
