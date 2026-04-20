"""
ChromaDB Setup: Create collections and embed chunks
"""

import json
import chromadb
from pathlib import Path
from typing import Dict, List
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from config import CHROMADB_PATH, CHROMADB_COLLECTIONS, EMBEDDING_MODEL, BATCH_SIZE, PHASE2_OUTPUT


def load_embedding_model():
    """
    Load the embedding model.
    
    Returns:
        model: SentenceTransformer model
    """
    print(f"\n🤖 Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"   ✅ Model loaded (dimension: {model.get_sentence_embedding_dimension()})")
    return model


def ensure_collections_exist(client: chromadb.Client) -> None:
    """
    Ensure all configured collections exist. Does not delete existing data.
    Used by incremental embedding while Phase 1/2 are still running.
    """
    print(f"\n📚 Ensuring ChromaDB collections exist...")
    for collection_name, config in CHROMADB_COLLECTIONS.items():
        try:
            client.get_collection(collection_name)
            print(f"   ✓ Collection exists: {collection_name}")
        except Exception:
            client.create_collection(
                name=collection_name,
                metadata={
                    "description": config['description'],
                    "section_types": ",".join(config['section_types']),
                },
            )
            print(f"   ✅ Created collection: {collection_name}")


def create_collections(client: chromadb.Client):
    """
    Recreate ChromaDB collections from scratch (deletes existing).
    Use full setup_chromadb() for a clean rebuild.
    
    Args:
        client: ChromaDB client
    """
    print(f"\n📚 Creating ChromaDB collections...")
    
    for collection_name, config in CHROMADB_COLLECTIONS.items():
        try:
            # Delete existing collection if it exists
            try:
                client.delete_collection(collection_name)
            except:
                pass
            
            # Create new collection
            collection = client.create_collection(
                name=collection_name,
                metadata={
                    "description": config['description'],
                    "section_types": ",".join(config['section_types']),
                }
            )
            print(f"   ✅ Created collection: {collection_name}")
            print(f"      Section types: {', '.join(config['section_types'])}")
        
        except Exception as e:
            print(f"   ⚠️  Error creating {collection_name}: {e}")


def load_chunks() -> List[Dict]:
    """
    Load all chunks from Phase 2 output.
    
    Returns:
        all_chunks: List of all chunks with metadata
    """
    print(f"\n📄 Loading chunks from Phase 2...")
    
    chunks_files = list((PHASE2_OUTPUT / "chunks").rglob("*_chunks.json"))
    
    all_chunks = []
    for chunks_file in chunks_files:
        with open(chunks_file) as f:
            data = json.load(f)
        
        chunks = data['chunks']
        metadata = data['metadata']
        
        # Add document metadata to each chunk
        for chunk in chunks:
            chunk['company'] = metadata.get('company')
            chunk['year'] = metadata.get('year')
            chunk['doc_type'] = metadata.get('doc_type')
        
        all_chunks.extend(chunks)
    
    print(f"   ✅ Loaded {len(all_chunks)} chunks from {len(chunks_files)} documents")
    
    return all_chunks


def embed_and_insert_chunks(
    client: chromadb.Client,
    model: SentenceTransformer,
    chunks: List[Dict],
):
    """
    Embed chunks and insert into appropriate collections.
    
    Args:
        client: ChromaDB client
        model: Embedding model
        chunks: List of chunks
    """
    print(f"\n🔢 Embedding and inserting {len(chunks)} chunks...")
    
    # Group chunks by collection
    chunks_by_collection = {name: [] for name in CHROMADB_COLLECTIONS.keys()}
    
    for chunk in chunks:
        section_type = chunk.get('section_type', 'other')
        
        # Find appropriate collection
        collection_name = None
        for coll_name, config in CHROMADB_COLLECTIONS.items():
            if section_type in config['section_types']:
                collection_name = coll_name
                break
        
        if collection_name:
            chunks_by_collection[collection_name].append(chunk)
    
    # Process each collection
    for collection_name, coll_chunks in chunks_by_collection.items():
        if not coll_chunks:
            print(f"\n   ⚠️  No chunks for collection: {collection_name}")
            continue
        
        print(f"\n   📚 Processing collection: {collection_name} ({len(coll_chunks)} chunks)")
        
        collection = client.get_collection(collection_name)
        
        # Process in batches
        for i in tqdm(range(0, len(coll_chunks), BATCH_SIZE), desc=f"   Embedding {collection_name}"):
            batch = coll_chunks[i:i + BATCH_SIZE]
            
            # Extract texts
            texts = [chunk['text'] for chunk in batch]
            
            # Generate embeddings
            embeddings = model.encode(texts, show_progress_bar=False)
            
            # Prepare metadata (ChromaDB rejects None values)
            ids = [chunk['chunk_id'] for chunk in batch]
            metadatas = [
                {
                    'doc_id': chunk.get('doc_id') or '',
                    'section_id': chunk.get('section_id') or '',
                    'section_type': chunk.get('section_type') or '',
                    'company': chunk.get('company') or '',
                    'year': str(chunk.get('year') or ''),
                    'doc_type': chunk.get('doc_type') or '',
                    'chunk_index': str(chunk.get('chunk_index') or 0),
                    'token_count': str(chunk.get('token_count') or 0),
                }
                for chunk in batch
            ]
            
            # Insert into collection
            collection.add(
                ids=ids,
                embeddings=embeddings.tolist(),
                documents=texts,
                metadatas=metadatas,
            )
        
        print(f"   ✅ Inserted {len(coll_chunks)} chunks into {collection_name}")


def setup_chromadb():
    """
    Main function to set up ChromaDB with all chunks.
    
    Returns:
        stats: Dict with insertion statistics
    """
    print(f"\n{'='*80}")
    print(f"CHROMADB SETUP")
    print(f"{'='*80}")
    print(f"\nPath: {CHROMADB_PATH}")
    
    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
    
    # Load embedding model
    model = load_embedding_model()
    
    # Create collections
    create_collections(client)
    
    # Load chunks
    chunks = load_chunks()
    
    # Embed and insert
    embed_and_insert_chunks(client, model, chunks)
    
    # Get statistics
    print(f"\n{'='*80}")
    print(f"CHROMADB STATISTICS")
    print(f"{'='*80}")
    
    stats = {}
    for collection_name in CHROMADB_COLLECTIONS.keys():
        try:
            collection = client.get_collection(collection_name)
            count = collection.count()
            stats[collection_name] = count
            print(f"\n   {collection_name}: {count} chunks")
        except Exception as e:
            print(f"\n   ⚠️  Error getting {collection_name}: {e}")
            stats[collection_name] = 0
    
    total_chunks = sum(stats.values())
    print(f"\n   Total: {total_chunks} chunks across {len(CHROMADB_COLLECTIONS)} collections")
    
    print(f"\n✅ ChromaDB setup complete!")
    
    return stats


if __name__ == "__main__":
    stats = setup_chromadb()
    
    print(f"\n{'='*80}")
    print(f"✅ ChromaDB ready for semantic search!")
    print(f"{'='*80}")
