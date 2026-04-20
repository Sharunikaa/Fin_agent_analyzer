"""
Process: Main orchestrator for knowledge extraction pipeline
"""

import json
import logging
from pathlib import Path
import sys
from typing import Dict, Optional
import time

sys.path.append(str(Path(__file__).parent.parent))

from knowledge_base.config import PHASE1_OUTPUT, PHASE1_METADATA, PER_PDF_DIR
from knowledge_base.extractors.kpi_extractor import extract_kpis
from knowledge_base.extractors.risk_extractor import extract_risks
from knowledge_base.extractors.promise_extractor import extract_promises
from knowledge_base.extractors.anomaly_detector import detect_anomalies
from knowledge_base.extractors.sentiment_analyzer import analyze_sentiment

from knowledge_base.storage.duckdb_handler import init_duckdb, store_kpis, store_risks, store_promises, store_anomalies
from knowledge_base.storage.chromadb_handler import init_chromadb, store_insights
from knowledge_base.storage.neo4j_handler import init_neo4j, store_knowledge_graph

from knowledge_base.synthesizers.company_synthesizer import synthesize_company_knowledge, save_company_knowledge
from knowledge_base.synthesizers.year_synthesizer import synthesize_year_knowledge, save_year_knowledge
from knowledge_base.synthesizers.master_synthesizer import synthesize_master_knowledge, save_master_knowledge

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_document(doc_path: Path, prior_year_kpis: Optional[Dict] = None) -> Dict:
    """
    Process single document through complete knowledge extraction pipeline.
    
    Args:
        doc_path: Path to Phase 1 normalized JSON
        prior_year_kpis: Prior year KPIs for anomaly detection
        
    Returns:
        Dict with extraction results
    """
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Processing: {doc_path.name}")
    logger.info(f"{'='*80}")
    
    try:
        # Load Phase 1 output
        with open(doc_path) as f:
            doc_data = json.load(f)
        
        metadata = doc_data.get('metadata', {})
        company = metadata.get('company', 'Unknown')
        fiscal_year = metadata.get('year')
        doc_type = metadata.get('doc_type', '10-K')
        doc_id = doc_path.stem
        
        # Load Phase 1 metadata with pre-extracted KPIs
        metadata_path = PHASE1_METADATA / f"{doc_id}_meta.json"
        phase1_kpis = {}
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    phase1_meta = json.load(f)
                    phase1_kpis = phase1_meta.get('kpis', {})
                    logger.info(f"✅ Loaded Phase 1 KPIs as context")
            except Exception as e:
                logger.warning(f"Could not load metadata: {e}")
        
        # Convert document to text
        sections_text = '\n'.join([s.get('text', '') for s in doc_data.get('sections', [])])
        full_text = str(doc_data)  # Fallback to JSON string
        if sections_text:
            full_text = sections_text
        
        logger.info(f"📄 {company} {fiscal_year} ({doc_type})")
        
        # Extract KPIs
        logger.info("Extracting KPIs...")
        kpis = extract_kpis(full_text, company, fiscal_year, doc_type, phase1_kpis)
        if not kpis:
            logger.warning(f"⚠️  KPI extraction returned None for {company} {fiscal_year}")
            kpis = {'company': company, 'fiscal_year': fiscal_year, 'extraction_failed': True}
        
        # Extract Risks
        logger.info("Extracting Risks...")
        risks = extract_risks(full_text, company, fiscal_year, phase1_kpis)
        if not risks:
            risks = {'company': company, 'fiscal_year': fiscal_year, 'risks': []}
        
        # Extract Promises
        logger.info("Extracting Promises...")
        promises = extract_promises(full_text, company, fiscal_year, phase1_kpis)
        if not promises:
            promises = {'company': company, 'fiscal_year': fiscal_year, 'promises': []}
        
        # Detect Anomalies
        logger.info("Detecting Anomalies...")
        anomalies = detect_anomalies(kpis, prior_year_kpis, company)
        
        # Analyze Sentiment
        logger.info("Analyzing Sentiment...")
        sentiment = analyze_sentiment(full_text, company, fiscal_year, phase1_kpis)
        
        # Store in all backends
        logger.info("Storing in databases...")
        
        try:
            store_kpis(kpis, doc_id)
            store_risks(risks, doc_id)
            store_promises(promises, doc_id)
            store_anomalies(anomalies, doc_id)
            store_insights(kpis, risks, promises, sentiment, doc_id)
            store_knowledge_graph(company, fiscal_year, doc_id, kpis, risks, promises)
        except Exception as e:
            logger.error(f"Storage error: {e}")
        
        # Save per-PDF extraction
        logger.info("Saving per-PDF extraction...")
        per_pdf_output = {
            'doc_id': doc_id,
            'company': company,
            'fiscal_year': fiscal_year,
            'doc_type': doc_type,
            'kpis': kpis,
            'risks': risks,
            'promises': promises,
            'anomalies': anomalies,
            'sentiment': sentiment
        }
        
        output_path = PER_PDF_DIR / f"{company}_{fiscal_year}_{doc_type}.json"
        with open(output_path, 'w') as f:
            json.dump(per_pdf_output, f, indent=2)
        
        logger.info(f"✅ Completed: {output_path}")
        
        return {
            'doc_id': doc_id,
            'company': company,
            'fiscal_year': fiscal_year,
            'status': 'success',
            'data': per_pdf_output
        }
        
    except Exception as e:
        logger.error(f"Error processing document: {e}", exc_info=True)
        return {
            'doc_id': doc_path.stem,
            'status': 'error',
            'error': str(e)
        }


def process_batch(limit: Optional[int] = None):
    """
    Process all Phase 1 documents in batch.
    
    Args:
        limit: Max documents to process (for testing)
    """
    
    logger.info(f"\n{'='*80}")
    logger.info("KNOWLEDGE EXTRACTION PIPELINE")
    logger.info(f"{'='*80}")
    
    # Initialize databases
    logger.info("Initializing databases...")
    init_duckdb()
    try:
        init_chromadb()
    except Exception as e:
        logger.warning(f"ChromaDB initialization issue (will continue without it): {e}")
    try:
        init_neo4j()
    except Exception as e:
        logger.warning(f"Neo4j not available - skipping graph initialization: {e}")
    
    # Find all Phase 1 outputs
    doc_paths = sorted(list(PHASE1_OUTPUT.rglob("*.json")))
    if limit:
        doc_paths = doc_paths[:limit]
    
    logger.info(f"Found {len(doc_paths)} documents to process")
    
    # Process by company and year for anomaly detection
    kpis_cache = {}  # {company: {year: kpis}}
    results = []
    
    for i, doc_path in enumerate(doc_paths, 1):
        logger.info(f"\n[{i}/{len(doc_paths)}]")
        
        # Get prior year KPIs if available (for anomaly detection)
        metadata = json.load(open(doc_path)).get('metadata', {})
        company = metadata.get('company')
        year = metadata.get('year')
        
        prior_kpis = None
        if company and year and company in kpis_cache:
            prior_year = year - 1
            if prior_year in kpis_cache[company]:
                prior_kpis = kpis_cache[company][prior_year]
        
        # Process document
        result = process_document(doc_path, prior_kpis)
        results.append(result)
        
        # Cache KPIs for next year
        if result['status'] == 'success' and 'data' in result:
            company = result['company']
            year = result['fiscal_year']
            if company not in kpis_cache:
                kpis_cache[company] = {}
            kpis_cache[company][year] = result['data']['kpis']
        
        time.sleep(1)  # Rate limiting
    
    # Synthesize knowledge
    logger.info(f"\n{'='*80}")
    logger.info("SYNTHESIZING KNOWLEDGE")
    logger.info(f"{'='*80}")
    
    successful = [r for r in results if r['status'] == 'success']
    
    if successful:
        # Build synthesis data
        synthesis_data = {}
        for result in successful:
            company = result['company']
            year = result['fiscal_year']
            if company not in synthesis_data:
                synthesis_data[company] = {}
            synthesis_data[company][year] = result['data']
        
        # Generate per-company knowledge
        logger.info("Generating per-company knowledge...")
        for company, years_data in synthesis_data.items():
            content = synthesize_company_knowledge(company, years_data)
            save_company_knowledge(company, content)
        
        # Generate per-year knowledge
        logger.info("Generating per-year knowledge...")
        all_years = set()
        for company_years in synthesis_data.values():
            all_years.update(company_years.keys())
        
        for year in sorted(all_years):
            year_data = {}
            for company, company_data in synthesis_data.items():
                if year in company_data:
                    year_data[company] = company_data[year]
            
            if year_data:
                content = synthesize_year_knowledge(year, year_data)
                save_year_knowledge(year, content)
        
        # Generate master knowledge
        logger.info("Generating master knowledge...")
        content = synthesize_master_knowledge(synthesis_data)
        save_master_knowledge(content)
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("PROCESSING SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Total: {len(results)}")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(results) - len(successful)}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, help='Max documents to process')
    parser.add_argument('--doc-id', type=str, help='Process specific document')
    
    args = parser.parse_args()
    
    if args.doc_id:
        # Process single document
        matches = list(PHASE1_OUTPUT.rglob(f"{args.doc_id}.json"))
        if matches:
            process_document(matches[0])
        else:
            logger.error(f"Document not found: {args.doc_id}")
    else:
        # Process batch
        process_batch(limit=args.limit)
