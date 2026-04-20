"""
Parallel Knowledge Base Document Processing

Process multiple documents concurrently using multiprocessing.

Usage:
    python knowledge_base/process_parallel.py
    python knowledge_base/process_parallel.py --workers 8
    python knowledge_base/process_parallel.py --start 62 --end 203
"""

import logging
import sys
from pathlib import Path
from typing import List, Tuple
import argparse
from multiprocessing import Pool, cpu_count
from functools import partial

sys.path.append(str(Path(__file__).parent.parent))

from knowledge_base.process import process_document
from knowledge_base.storage.chromadb_handler import init_chromadb

# Configure logging for multiprocessing
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_doc_wrapper(doc_path: Path) -> Tuple[str, bool, str]:
    """
    Wrapper for process_document to handle multiprocessing.
    
    Returns:
        (doc_name, success, message)
    """
    try:
        process_document(doc_path)
        return (doc_path.name, True, "✅")
    except Exception as e:
        return (doc_path.name, False, f"❌ {str(e)[:100]}")


def process_parallel(
    doc_dir: Path = None,
    num_workers: int = None,
    start_idx: int = 0,
    end_idx: int = None,
    verbose: bool = False
):
    """
    Process documents in parallel.
    
    Args:
        doc_dir: Directory containing normalized documents
        num_workers: Number of parallel workers (default: CPU count)
        start_idx: Start index in sorted document list
        end_idx: End index in sorted document list
        verbose: Print detailed progress
    """
    
    if doc_dir is None:
        doc_dir = Path("phase1_output/normalized")
    
    if num_workers is None:
        num_workers = max(1, cpu_count() - 1)  # Leave one CPU free
    
    # Initialize ChromaDB once (before multiprocessing)
    logger.info("🔧 Initializing ChromaDB...")
    try:
        init_chromadb()
    except Exception as e:
        logger.warning(f"ChromaDB unavailable: {e}")
    
    # Get documents (recursively from nested directories)
    docs = sorted(doc_dir.glob("**/*.json"))
    
    if end_idx is None:
        end_idx = len(docs)
    
    docs_to_process = docs[start_idx:end_idx]
    
    logger.info("="*80)
    logger.info(f"📚 PARALLEL DOCUMENT PROCESSING")
    logger.info("="*80)
    logger.info(f"Documents: {len(docs_to_process)} to process")
    logger.info(f"Workers: {num_workers}")
    logger.info(f"Range: [{start_idx}:{end_idx}] of {len(docs)}")
    logger.info("="*80 + "\n")
    
    # Process in parallel
    processed = 0
    failed = 0
    
    with Pool(processes=num_workers) as pool:
        # Use imap_unordered for better progress tracking
        results = pool.imap_unordered(
            process_doc_wrapper,
            docs_to_process,
            chunksize=2
        )
        
        # Stream results
        for i, (doc_name, success, message) in enumerate(results, start_idx + 1):
            if success:
                processed += 1
                status = message
            else:
                failed += 1
                status = message
            
            # Progress output
            pct = int((i / len(docs)) * 100)
            bar_len = 40
            filled = int((i / len(docs)) * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            
            print(f"[{i:3d}/{len(docs)}] {pct:3d}% [{bar}] {doc_name[:40]:<40} {status}")
            
            if verbose and not success:
                print(f"       Error details: {message}")
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info(f"📊 PROCESSING COMPLETE")
    logger.info("="*80)
    logger.info(f"✅ Processed: {processed}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"Total: {processed + failed}")
    logger.info("="*80 + "\n")
    
    return processed, failed


def main():
    parser = argparse.ArgumentParser(description="Parallel Document Processing")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--end", type=int, default=None, help="End index")
    parser.add_argument("--dir", type=str, default="phase1_output/normalized", help="Document directory")
    parser.add_argument("--verbose", action="store_true", help="Verbose error output")
    
    args = parser.parse_args()
    
    doc_dir = Path(args.dir)
    
    if not doc_dir.exists():
        logger.error(f"Document directory not found: {doc_dir}")
        sys.exit(1)
    
    processed, failed = process_parallel(
        doc_dir=doc_dir,
        num_workers=args.workers,
        start_idx=args.start,
        end_idx=args.end,
        verbose=args.verbose
    )
    
    # Exit with error if any failed
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
