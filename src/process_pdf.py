"""
Main PDF processing pipeline.
Orchestrates extraction, classification, KPI extraction, and storage.
"""

import sys
import json
from pathlib import Path
from typing import Dict
import logging

# Import our modules
from extract_pdf import extract_pdf_full, save_extraction_results
from section_classifier import classify_pages, extract_all_sections, detect_financial_tables, classify_table_by_headers
from kpi_extractor import extract_all_kpis
from chart_extractor import process_chart_pages
from storage import (
    init_duckdb, init_chromadb,
    save_metadata_to_duckdb, save_kpis_to_duckdb,
    save_segment_revenue_to_duckdb, save_tables_catalog_to_duckdb,
    save_sections_to_chromadb
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_single_pdf(
    pdf_path: str,
    extract_charts: bool = True,
    save_to_db: bool = True,
    output_dir: str = "output"
) -> Dict:
    """
    Complete processing pipeline for a single PDF.
    
    Steps:
    1. Extract text and tables
    2. Classify sections
    3. Extract KPIs
    4. Extract charts (optional)
    5. Save to DuckDB + ChromaDB
    
    Args:
        pdf_path: Path to PDF file
        extract_charts: Whether to extract chart data (slower)
        save_to_db: Whether to save to databases
        output_dir: Directory to save intermediate results
    
    Returns:
        Processing results dict
    """
    logger.info("="*80)
    logger.info(f"Processing PDF: {pdf_path}")
    logger.info("="*80)
    
    # Step 1: Extract text and tables
    logger.info("\n[Step 1/6] Extracting text and tables...")
    extraction_results = extract_pdf_full(pdf_path)
    
    company = extraction_results["metadata"]["company"]
    year = extraction_results["metadata"]["year"]
    
    # Save raw extraction results
    extraction_json_path = save_extraction_results(extraction_results, output_dir)
    
    # Step 2: Classify sections
    logger.info("\n[Step 2/6] Classifying sections...")
    pages_data = extraction_results["pages"]
    pages_data = classify_pages(pages_data)
    extraction_results["pages"] = pages_data
    
    # Extract section text
    sections = extract_all_sections(pages_data)
    
    # Step 3: Classify tables
    logger.info("\n[Step 3/6] Classifying tables...")
    financial_tables = detect_financial_tables(pages_data)
    
    # Also classify tables by headers
    all_tables = []
    for page in pages_data:
        for table in page.get("tables", []):
            if "table_type" not in table or table["table_type"] == "other":
                table["table_type"] = classify_table_by_headers(table)
            table["section_type"] = page.get("section_type", "other")
            all_tables.append(table)
    
    logger.info(f"Total tables: {len(all_tables)}")
    logger.info(f"Financial statement tables: {len(financial_tables)}")
    
    # Step 4: Extract KPIs
    logger.info("\n[Step 4/6] Extracting KPIs...")
    kpi_results = extract_all_kpis(extraction_results)
    
    kpis = kpi_results["kpis"]
    segment_revenue = kpi_results["segment_revenue"]
    
    # Log extracted KPIs
    logger.info("Extracted KPIs:")
    for kpi_name, value in kpis.items():
        if value is not None:
            if "pct" in kpi_name:
                logger.info(f"  {kpi_name}: {value:.2f}%")
            else:
                logger.info(f"  {kpi_name}: ${value:.1f}M")
    
    if segment_revenue:
        logger.info("Segment Revenue:")
        for segment, revenue in segment_revenue.items():
            logger.info(f"  {segment}: ${revenue:.1f}M")
    
    # Step 5: Extract charts (optional)
    charts_data = []
    if extract_charts:
        logger.info("\n[Step 5/6] Extracting charts...")
        chart_pages = extraction_results.get("chart_pages", [])
        
        if chart_pages:
            charts_output_dir = f"{output_dir}/charts/{company}_{year}"
            charts_data = process_chart_pages(pdf_path, chart_pages, charts_output_dir)
            logger.info(f"Extracted {len(charts_data)} charts")
        else:
            logger.info("No chart pages detected")
    else:
        logger.info("\n[Step 5/6] Skipping chart extraction")
    
    # Step 6: Save to databases
    if save_to_db:
        logger.info("\n[Step 6/6] Saving to databases...")
        
        try:
            # Initialize databases
            db_conn = init_duckdb()
            
            # Save to DuckDB
            metadata = extraction_results["metadata"]
            metadata["total_tables"] = len(all_tables)
            
            save_metadata_to_duckdb(db_conn, metadata)
            save_kpis_to_duckdb(db_conn, company, year, kpis)
            
            if segment_revenue:
                save_segment_revenue_to_duckdb(db_conn, company, year, segment_revenue)
            
            save_tables_catalog_to_duckdb(db_conn, company, year, all_tables)
            
            db_conn.close()
            logger.info("✅ Saved to DuckDB")
            
            # Try ChromaDB (skip if fails)
            try:
                chroma_client, chroma_collection = init_chromadb()
                if chroma_collection:
                    save_sections_to_chromadb(chroma_collection, company, year, sections, pages_data)
                    logger.info("✅ Saved to ChromaDB")
            except Exception as e:
                logger.warning(f"⚠️  ChromaDB save failed (skipping): {e}")
                
        except Exception as e:
            logger.error(f"❌ Database save failed: {e}")
    else:
        logger.info("\n[Step 6/6] Skipping database save")
    
    # Compile results
    results = {
        "pdf_path": pdf_path,
        "company": company,
        "year": year,
        "metadata": extraction_results["metadata"],
        "sections_found": list(sections.keys()),
        "kpis": kpis,
        "segment_revenue": segment_revenue,
        "num_tables": len(all_tables),
        "num_financial_tables": len(financial_tables),
        "num_charts": len(charts_data),
        "extraction_json": extraction_json_path,
        "status": "success"
    }
    
    logger.info("\n" + "="*80)
    logger.info("✅ Processing complete!")
    logger.info(f"Company: {company} | Year: {year}")
    logger.info(f"Pages: {extraction_results['total_pages']} | Tables: {len(all_tables)} | Charts: {len(charts_data)}")
    logger.info(f"KPIs extracted: {len([k for k, v in kpis.items() if v is not None])}")
    logger.info("="*80 + "\n")
    
    return results


def main():
    """Command-line interface."""
    if len(sys.argv) < 2:
        print("Usage: python process_pdf.py <pdf_path> [--no-charts] [--no-db]")
        print("\nExample:")
        print("  python process_pdf.py uploads/AMD_2021_10K.pdf")
        print("  python process_pdf.py uploads/AMD_2021_10K.pdf --no-charts")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    extract_charts = "--no-charts" not in sys.argv
    save_to_db = "--no-db" not in sys.argv
    
    if not Path(pdf_path).exists():
        print(f"❌ Error: File not found: {pdf_path}")
        sys.exit(1)
    
    # Process PDF
    results = process_single_pdf(
        pdf_path,
        extract_charts=extract_charts,
        save_to_db=save_to_db
    )
    
    # Save summary
    summary_path = f"output/{results['company']}_{results['year']}_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
