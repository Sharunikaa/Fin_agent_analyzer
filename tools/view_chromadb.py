"""
ChromaDB Viewer: Interactive tool to view ChromaDB collections
"""

import chromadb
from pathlib import Path
import json

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "chromadb"

def view_chromadb():
    """Interactive ChromaDB viewer."""
    
    if not DB_PATH.exists():
        print(f"❌ Database not found at: {DB_PATH}")
        print("   Run Phase 3 setup first: python phase3/setup.py")
        return
    
    print("="*80)
    print("CHROMADB VIEWER")
    print("="*80)
    print(f"Database: {DB_PATH}")
    print()
    
    # Connect
    client = chromadb.PersistentClient(path=str(DB_PATH))
    
    # List collections
    collections = client.list_collections()
    
    if not collections:
        print("❌ No collections found")
        print("   Run Phase 3 setup first: python phase3/setup.py")
        return
    
    print("📊 Available Collections:")
    print("-"*80)
    for i, collection in enumerate(collections, 1):
        print(f"{i}. {collection.name}")
        count = collection.count()
        print(f"   Documents: {count:,}")
    print()
    
    # Show collection details
    for collection in collections:
        print(f"\n📋 Collection: {collection.name}")
        print("-"*80)
        
        count = collection.count()
        print(f"Documents: {count:,}")
        
        if count > 0:
            # Get sample documents
            results = collection.get(limit=5)
            
            print("\nSample Documents (first 5):")
            for i, (doc_id, doc, metadata) in enumerate(zip(
                results['ids'],
                results['documents'],
                results['metadatas']
            ), 1):
                print(f"\n{i}. ID: {doc_id}")
                print(f"   Document: {doc[:200]}...")
                print(f"   Metadata: {json.dumps(metadata, indent=2)}")
        else:
            print("\n(No documents yet)")
        
        print()
    
    # Interactive query mode
    print("\n" + "="*80)
    print("INTERACTIVE QUERY MODE")
    print("="*80)
    print("Enter queries (or 'quit' to exit)")
    print()
    
    # Select collection
    if len(collections) == 1:
        selected_collection = collections[0]
        print(f"Using collection: {selected_collection.name}")
    else:
        print("Select collection:")
        for i, collection in enumerate(collections, 1):
            print(f"{i}. {collection.name}")
        
        choice = input("\nCollection number: ").strip()
        try:
            selected_collection = collections[int(choice) - 1]
            print(f"Using collection: {selected_collection.name}")
        except:
            print("Invalid choice, using first collection")
            selected_collection = collections[0]
    
    print()
    
    while True:
        try:
            query = input("Query> ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                break
            
            if not query:
                continue
            
            # Search
            results = selected_collection.query(
                query_texts=[query],
                n_results=5
            )
            
            print("\nResults:")
            print("-"*80)
            
            if results['documents'] and results['documents'][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                ), 1):
                    print(f"\n{i}. Score: {1 - distance:.3f}")
                    print(f"   Document: {doc[:300]}...")
                    print(f"   Metadata: {json.dumps(metadata, indent=2)}")
            else:
                print("No results found")
            
            print()
            
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")
    
    print("\n✅ Done")


if __name__ == "__main__":
    view_chromadb()
