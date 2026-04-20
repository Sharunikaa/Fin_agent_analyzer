"""
Neo4j Setup: Create graph nodes and relationships from Phase 2 output.
Run AFTER Phase 2 chunking, BEFORE ChromaDB embedding.

Graph model:
  (Company)-[:FILED]->(Document)-[:CONTAINS]->(Section)<-[:PART_OF]-(Chunk)
  (Document)-[:SUPERSEDES]->(Document)   [same company, prev year]
"""

import json
import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "asdfghjkl")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "hyperverge-base")

PHASE2_OUTPUT = Path(__file__).parent.parent / "phase2_output"

BATCH_SIZE = 500
MAX_WORKERS = 4


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def create_constraints(tx):
    for label, prop in [("Company", "name"), ("Document", "doc_id"),
                        ("Section", "section_id"), ("Chunk", "chunk_id")]:
        tx.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")
    # Index for fast section lookups by company+year
    tx.run("CREATE INDEX IF NOT EXISTS FOR (s:Section) ON (s.company, s.year)")


def ingest_document(driver, doc_id, metadata, sections, chunks):
    t0 = time.time()
    company = metadata.get("company", "")
    year = metadata.get("year", 0)
    doc_type = metadata.get("doc_type", "10-K")

    with driver.session(database=NEO4J_DATABASE) as session:
        # Company + Document + FILED + SUPERSEDES
        session.run(
            """
            MERGE (c:Company {name: $company})
            MERGE (d:Document {doc_id: $doc_id})
            SET d.year = $year, d.doc_type = $doc_type, d.company = $company
            MERGE (c)-[:FILED]->(d)
            WITH d
            OPTIONAL MATCH (d_old:Document {company: $company, doc_type: $doc_type})
            WHERE d_old.year = $prev_year
            FOREACH (_ IN CASE WHEN d_old IS NOT NULL THEN [1] ELSE [] END |
                MERGE (d)-[:SUPERSEDES]->(d_old)
            )
            """,
            company=company, doc_id=doc_id, year=year, doc_type=doc_type, prev_year=year - 1,
        )

        # Batch sections
        sec_rows = [
            {"section_id": s.get("section_id", ""),
             "section_type": s.get("section_type", "other"),
             "text_length": len(s.get("text", ""))}
            for s in sections
        ]
        for i in range(0, len(sec_rows), BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS r
                MATCH (d:Document {doc_id: $doc_id})
                MERGE (s:Section {section_id: r.section_id})
                SET s.section_type = r.section_type, s.text_length = r.text_length,
                    s.company = $company, s.year = $year
                MERGE (d)-[:CONTAINS]->(s)
                """,
                rows=sec_rows[i:i+BATCH_SIZE], doc_id=doc_id, company=company, year=year,
            )

        # Batch chunks
        chunk_rows = [
            {"chunk_id": c.get("chunk_id", ""),
             "section_id": c.get("section_id", ""),
             "chunk_index": c.get("chunk_index", 0),
             "token_count": c.get("token_count", 0),
             "section_type": c.get("section_type", "other")}
            for c in chunks
        ]
        for i in range(0, len(chunk_rows), BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS r
                MATCH (s:Section {section_id: r.section_id})
                MERGE (c:Chunk {chunk_id: r.chunk_id})
                SET c.chunk_index = r.chunk_index, c.token_count = r.token_count,
                    c.section_type = r.section_type
                MERGE (c)-[:PART_OF]->(s)
                """,
                rows=chunk_rows[i:i+BATCH_SIZE],
            )

    elapsed = time.time() - t0
    return doc_id, len(sections), len(chunks), elapsed


def setup_neo4j():
    driver = get_driver()

    with driver.session(database=NEO4J_DATABASE) as session:
        session.execute_write(create_constraints)
    print("✅ Neo4j constraints created")

    section_files = sorted((PHASE2_OUTPUT / "classified_sections").rglob("*_sections.json"))
    chunk_files = sorted((PHASE2_OUTPUT / "chunks").rglob("*_chunks.json"))

    chunks_by_doc = {}
    for cf in chunk_files:
        with open(cf) as f:
            data = json.load(f)
        chunks_by_doc[data["doc_id"]] = data.get("chunks", [])

    jobs = []
    for sf in section_files:
        with open(sf) as f:
            data = json.load(f)
        jobs.append((data["doc_id"], data["metadata"], data["sections"],
                      chunks_by_doc.get(data["doc_id"], [])))

    total = len(jobs)
    print(f"📄 Processing {total} documents with {MAX_WORKERS} workers...\n")
    t_start = time.time()
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(ingest_document, driver, *job): job[0] for job in jobs}
        for future in as_completed(futures):
            doc_id, n_sec, n_ch, elapsed = future.result()
            done += 1
            print(f"   [{done}/{total}] ✅ {doc_id}: {n_sec} sec, {n_ch} chunks ({elapsed:.1f}s)")

    driver.close()
    total_time = time.time() - t_start
    print(f"\n✅ Neo4j populated: {total} documents in {total_time:.1f}s")
    return {"documents": total}


if __name__ == "__main__":
    setup_neo4j()
