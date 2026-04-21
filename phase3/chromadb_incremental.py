"""
Incremental ChromaDB setup: only embeds chunks not already in ChromaDB.
Keeps existing data intact.
"""

import json
import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from config import CHROMADB_PATH, CHROMADB_COLLECTIONS, EMBEDDING_MODEL, BATCH_SIZE, PHASE2_OUTPUT


def run():
    client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
    model = SentenceTransformer(EMBEDDING_MODEL)

    # Ensure all collections exist (without deleting)
    for name, cfg in CHROMADB_COLLECTIONS.items():
        try:
            client.get_collection(name)
        except Exception:
            client.create_collection(name=name, metadata={
                "description": cfg["description"],
                "section_types": ",".join(cfg["section_types"]),
            })
            print(f"✅ Created missing collection: {name}")

    # Gather existing IDs across all collections
    existing_ids = set()
    for name in CHROMADB_COLLECTIONS:
        col = client.get_collection(name)
        cnt = col.count()
        if cnt:
            existing_ids.update(col.get(limit=cnt)["ids"])
    print(f"\n📊 Already indexed: {len(existing_ids)} chunks")

    # Load all chunks, skip existing
    chunks_by_col = {n: [] for n in CHROMADB_COLLECTIONS}
    for f in sorted((PHASE2_OUTPUT / "chunks").rglob("*_chunks.json")):
        with open(f) as fh:
            data = json.load(fh)
        meta = data.get("metadata", {})
        for chunk in data.get("chunks", []):
            if chunk.get("chunk_id") in existing_ids:
                continue
            chunk["company"] = meta.get("company")
            chunk["year"] = meta.get("year")
            chunk["doc_type"] = meta.get("doc_type")
            st = chunk.get("section_type", "other")
            target = None
            for cname, cfg in CHROMADB_COLLECTIONS.items():
                if st in cfg["section_types"]:
                    target = cname
                    break
            if target:
                chunks_by_col[target].append(chunk)

    total_new = sum(len(v) for v in chunks_by_col.values())
    print(f"🆕 New chunks to embed: {total_new}\n")

    for col_name, chunks in chunks_by_col.items():
        if not chunks:
            continue
        col = client.get_collection(col_name)
        print(f"📚 {col_name}: embedding {len(chunks)} chunks...")
        for i in tqdm(range(0, len(chunks), BATCH_SIZE), desc=f"  {col_name}"):
            batch = chunks[i:i + BATCH_SIZE]
            texts = [c["text"] for c in batch]
            embeddings = model.encode(texts, show_progress_bar=False).tolist()
            col.add(
                ids=[c["chunk_id"] for c in batch],
                embeddings=embeddings,
                documents=texts,
                metadatas=[{
                    "doc_id": c.get("doc_id") or "",
                    "section_id": c.get("section_id") or "",
                    "section_type": c.get("section_type") or "",
                    "company": c.get("company") or "",
                    "year": str(c.get("year") or ""),
                    "doc_type": c.get("doc_type") or "",
                    "chunk_index": str(c.get("chunk_index") or 0),
                    "token_count": str(c.get("token_count") or 0),
                } for c in batch],
            )
        print(f"   ✅ {col_name}: now {col.count()} total chunks\n")

    print("✅ Incremental ChromaDB update complete!")
    for name in CHROMADB_COLLECTIONS:
        print(f"   {name}: {client.get_collection(name).count()} chunks")


if __name__ == "__main__":
    run()
