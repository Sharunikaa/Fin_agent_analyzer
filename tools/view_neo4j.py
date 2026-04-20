"""
Neo4j Viewer: Interactive tool to view Neo4j graph database
"""

from neo4j import GraphDatabase
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Neo4j configuration
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "asdfghjkl")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "hyperverge-base")

def view_neo4j():
    """Interactive Neo4j viewer."""
    
    print("="*80)
    print("NEO4J VIEWER")
    print("="*80)
    print(f"URI: {NEO4J_URI}")
    print(f"User: {NEO4J_USER}")
    print()
    
    try:
        # Connect
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        with driver.session(database=NEO4J_DATABASE) as session:
            # Test connection
            result = session.run("RETURN 1 as test")
            result.single()
            print("✅ Connected to Neo4j")
            print()
            
            # Show node counts
            print("📊 Node Counts:")
            print("-"*80)
            
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, COUNT(n) as count
                ORDER BY count DESC
            """)
            
            for record in result:
                print(f"{record['label']}: {record['count']:,}")
            
            print()
            
            # Show relationship counts
            print("🔗 Relationship Counts:")
            print("-"*80)
            
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, COUNT(r) as count
                ORDER BY count DESC
            """)
            
            for record in result:
                print(f"{record['type']}: {record['count']:,}")
            
            print()
            
            # Sample queries
            print("📋 Sample Queries:")
            print("-"*80)
            
            queries = [
                ("Companies", "MATCH (c:Company) RETURN c.name as name, c.sector as sector LIMIT 10"),
                ("Documents", "MATCH (d:Document) RETURN d.company as company, d.year as year, d.doc_type as type LIMIT 10"),
                ("Risks", "MATCH (r:Risk) RETURN r.company as company, r.description as description LIMIT 5"),
            ]
            
            for title, query in queries:
                print(f"\n{title}:")
                result = session.run(query)
                for i, record in enumerate(result, 1):
                    print(f"{i}. {dict(record)}")
            
            print()
            
            # Interactive query mode
            print("\n" + "="*80)
            print("INTERACTIVE QUERY MODE")
            print("="*80)
            print("Enter Cypher queries (or 'quit' to exit)")
            print("\nExamples:")
            print("  MATCH (c:Company) RETURN c.name, c.sector")
            print("  MATCH (c:Company)-[:FILED]->(d:Document) WHERE c.name = 'AMD' RETURN d.year")
            print("  MATCH (r1:Risk)-[:EVOLVED_TO]->(r2:Risk) RETURN r1.description, r2.description")
            print()
            
            while True:
                try:
                    query = input("Cypher> ").strip()
                    
                    if query.lower() in ['quit', 'exit', 'q']:
                        break
                    
                    if not query:
                        continue
                    
                    result = session.run(query)
                    
                    print("\nResults:")
                    print("-"*80)
                    
                    count = 0
                    for record in result:
                        count += 1
                        print(f"{count}. {dict(record)}")
                    
                    print(f"\n({count} rows)")
                    print()
                    
                except KeyboardInterrupt:
                    print("\n\nExiting...")
                    break
                except Exception as e:
                    print(f"❌ Error: {e}\n")
        
        driver.close()
        print("\n✅ Connection closed")
        
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Neo4j is running")
        print("2. Check NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env")
        print("3. Install Neo4j Desktop: https://neo4j.com/download/")


if __name__ == "__main__":
    view_neo4j()
