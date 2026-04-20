"""
DuckDB Viewer: Interactive tool to view DuckDB database
"""

import duckdb
from pathlib import Path
import pandas as pd

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "duckdb" / "financial_intelligence.db"

def view_duckdb():
    """Interactive DuckDB viewer."""
    
    if not DB_PATH.exists():
        print(f"❌ Database not found at: {DB_PATH}")
        print("   Run Phase 3 setup first: python phase3/setup.py")
        return
    
    print("="*80)
    print("DUCKDB VIEWER")
    print("="*80)
    print(f"Database: {DB_PATH}")
    print()
    
    # Connect
    conn = duckdb.connect(str(DB_PATH))
    
    # Show tables
    print("📊 Available Tables:")
    print("-"*80)
    tables = conn.execute("SHOW TABLES").fetchdf()
    print(tables)
    print()
    
    # Show table details
    for table_name in tables['name']:
        print(f"\n📋 Table: {table_name}")
        print("-"*80)
        
        # Get row count
        count = conn.execute(f"SELECT COUNT(*) as count FROM {table_name}").fetchdf()
        print(f"Rows: {count['count'][0]:,}")
        
        # Show schema
        schema = conn.execute(f"DESCRIBE {table_name}").fetchdf()
        print("\nSchema:")
        print(schema[['column_name', 'column_type']].to_string(index=False))
        
        # Show sample data
        sample = conn.execute(f"SELECT * FROM {table_name} LIMIT 5").fetchdf()
        if len(sample) > 0:
            print("\nSample Data (first 5 rows):")
            print(sample.to_string(index=False))
        else:
            print("\n(No data yet)")
        
        print()
    
    # Interactive query mode
    print("\n" + "="*80)
    print("INTERACTIVE QUERY MODE")
    print("="*80)
    print("Enter SQL queries (or 'quit' to exit)")
    print("Examples:")
    print("  SELECT * FROM documents WHERE company = 'AMD'")
    print("  SELECT company, COUNT(*) FROM documents GROUP BY company")
    print()
    
    while True:
        try:
            query = input("SQL> ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                break
            
            if not query:
                continue
            
            result = conn.execute(query).fetchdf()
            print("\nResult:")
            print(result.to_string(index=False))
            print(f"\n({len(result)} rows)")
            print()
            
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")
    
    conn.close()
    print("\n✅ Connection closed")


if __name__ == "__main__":
    view_duckdb()
