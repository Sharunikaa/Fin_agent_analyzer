"""
Storage functions for DuckDB and ChromaDB.
Handles saving extracted data to persistent storage.
"""

import duckdb
import chromadb
from chromadb.config import Settings
import json
from pathlib import Path
from typing import Dict, List, Optional
import logging
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize embedding model (lazy loading)
_embedding_model = None

def get_embedding_model():
    """Get or initialize the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading embedding model: BAAI/bge-large-en-v1.5...")
        _embedding_model = SentenceTransformer('BAAI/bge-large-en-v1.5')
        logger.info("Embedding model loaded")
    return _embedding_model


def init_duckdb(db_path: str = "data/duckdb/finance.db"):
    """
    Initialize DuckDB database with required tables.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = duckdb.connect(db_path)
    
    # Create metadata table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            id INTEGER PRIMARY KEY,
            company VARCHAR,
            year INTEGER,
            doc_type VARCHAR,
            filename VARCHAR,
            file_path VARCHAR,
            is_extractable BOOLEAN,
            total_pages INTEGER,
            total_tables INTEGER,
            num_chart_pages INTEGER,
            ingestion_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company, year, doc_type)
        )
    """)
    
    # Create KPIs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kpis (
            id INTEGER PRIMARY KEY,
            company VARCHAR,
            year INTEGER,
            fiscal_period VARCHAR,
            total_revenue DOUBLE,
            gross_profit DOUBLE,
            gross_margin_pct DOUBLE,
            operating_income DOUBLE,
            operating_margin_pct DOUBLE,
            net_income DOUBLE,
            net_margin_pct DOUBLE,
            r_and_d DOUBLE,
            total_assets DOUBLE,
            total_liabilities DOUBLE,
            total_equity DOUBLE,
            cash_and_equivalents DOUBLE,
            total_debt DOUBLE,
            UNIQUE(company, year, fiscal_period)
        )
    """)
    
    # Create segment revenue table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS segment_revenue (
            id INTEGER PRIMARY KEY,
            company VARCHAR,
            year INTEGER,
            segment_name VARCHAR,
            revenue DOUBLE,
            UNIQUE(company, year, segment_name)
        )
    """)
    
    # Create tables catalog
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tables_catalog (
            id INTEGER PRIMARY KEY,
            company VARCHAR,
            year INTEGER,
            table_id VARCHAR,
            page_num INTEGER,
            table_type VARCHAR,
            section_type VARCHAR,
            headers VARCHAR,
            num_rows INTEGER,
            extraction_method VARCHAR
        )
    """)
    
    # Create risk factors table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS risk_factors (
            id INTEGER PRIMARY KEY,
            company VARCHAR,
            year INTEGER,
            risk_text TEXT,
            text_hash VARCHAR,
            embedding_id VARCHAR
        )
    """)
    
    logger.info(f"DuckDB initialized at {db_path}")
    
    return conn


def save_metadata_to_duckdb(conn, metadata: Dict):
    """Save document metadata to DuckDB."""
    conn.execute("""
        INSERT OR REPLACE INTO metadata 
        (company, year, doc_type, filename, file_path, is_extractable, 
         total_pages, total_tables, num_chart_pages)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        metadata.get("company"),
        metadata.get("year"),
        metadata.get("doc_type"),
        metadata.get("filename"),
        metadata.get("file_path"),
        metadata.get("is_extractable"),
        metadata.get("total_pages"),
        metadata.get("total_tables"),
        metadata.get("num_chart_pages")
    ])
    
    logger.info(f"Saved metadata: {metadata['company']} {metadata['year']}")


def save_kpis_to_duckdb(conn, company: str, year: int, kpis: Dict):
    """Save financial KPIs to DuckDB."""
    fiscal_period = f"FY{year}"
    
    conn.execute("""
        INSERT OR REPLACE INTO kpis
        (company, year, fiscal_period, total_revenue, gross_profit, gross_margin_pct,
         operating_income, operating_margin_pct, net_income, net_margin_pct,
         r_and_d, total_assets, total_liabilities, total_equity,
         cash_and_equivalents, total_debt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        company, year, fiscal_period,
        kpis.get("total_revenue"),
        kpis.get("gross_profit"),
        kpis.get("gross_margin_pct"),
        kpis.get("operating_income"),
        kpis.get("operating_margin_pct"),
        kpis.get("net_income"),
        kpis.get("net_margin_pct"),
        kpis.get("r_and_d"),
        kpis.get("total_assets"),
        kpis.get("total_liabilities"),
        kpis.get("total_equity"),
        kpis.get("cash_and_equivalents"),
        kpis.get("total_debt")
    ])
    
    logger.info(f"Saved KPIs: {company} {year}")


def save_segment_revenue_to_duckdb(conn, company: str, year: int, segment_revenue: Dict):
    """Save segment revenue to DuckDB."""
    for segment_name, revenue in segment_revenue.items():
        conn.execute("""
            INSERT OR REPLACE INTO segment_revenue
            (company, year, segment_name, revenue)
            VALUES (?, ?, ?, ?)
        """, [company, year, segment_name, revenue])
    
    logger.info(f"Saved {len(segment_revenue)} segments: {company} {year}")


def save_tables_catalog_to_duckdb(conn, company: str, year: int, tables: List[Dict]):
    """Save table catalog to DuckDB."""
    for table in tables:
        conn.execute("""
            INSERT OR REPLACE INTO tables_catalog
            (company, year, table_id, page_num, table_type, section_type,
             headers, num_rows, extraction_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            company, year,
            table.get("table_id"),
            table.get("page_num"),
            table.get("table_type", "other"),
            table.get("section_type", "other"),
            json.dumps(table.get("headers", [])),
            len(table.get("rows", [])),
            table.get("extraction_method", "unknown")
        ])
    
    logger.info(f"Saved {len(tables)} tables to catalog: {company} {year}")


def init_chromadb(persist_dir: str = "data/chromadb"):
    """
    Initialize ChromaDB client.
    """
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    
    client = chromadb.PersistentClient(path=persist_dir)
    
    # Create collection for narrative chunks
    try:
        collection = client.get_or_create_collection(
            name="financial_narratives",
            metadata={"description": "Narrative text chunks from financial documents"}
        )
        logger.info(f"ChromaDB initialized at {persist_dir}")
        return client, collection
    except Exception as e:
        logger.error(f"Error initializing ChromaDB: {e}")
        return None, None


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Text to chunk
        chunk_size: Target chunk size in tokens (approximate)
        overlap: Overlap between chunks in tokens
    
    Returns:
        List of text chunks
    """
    # Simple word-based chunking (approximate)
    words = text.split()
    chunks = []
    
    step = chunk_size - overlap
    
    for i in range(0, len(words), step):
        chunk_words = words[i:i + chunk_size]
        chunk = " ".join(chunk_words)
        chunks.append(chunk)
    
    return chunks


def save_sections_to_chromadb(collection, company: str, year: int, sections: Dict, pages_data: List[Dict]):
    """
    Save section text to ChromaDB with embeddings.
    
    Args:
        collection: ChromaDB collection
        company: Company name
        year: Year
        sections: Dict of {section_type: text}
        pages_data: List of page dicts (for page number mapping)
    """
    model = get_embedding_model()
    
    all_chunks = []
    all_metadatas = []
    all_ids = []
    
    chunk_id = 0
    
    for section_type, text in sections.items():
        if not text or len(text.strip()) < 50:
            continue
        
        # Chunk the text
        chunks = chunk_text(text)
        
        # Find page numbers for this section
        section_pages = [p["page_num"] for p in pages_data if p.get("section_type") == section_type]
        page_range = f"{min(section_pages)}-{max(section_pages)}" if section_pages else "unknown"
        
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadatas.append({
                "company": company,
                "year": str(year),
                "section_type": section_type,
                "chunk_index": i,
                "page_range": page_range,
                "doc_id": f"{company}_{year}"
            })
            all_ids.append(f"{company}_{year}_{section_type}_{chunk_id}")
            chunk_id += 1
    
    if not all_chunks:
        logger.warning("No chunks to save to ChromaDB")
        return
    
    logger.info(f"Embedding {len(all_chunks)} chunks...")
    embeddings = model.encode(all_chunks, show_progress_bar=True)
    
    # Add to ChromaDB
    collection.add(
        documents=all_chunks,
        embeddings=embeddings.tolist(),
        metadatas=all_metadatas,
        ids=all_ids
    )
    
    logger.info(f"Saved {len(all_chunks)} chunks to ChromaDB: {company} {year}")


def query_chromadb(collection, query: str, section_type: Optional[str] = None, 
                   company: Optional[str] = None, year: Optional[int] = None,
                   n_results: int = 5) -> List[Dict]:
    """
    Query ChromaDB for relevant chunks.
    
    Args:
        collection: ChromaDB collection
        query: Query text
        section_type: Optional filter by section type
        company: Optional filter by company
        year: Optional filter by year
        n_results: Number of results to return
    
    Returns:
        List of {text, metadata, distance} dicts
    """
    model = get_embedding_model()
    
    # Embed query
    query_embedding = model.encode([query])[0]
    
    # Build where filter
    where_filter = {}
    if section_type:
        where_filter["section_type"] = section_type
    if company:
        where_filter["company"] = company
    if year:
        where_filter["year"] = str(year)
    
    # Query
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=n_results,
        where=where_filter if where_filter else None
    )
    
    # Format results
    formatted_results = []
    for i in range(len(results["documents"][0])):
        formatted_results.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i]
        })
    
    return formatted_results


# Test function
if __name__ == "__main__":
    print("Testing storage initialization...\n")
    
    # Test DuckDB
    print("Initializing DuckDB...")
    conn = init_duckdb("data/duckdb/test.db")
    
    # Test metadata save
    test_metadata = {
        "company": "AMD",
        "year": 2021,
        "doc_type": "10K",
        "filename": "AMD_2021_10K",
        "file_path": "/test/path.pdf",
        "is_extractable": True,
        "total_pages": 120,
        "total_tables": 45,
        "num_chart_pages": 10
    }
    save_metadata_to_duckdb(conn, test_metadata)
    
    # Query back
    result = conn.execute("SELECT * FROM metadata WHERE company = 'AMD'").fetchall()
    print(f"✅ Saved and retrieved metadata: {len(result)} rows")
    
    # Test ChromaDB
    print("\nInitializing ChromaDB...")
    client, collection = init_chromadb("data/chromadb/test")
    
    if collection:
        print(f"✅ ChromaDB collection created: {collection.name}")
    
    print("\n✅ All storage tests passed!")
