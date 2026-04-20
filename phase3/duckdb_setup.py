"""
DuckDB Setup: Create tables and insert structured data
"""

import json
import duckdb
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from config import DUCKDB_PATH, DUCKDB_SCHEMA, PHASE2_OUTPUT


def create_tables(conn: duckdb.DuckDBPyConnection):
    """
    Create all DuckDB tables.
    
    Args:
        conn: DuckDB connection
    """
    print("\n📊 Creating DuckDB tables...")
    
    for table_name, schema in DUCKDB_SCHEMA.items():
        conn.execute(schema)
        print(f"   ✅ Created table: {table_name}")


def insert_documents(conn: duckdb.DuckDBPyConnection):
    """
    Insert document metadata.
    
    Args:
        conn: DuckDB connection
    """
    print("\n📄 Inserting document metadata...")
    
    # Find all Phase 2 classified sections files
    sections_files = list((PHASE2_OUTPUT / "classified_sections").rglob("*_sections.json"))
    
    inserted = 0
    for sections_file in sections_files:
        with open(sections_file) as f:
            data = json.load(f)
        
        metadata = data['metadata']
        doc_id = data['doc_id']
        
        # Insert document
        conn.execute("""
            INSERT OR REPLACE INTO documents (
                doc_id, company, ticker, full_name, sector, year, doc_type,
                filing_date, pages, source, ingestion_method, ingest_timestamp, phase2_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            doc_id,
            metadata.get('company'),
            metadata.get('ticker'),
            metadata.get('full_name'),
            metadata.get('sector'),
            metadata.get('year'),
            metadata.get('doc_type'),
            metadata.get('filing_date'),
            metadata.get('pages'),
            metadata.get('source'),
            metadata.get('ingestion_method'),
            metadata.get('ingest_timestamp'),
            datetime.now().isoformat(),
        ])
        
        inserted += 1
    
    print(f"   ✅ Inserted {inserted} documents")
    
    return inserted


def insert_sections_metadata(conn: duckdb.DuckDBPyConnection):
    """
    Insert section metadata.
    
    Args:
        conn: DuckDB connection
    """
    print("\n📋 Inserting section metadata...")
    
    sections_files = list((PHASE2_OUTPUT / "classified_sections").rglob("*_sections.json"))
    
    total_sections = 0
    for sections_file in sections_files:
        with open(sections_file) as f:
            data = json.load(f)
        
        doc_id = data['doc_id']
        metadata = data['metadata']
        sections = data['sections']
        
        for section in sections:
            section_id = section.get('section_id', f"{doc_id}_sec_{total_sections}")
            
            conn.execute("""
                INSERT INTO sections_metadata (
                    section_id, doc_id, company, year, section_type,
                    level, page_start, page_end, text_length, chunk_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (section_id) DO UPDATE SET
                    section_type = EXCLUDED.section_type,
                    text_length = EXCLUDED.text_length
            """, [
                section_id,
                doc_id,
                metadata.get('company'),
                metadata.get('year'),
                section.get('section_type', 'other'),
                section.get('level', 0),
                section.get('page_start'),
                section.get('page_end'),
                len(section.get('text', '')),
                1,  # Will be updated later with actual chunk count
            ])
            
            total_sections += 1
    
    print(f"   ✅ Inserted {total_sections} section metadata records")
    
    return total_sections


def insert_tables_metadata(conn: duckdb.DuckDBPyConnection):
    """
    Insert table metadata.
    
    Args:
        conn: DuckDB connection
    """
    print("\n📊 Inserting table metadata...")
    
    tables_files = list((PHASE2_OUTPUT / "classified_tables").rglob("*_tables.json"))
    
    total_tables = 0
    for tables_file in tables_files:
        with open(tables_file) as f:
            data = json.load(f)
        
        doc_id = data['doc_id']
        metadata = data['metadata']
        tables = data['tables']
        
        for table in tables:
            table_id = table.get('table_id', f"{doc_id}_tbl_{total_tables}")
            
            conn.execute("""
                INSERT INTO tables_metadata (
                    table_id, doc_id, company, year, table_type,
                    storage_destination, location, caption, row_count, column_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (table_id) DO UPDATE SET
                    table_type = EXCLUDED.table_type,
                    storage_destination = EXCLUDED.storage_destination
            """, [
                table_id,
                doc_id,
                metadata.get('company'),
                metadata.get('year'),
                table.get('table_type', 'other'),
                table.get('storage_destination', 'chromadb'),
                table.get('location', ''),
                table.get('caption', ''),
                len(table.get('rows', [])),
                len(table.get('headers', [])),
            ])
            
            total_tables += 1
    
    print(f"   ✅ Inserted {total_tables} table metadata records")
    
    return total_tables


def insert_signals(conn: duckdb.DuckDBPyConnection):
    """
    Insert extracted signals.
    
    Args:
        conn: DuckDB connection
    """
    print("\n🏷️  Inserting signals...")
    
    signals_files = list((PHASE2_OUTPUT / "signals").rglob("*_signals.json"))
    
    total_signals = 0
    for signals_file in signals_files:
        with open(signals_file) as f:
            data = json.load(f)
        
        doc_id = data['doc_id']
        metadata = data['metadata']
        
        # Insert risk markers
        for i, marker in enumerate(data.get('top_risk_markers', [])[:20]):
            signal_id = f"{doc_id}_risk_{i}"
            
            try:
                conn.execute("""
                    INSERT INTO signals (
                        signal_id, doc_id, company, year, signal_type,
                        signal_text, context, section_id, chunk_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (signal_id) DO NOTHING
                """, [
                    signal_id,
                    doc_id,
                    metadata.get('company'),
                    metadata.get('year'),
                    'risk_marker',
                    marker.get('text', ''),
                    marker.get('pattern', ''),
                    None,
                    None,
                ])
                
                total_signals += 1
            except Exception:
                pass
        
        # Insert commitments
        for i, commit in enumerate(data.get('top_commitments', [])[:20]):
            signal_id = f"{doc_id}_commit_{i}"
            
            try:
                conn.execute("""
                    INSERT INTO signals (
                        signal_id, doc_id, company, year, signal_type,
                        signal_text, context, section_id, chunk_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (signal_id) DO NOTHING
                """, [
                    signal_id,
                    doc_id,
                    metadata.get('company'),
                    metadata.get('year'),
                    'commitment',
                    commit.get('text', ''),
                    commit.get('context', ''),
                    None,
                    None,
                ])
                
                total_signals += 1
            except Exception as e:
                # Skip if insert fails
                pass
    
    print(f"   ✅ Inserted {total_signals} signals")
    
    return total_signals


def setup_duckdb():
    """
    Main function to set up DuckDB with all data.
    
    Returns:
        stats: Dict with insertion statistics
    """
    print(f"\n{'='*80}")
    print(f"DUCKDB SETUP")
    print(f"{'='*80}")
    print(f"\nDatabase: {DUCKDB_PATH}")
    
    # Connect to DuckDB
    conn = duckdb.connect(str(DUCKDB_PATH))
    
    try:
        # Create tables
        create_tables(conn)
        
        # Insert data
        docs_count = insert_documents(conn)
        sections_count = insert_sections_metadata(conn)
        tables_count = insert_tables_metadata(conn)
        signals_count = insert_signals(conn)
        
        # Commit
        conn.commit()
        
        # Get statistics
        print(f"\n{'='*80}")
        print(f"DUCKDB STATISTICS")
        print(f"{'='*80}")
        
        stats = {
            'documents': conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
            'sections': conn.execute("SELECT COUNT(*) FROM sections_metadata").fetchone()[0],
            'tables': conn.execute("SELECT COUNT(*) FROM tables_metadata").fetchone()[0],
            'signals': conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0],
        }
        
        print(f"\n📊 Database Statistics:")
        print(f"   Documents: {stats['documents']}")
        print(f"   Sections: {stats['sections']}")
        print(f"   Tables: {stats['tables']}")
        print(f"   Signals: {stats['signals']}")
        
        # Sample queries
        print(f"\n📋 Sample Queries:")
        
        # Companies
        companies = conn.execute("SELECT DISTINCT company, COUNT(*) as doc_count FROM documents GROUP BY company ORDER BY company").fetchall()
        print(f"\n   Companies:")
        for company, count in companies:
            print(f"      {company}: {count} documents")
        
        # Section types
        section_types = conn.execute("""
            SELECT section_type, COUNT(*) as count 
            FROM sections_metadata 
            GROUP BY section_type 
            ORDER BY count DESC 
            LIMIT 5
        """).fetchall()
        print(f"\n   Top Section Types:")
        for section_type, count in section_types:
            print(f"      {section_type}: {count}")
        
        # Table types
        table_types = conn.execute("""
            SELECT table_type, storage_destination, COUNT(*) as count 
            FROM tables_metadata 
            GROUP BY table_type, storage_destination 
            ORDER BY count DESC
        """).fetchall()
        print(f"\n   Table Types:")
        for table_type, storage, count in table_types:
            print(f"      {table_type} → {storage}: {count}")
        
        print(f"\n✅ DuckDB setup complete!")
        
        return stats
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    finally:
        conn.close()


if __name__ == "__main__":
    stats = setup_duckdb()
    
    print(f"\n{'='*80}")
    print(f"✅ DuckDB ready for queries!")
    print(f"{'='*80}")
