"""
Inject: LLM context injection for enhanced query responses
"""

import logging
from pathlib import Path
import sys
from typing import Optional
import google.generativeai as genai

sys.path.append(str(Path(__file__).parent.parent))

from knowledge_base.config import MASTER_DIR, PER_COMPANY_DIR, GEMINI_API_KEY, LLM_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def load_master_knowledge() -> str:
    """Load master knowledge file."""
    master_file = MASTER_DIR / "sector_knowledge.md"
    if master_file.exists():
        with open(master_file) as f:
            return f.read()
    return ""


def load_company_knowledge(company: str) -> Optional[str]:
    """Load company-specific knowledge file."""
    company_file = PER_COMPANY_DIR / f"{company}_knowledge.md"
    if company_file.exists():
        with open(company_file) as f:
            return f.read()
    return None


def query_with_knowledge(
    user_question: str,
    company: Optional[str] = None
) -> str:
    """
    Answer user question with knowledge base context injected.
    
    Args:
        user_question: User's query
        company: Optional company filter
        
    Returns:
        Enhanced response with knowledge context
    """
    
    logger.info(f"Query: {user_question}")
    
    # Load knowledge context
    master_knowledge = load_master_knowledge()
    company_knowledge = None
    
    if company:
        company_knowledge = load_company_knowledge(company)
    
    # Build context
    context = "KNOWLEDGE BASE CONTEXT:\n\n"
    
    if company and company_knowledge:
        context += f"=== {company} Knowledge ===\n{company_knowledge}\n\n"
    
    if master_knowledge:
        context += f"=== Sector Knowledge ===\n{master_knowledge}\n\n"
    
    # Prepare prompt
    system_prompt = """You are a financial analyst with access to a knowledge base of extracted financial insights. 
Use the provided knowledge base to answer questions accurately. If relevant information is in the knowledge base, cite it.
Be specific with numbers and use data from the knowledge base."""
    
    user_prompt = f"""{context}

USER QUESTION:
{user_question}

Please answer the question using the knowledge base above. Include specific data points and sources where available."""
    
    try:
        # Call LLM
        model = genai.GenerativeModel(LLM_CONFIG["text_model"])
        response = model.generate_content(
            f"{system_prompt}\n\n{user_prompt}",
            generation_config=genai.types.GenerationConfig(
                temperature=LLM_CONFIG["temperature"],
                max_output_tokens=LLM_CONFIG["max_tokens"],
            )
        )
        
        answer = response.text.strip()
        logger.info(f"Response generated ({len(answer)} chars)")
        return answer
        
    except Exception as e:
        logger.error(f"Error querying with knowledge: {e}")
        return f"Error processing query: {e}"


def interactive_mode():
    """Run interactive query mode."""
    logger.info("\n" + "="*80)
    logger.info("Knowledge Base Query Interface")
    logger.info("="*80)
    logger.info("Type 'exit' to quit\n")
    
    while True:
        try:
            company = input("Company (leave blank for all): ").strip()
            if not company:
                company = None
            
            question = input("Question: ").strip()
            
            if question.lower() == 'exit':
                break
            
            print("\nSearching knowledge base...")
            answer = query_with_knowledge(question, company)
            print(f"\n{answer}\n")
            print("-" * 80 + "\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', type=str, help='Single query')
    parser.add_argument('--company', type=str, help='Filter by company')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode')
    
    args = parser.parse_args()
    
    if args.query:
        # Single query mode
        answer = query_with_knowledge(args.query, args.company)
        print(answer)
    elif args.interactive or (not args.query):
        # Interactive mode
        interactive_mode()
