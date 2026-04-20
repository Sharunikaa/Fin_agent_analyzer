#!/usr/bin/env python3
"""
Incremental ChromaDB embedding: safe to run in a second terminal while Phase 1/2 run.

- Only processes documents that already have ``phase2_output/chunks/**/{doc_id}_chunks.json``.
- Skips doc_ids already embedded (same chunk file mtime as recorded in manifest).
- Does NOT wipe collections (use ``python phase3/chromadb_setup.py`` for full rebuild).

Usage:
  # One pass: embed any new/updated chunk files
  python phase3/embed_incremental.py

  # Poll every 60 seconds (good for parallel terminal)
  python phase3/embed_incremental.py --loop 60

  # Re-embed everything that has chunk files (ignores manifest)
  python phase3/embed_incremental.py --force
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import chromadb
from sentence_transformers import SentenceTransformer

from config import CHROMADB_PATH, CHROMADB_COLLECTIONS, EMBEDDING_MODEL, PHASE2_OUTPUT
from chromadb_setup import embed_and_insert_chunks, ensure_collections_exist, load_embedding_model


MANIFEST_NAME = "embed_manifest.json"


def manifest_path() -> Path:
    p = CHROMADB_PATH / MANIFEST_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_manifest() -> Dict:
    p = manifest_path()
    if not p.is_file():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_manifest(data: Dict) -> None:
    with open(manifest_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def delete_doc_from_all_collections(client: chromadb.Client, doc_id: str) -> None:
    """Remove existing vectors for doc_id before re-embedding an updated Phase 2 file."""
    for collection_name in CHROMADB_COLLECTIONS:
        try:
            coll = client.get_collection(collection_name)
            coll.delete(where={"doc_id": doc_id})
        except Exception:
            pass


def load_chunks_from_file(chunks_file: Path) -> Tuple[str, List[dict]]:
    with open(chunks_file, encoding="utf-8") as f:
        data = json.load(f)
    doc_id = data["doc_id"]
    chunks = data["chunks"]
    meta = data["metadata"]
    for ch in chunks:
        ch["company"] = meta.get("company")
        ch["year"] = meta.get("year")
        ch["doc_type"] = meta.get("doc_type")
    return doc_id, chunks


def list_chunk_files() -> List[Path]:
    return sorted((PHASE2_OUTPUT / "chunks").rglob("*_chunks.json"))


def run_once(
    client: chromadb.Client,
    model: SentenceTransformer,
    manifest: Dict,
    force: bool,
) -> Tuple[Dict, int]:
    """
    Embed documents that are new or changed. Returns (updated_manifest, num_embedded).
    """
    ensure_collections_exist(client)
    files = list_chunk_files()
    embedded_count = 0

    for chunks_file in files:
        try:
            mtime = chunks_file.stat().st_mtime
            doc_id, chunks = load_chunks_from_file(chunks_file)
        except Exception as e:
            print(f"⚠️  Skip unreadable {chunks_file}: {e}")
            continue

        prev = manifest.get(doc_id)
        if not force and prev and prev.get("mtime") == mtime:
            continue

        print(f"\n📎 Embedding doc_id={doc_id} ({len(chunks)} chunks) ← {chunks_file.name}")
        delete_doc_from_all_collections(client, doc_id)
        embed_and_insert_chunks(client, model, chunks)
        manifest[doc_id] = {
            "mtime": mtime,
            "chunks_file": str(chunks_file),
            "num_chunks": len(chunks),
        }
        embedded_count += 1
        save_manifest(manifest)

    return manifest, embedded_count


def main():
    parser = argparse.ArgumentParser(description="Incremental Chroma embeddings (parallel-safe)")
    parser.add_argument(
        "--loop",
        type=int,
        metavar="SECONDS",
        help="Re-run forever, sleeping SECONDS between passes (e.g. 60)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore manifest; re-embed every document that has a chunks file",
    )
    args = parser.parse_args()

    print(f"Chroma path: {CHROMADB_PATH}")
    print(f"Phase 2 chunks root: {PHASE2_OUTPUT / 'chunks'}")

    client = chromadb.PersistentClient(path=str(CHROMADB_PATH))

    def one_pass():
        manifest = load_manifest()
        model = load_embedding_model()
        manifest, n = run_once(client, model, manifest, force=args.force)
        if n == 0:
            print("\n✅ No new or updated chunk files to embed (use --force to re-embed all).")
        else:
            print(f"\n✅ Embedded {n} document(s). Manifest: {manifest_path()}")
        return n

    if args.loop and args.loop > 0:
        print(f"🔁 Loop mode: every {args.loop}s (Ctrl+C to stop)\n")
        while True:
            try:
                one_pass()
            except KeyboardInterrupt:
                print("\nStopped.")
                break
            time.sleep(args.loop)
    else:
        one_pass()


if __name__ == "__main__":
    main()
