"""
Phase 2 Main Processor: Orchestrate all Phase 2 operations
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from config import PHASE1_OUTPUT, PHASE2_OUTPUT, CHUNKS_DIR, SIGNALS_DIR, CLASSIFIED_SECTIONS_DIR, CLASSIFIED_TABLES_DIR
from section_classifier import classify_all_sections, validate_classification, get_section_statistics
from table_classifier import classify_all_tables, validate_table_classification, get_table_statistics
from chunker import create_all_chunks, get_chunk_statistics
from signal_extractor import extract_signals_from_chunk, get_signal_statistics


def process_document(doc_path: Path) -> Dict:
    """
    Process a single document through Phase 2 pipeline.
    
    Steps:
    1. Load Phase 1 output
    2. Classify sections (12 types)
    3. Classify tables (5 types)
    4. Create hierarchical chunks
    5. Extract signals from chunks
    6. Save outputs
    
    Args:
        doc_path: Path to Phase 1 normalized JSON
        
    Returns:
        result: Dict with processing results and statistics
    """
    start_time = time.time()
    
    print(f"\n{'='*80}")
    print(f"Processing: {doc_path.name}")
    print(f"{'='*80}")
    
    # Load Phase 1 output
    with open(doc_path) as f:
        doc_data = json.load(f)
    
    metadata = doc_data['metadata']
    sections = doc_data['sections']
    tables = doc_data['tables']
    
    # Extract doc_id from filename (Phase 1 doesn't store it in metadata)
    doc_id = doc_path.stem  # e.g., "AMD_2021_10K_a95494befa9d"
    
    print(f"\n📄 Document: {metadata['company']} {metadata['year']} ({metadata['doc_type']})")
    print(f"   Sections: {len(sections)}")
    print(f"   Tables: {len(tables)}")
    
    # Step 1: Classify sections
    print(f"\n🏷️  Step 1: Classifying sections...")
    classified_sections = classify_all_sections(sections, metadata)
    section_validation = validate_classification(classified_sections)
    section_stats = get_section_statistics(classified_sections)
    
    print(f"   ✅ Classified {len(classified_sections)} sections")
    print(f"   Distribution:")
    for section_type, count in sorted(section_stats['counts'].items(), key=lambda x: -x[1])[:5]:
        pct = section_stats['percentages'][section_type]
        print(f"      {section_type:20s}: {count:4d} ({pct:5.1f}%)")
    
    if not section_validation['valid']:
        print(f"   ⚠️  Validation warnings:")
        for warning in section_validation['warnings'][:3]:
            print(f"      {warning}")
    
    # Step 2: Classify tables
    print(f"\n📊 Step 2: Classifying tables...")
    classified_tables = classify_all_tables(tables)
    table_validation = validate_table_classification(classified_tables)
    table_stats = get_table_statistics(classified_tables)
    
    print(f"   ✅ Classified {len(classified_tables)} tables")
    print(f"   Distribution:")
    for table_type, count in sorted(table_stats['counts'].items(), key=lambda x: -x[1]):
        pct = table_stats['percentages'][table_type]
        storage = "DuckDB" if table_type != "other" else "ChromaDB"
        print(f"      {table_type:20s}: {count:4d} ({pct:5.1f}%) → {storage}")
    
    if not table_validation['valid']:
        print(f"   ⚠️  Validation warnings:")
        for warning in table_validation['warnings'][:3]:
            print(f"      {warning}")
    
    # Step 3: Create hierarchical chunks
    print(f"\n🔪 Step 3: Creating hierarchical chunks...")
    chunks = create_all_chunks(classified_sections, doc_id, metadata)
    chunk_stats = get_chunk_statistics(chunks)
    
    print(f"   ✅ Created {len(chunks)} chunks")
    print(f"   Avg tokens per chunk: {chunk_stats['avg_tokens_per_chunk']:.0f}")
    print(f"   Range: {chunk_stats['min_tokens']}-{chunk_stats['max_tokens']} tokens")
    print(f"   Top section types:")
    for section_type, count in sorted(chunk_stats['by_section_type'].items(), key=lambda x: -x[1])[:5]:
        print(f"      {section_type:20s}: {count:4d} chunks")
    
    # Step 4: Extract signals
    print(f"\n🏷️  Step 4: Extracting signals...")
    chunks_with_signals = []
    for i, chunk in enumerate(chunks):
        if i % 100 == 0 and i > 0:
            print(f"   Processing chunk {i}/{len(chunks)}...")
        chunk_with_signals = extract_signals_from_chunk(chunk)
        chunks_with_signals.append(chunk_with_signals)
    
    signal_stats = get_signal_statistics(chunks_with_signals)
    
    print(f"   ✅ Extracted {signal_stats['total_signals']} signals")
    print(f"   Avg signals per chunk: {signal_stats['avg_signals_per_chunk']:.1f}")
    print(f"   Signal breakdown:")
    for signal_type, count in signal_stats['signal_counts'].items():
        print(f"      {signal_type:20s}: {count:4d}")
    
    # Step 5: Save outputs
    print(f"\n💾 Step 5: Saving outputs...")
    
    # Save classified sections
    company = metadata['company']
    year = metadata['year']
    
    sections_output_dir = CLASSIFIED_SECTIONS_DIR / company / str(year)
    sections_output_dir.mkdir(parents=True, exist_ok=True)
    sections_output_path = sections_output_dir / f"{doc_id}_sections.json"
    
    with open(sections_output_path, 'w') as f:
        json.dump({
            'doc_id': doc_id,
            'metadata': metadata,
            'sections': classified_sections,
            'statistics': section_stats,
            'validation': section_validation,
        }, f, indent=2)
    
    print(f"   ✅ Saved classified sections: {sections_output_path}")
    
    # Save classified tables
    tables_output_dir = CLASSIFIED_TABLES_DIR / company / str(year)
    tables_output_dir.mkdir(parents=True, exist_ok=True)
    tables_output_path = tables_output_dir / f"{doc_id}_tables.json"
    
    with open(tables_output_path, 'w') as f:
        json.dump({
            'doc_id': doc_id,
            'metadata': metadata,
            'tables': classified_tables,
            'statistics': table_stats,
            'validation': table_validation,
        }, f, indent=2)
    
    print(f"   ✅ Saved classified tables: {tables_output_path}")
    
    # Save chunks with signals
    chunks_output_dir = CHUNKS_DIR / company / str(year)
    chunks_output_dir.mkdir(parents=True, exist_ok=True)
    chunks_output_path = chunks_output_dir / f"{doc_id}_chunks.json"
    
    with open(chunks_output_path, 'w') as f:
        json.dump({
            'doc_id': doc_id,
            'metadata': metadata,
            'chunks': chunks_with_signals,
            'statistics': {
                'chunk_stats': chunk_stats,
                'signal_stats': signal_stats,
            },
        }, f, indent=2)
    
    print(f"   ✅ Saved chunks: {chunks_output_path}")
    
    # Save signal summary
    signals_output_dir = SIGNALS_DIR / company / str(year)
    signals_output_dir.mkdir(parents=True, exist_ok=True)
    signals_output_path = signals_output_dir / f"{doc_id}_signals.json"
    
    # Extract top signals for summary
    top_risk_markers = []
    top_commitments = []
    top_entities = set()
    
    for chunk in chunks_with_signals:
        signals = chunk.get('signals', {})
        top_risk_markers.extend(signals.get('risk_markers', [])[:2])
        top_commitments.extend(signals.get('commitments', [])[:2])
        for entity in signals.get('named_entities', []):
            top_entities.add(entity['text'])
    
    with open(signals_output_path, 'w') as f:
        json.dump({
            'doc_id': doc_id,
            'metadata': metadata,
            'statistics': signal_stats,
            'top_risk_markers': top_risk_markers[:20],
            'top_commitments': top_commitments[:20],
            'named_entities': list(top_entities)[:50],
        }, f, indent=2)
    
    print(f"   ✅ Saved signals: {signals_output_path}")
    
    elapsed = time.time() - start_time
    
    result = {
        'doc_id': doc_id,
        'company': company,
        'year': year,
        'doc_type': metadata['doc_type'],
        'sections': len(classified_sections),
        'tables': len(classified_tables),
        'chunks': len(chunks_with_signals),
        'signals': signal_stats['total_signals'],
        'elapsed_seconds': elapsed,
        'outputs': {
            'sections': str(sections_output_path),
            'tables': str(tables_output_path),
            'chunks': str(chunks_output_path),
            'signals': str(signals_output_path),
        }
    }
    
    print(f"\n✅ Completed in {elapsed:.1f}s")
    
    return result


def process_single_document(doc_id: str, embedding_model=None) -> Optional[Dict]:
    """
    Run Phase 2 for one document identified by doc_id.

    Locates Phase 1 normalized JSON under ``phase1_output/normalized/**/{doc_id}.json``.
    ``embedding_model`` is reserved for future inline embedding; Phase 2 currently writes
    chunks to JSON on disk only.
    """
    _ = embedding_model
    matches = list(PHASE1_OUTPUT.rglob(f"{doc_id}.json"))
    if not matches:
        print(f"❌ No Phase 1 normalized JSON found for doc_id={doc_id} (expected under {PHASE1_OUTPUT})")
        return None
    return process_document(matches[0])


def process_batch(doc_paths: List[Path] = None) -> List[Dict]:
    """
    Process multiple documents.
    
    Args:
        doc_paths: List of paths to Phase 1 normalized JSONs (if None, process all)
        
    Returns:
        results: List of processing results
    """
    if doc_paths is None:
        # Find all Phase 1 outputs
        doc_paths = list(PHASE1_OUTPUT.rglob("*.json"))
    
    print(f"\n{'='*80}")
    print(f"PHASE 2: INTELLIGENT CHUNKING & SIGNAL EXTRACTION")
    print(f"{'='*80}")
    print(f"\nFound {len(doc_paths)} documents to process")
    
    results = []
    
    for i, doc_path in enumerate(doc_paths, 1):
        print(f"\n[{i}/{len(doc_paths)}]")
        
        try:
            result = process_document(doc_path)
            results.append(result)
        except Exception as e:
            print(f"❌ Error processing {doc_path.name}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'doc_id': doc_path.stem,
                'error': str(e),
            })
    
    # Summary report
    print(f"\n{'='*80}")
    print(f"PHASE 2 SUMMARY")
    print(f"{'='*80}")
    
    successful = [r for r in results if 'error' not in r]
    failed = [r for r in results if 'error' in r]
    
    print(f"\n✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")
    
    if successful:
        total_sections = sum(r['sections'] for r in successful)
        total_tables = sum(r['tables'] for r in successful)
        total_chunks = sum(r['chunks'] for r in successful)
        total_signals = sum(r['signals'] for r in successful)
        total_time = sum(r['elapsed_seconds'] for r in successful)
        
        print(f"\nTotals:")
        print(f"  Sections: {total_sections:,}")
        print(f"  Tables: {total_tables:,}")
        print(f"  Chunks: {total_chunks:,}")
        print(f"  Signals: {total_signals:,}")
        print(f"  Time: {total_time:.1f}s (avg {total_time/len(successful):.1f}s per doc)")
    
    # Save batch report
    report_path = PHASE2_OUTPUT / f"phase2_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_documents': len(results),
            'successful': len(successful),
            'failed': len(failed),
            'results': results,
        }, f, indent=2)
    
    print(f"\n📊 Report saved: {report_path}")
    
    return results


if __name__ == "__main__":
    # Process all Phase 1 outputs
    results = process_batch()
    
    print(f"\n{'='*80}")
    print(f"✅ Phase 2 complete!")
    print(f"{'='*80}")
