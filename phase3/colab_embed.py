"""
Colab GPU ChromaDB Embedding Script (streaming, RAM-safe)
==========================================================
Processes one chunk file at a time — never loads all chunks into memory.
Each batch is persisted immediately, so progress survives crashes.

Usage in Colab:
  !pip install chromadb sentence-transformers
  !python colab_embed.py
"""

import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import chromadb

CHUNKS_DIR = Path("phase2_output/chunks")
CHROMADB_PATH = Path("data/chromadb")
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"
BATCH_SIZE = 256
COLLECTIONS = {
    "business_overview": ["business_overview"],
    "risk_factors": ["risk_factors"],
    "mda": ["mda"],
    "financial_statements": ["financial_statements", "footnotes"],
    "all_sections": ["other", "header", "cover_page", "table_of_contents",
                     "segment_breakdown", "esg", "legal"],
}
SEC_TO_COL = {}
for col, types in COLLECTIONS.items():
    for t in types:
        SEC_TO_COL[t] = col


def main():
    CHROMADB_PATH.mkdir(parents=True, exist_ok=True)

    print("🤖 Loading model...")
    device = "cuda"
    try:
        import torch
        if not torch.cuda.is_available():
            device = "cpu"
            print("   ⚠️  No GPU, using CPU")
    except:
        device = "cpu"
    model = SentenceTransformer(EMBEDDING_MODEL, device=device)
    print(f"   ✅ Loaded on {device}")

    client = chromadb.PersistentClient(path=str(CHROMADB_PATH))

    # Ensure collections exist
    cols = {}
    for name in COLLECTIONS:
        try:
            cols[name] = client.get_collection(name)
        except:
            cols[name] = client.create_collection(name=name)

    # Gather already-indexed IDs using pagination to avoid memory overload
    existing_ids = set()
    for name, col in cols.items():
        cnt = col.count()
        if cnt:
            # Page through results to avoid fetching all IDs at once
            offset = 0
            page_size = 5000
            while offset < cnt:
                batch = col.get(offset=offset, limit=page_size)
                existing_ids.update(batch["ids"])
                offset += page_size
    print(f"📊 Already indexed: {len(existing_ids)} chunks\n")

    files = sorted(CHUNKS_DIR.rglob("*_chunks.json"))
    total_new = 0
    buffer = {}  # col_name -> list of chunks

    for fi, f in enumerate(tqdm(files, desc="Processing files")):
        with open(f) as fh:
            data = json.load(fh)
        meta = data.get("metadata", {})

        for c in data.get("chunks", []):
            if c.get("chunk_id") in existing_ids:
                continue
            st = c.get("section_type", "other")
            col_name = SEC_TO_COL.get(st)
            if not col_name:
                continue
            c["company"] = meta.get("company")
            c["year"] = meta.get("year")
            c["doc_type"] = meta.get("doc_type")
            buffer.setdefault(col_name, []).append(c)

        # Flush any buffer that hit BATCH_SIZE
        for col_name in list(buffer.keys()):
            while len(buffer[col_name]) >= BATCH_SIZE:
                batch = buffer[col_name][:BATCH_SIZE]
                buffer[col_name] = buffer[col_name][BATCH_SIZE:]
                _embed_batch(model, cols[col_name], batch)
                total_new += len(batch)

    # Flush remaining
    for col_name, chunks in buffer.items():
        if chunks:
            _embed_batch(model, cols[col_name], chunks)
            total_new += len(chunks)

    print(f"\n🎉 Done! Embedded {total_new} new chunks.")
    for name in COLLECTIONS:
        print(f"   {name}: {client.get_collection(name).count()}")


def _embed_batch(model, collection, batch):
    texts = [c["text"] for c in batch]
    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    collection.add(
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


if __name__ == "__main__":
    main()
