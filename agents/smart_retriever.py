"""
Smart Retriever: Neo4j-first retrieval with ChromaDB + DuckDB fallback.

Workflow:
  1. Parse query → extract company, year, topic keywords
  2. Neo4j → find matching company/year → get section types (table of contents)
  3. Match query to relevant section types
  4. ChromaDB → retrieve chunks filtered by section_ids from Neo4j
  5. DuckDB → retrieve numerical signals/metrics
  6. Attach citations (company, year, doc_id, section, source)
"""

import os
import sys
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

sys.path.append(str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "hyperverge-base")
CHROMADB_PATH = Path(__file__).parent.parent / "data" / "chromadb"
DUCKDB_PATH = Path(__file__).parent.parent / "data" / "duckdb" / "financial_intelligence.db"

# Cache heavy embedding model across requests to reduce /api/query latency.
_EMBED_MODEL = None

# Map query keywords → section types
TOPIC_TO_SECTIONS = {
    "revenue": ["financial_statements", "mda", "segment_breakdown"],
    "profit": ["financial_statements", "mda"],
    "margin": ["financial_statements", "mda"],
    "income": ["financial_statements", "mda"],
    "earnings": ["financial_statements", "mda"],
    "cash flow": ["financial_statements"],
    "debt": ["financial_statements", "footnotes"],
    "risk": ["risk_factors"],
    "competition": ["business_overview", "risk_factors"],
    "strategy": ["business_overview", "mda", "ceo_letter"],
    "product": ["business_overview", "segment_breakdown"],
    "segment": ["segment_breakdown", "mda"],
    "legal": ["legal", "risk_factors"],
    "esg": ["esg"],
    "sustainability": ["esg"],
    "growth": ["mda", "business_overview", "ceo_letter"],
    "acquisition": ["business_overview", "mda", "footnotes"],
    "outlook": ["mda", "ceo_letter"],
    "guidance": ["mda", "ceo_letter"],
    "supply chain": ["risk_factors", "business_overview"],
    "employee": ["business_overview", "esg"],
    "capex": ["financial_statements", "mda"],
    "r&d": ["business_overview", "mda"],
    "research": ["business_overview", "mda"],
}

# Known companies in the graph
COMPANY_ALIASES = {
    "amd": "AMD", "apple": "APPLE", "microsoft": "MICROSOFT", "msft": "MICROSOFT",
    "netflix": "NETFLIX", "nflx": "NETFLIX", "amazon": "AMAZON", "amzn": "AMAZON",
    "walmart": "WALMART", "wmt": "WALMART", "nike": "NIKE", "oracle": "ORACLE",
    "orcl": "ORACLE", "pfizer": "PFIZER", "pfe": "PFIZER", "pepsico": "PEPSICO",
    "pep": "PEPSICO", "verizon": "VERIZON", "vz": "VERIZON",
    "lockheed": "LOCKHEEDMARTIN", "lockheed martin": "LOCKHEEDMARTIN",
    "kraft": "KRAFTHEINZ", "kraft heinz": "KRAFTHEINZ",
    "mgm": "MGMRESORTS", "mgm resorts": "MGMRESORTS",
    "jpmorgan": "JPMORGAN", "jpm": "JPMORGAN", "jp morgan": "JPMORGAN",
    "salesforce": "SALESFORCE", "crm": "SALESFORCE",
    "paypal": "PAYPAL", "pypl": "PAYPAL",
    "adobe": "ADOBE", "adbe": "ADOBE",
    "activision": "ACTIVISIONBLIZZARD", "activision blizzard": "ACTIVISIONBLIZZARD",
    "aes": "AES", "amcor": "AMCOR",
    "ulta": "ULTABEAUTY", "ulta beauty": "ULTABEAUTY",
    "mcdonalds": "MCDONALDS", "mcdonald's": "MCDONALDS",
    "3m": "STATE OF",  # mapped as STATE OF in the data
    "pg&e": "PG", "pge": "PG", "pg": "PG",
}


@dataclass
class Citation:
    company: str
    year: int
    doc_id: str
    section_type: str
    section_id: str = ""
    source_db: str = ""  # "neo4j", "chromadb", "duckdb"

    def __str__(self):
        return f"[{self.company} {self.year} | {self.section_type} | {self.doc_id}]"


@dataclass
class RetrievalResult:
    query: str
    companies_found: List[str] = field(default_factory=list)
    years_found: List[int] = field(default_factory=list)
    matched_sections: List[str] = field(default_factory=list)
    text_results: List[Dict] = field(default_factory=list)
    numerical_results: List[Dict] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)


def parse_query(query: str) -> Dict:
    """Extract company, year, and topic from natural language query."""
    q_lower = query.lower()

    # Extract companies — check all aliases
    companies = []
    # Sort by length DESC so "activision blizzard" matches before "activision"
    for alias, canonical in sorted(COMPANY_ALIASES.items(), key=lambda x: -len(x[0])):
        # Use regex for word boundary matching (handles "Amazon's", "AMAZON", etc.)
        pattern = r'\b' + re.escape(alias) + r'(?:\b|\'s|\s)'
        if re.search(pattern, q_lower):
            if canonical not in companies:
                companies.append(canonical)

    # Extract years
    years = [int(y) for y in re.findall(r'\b(20[12]\d)\b', query)]

    # Match topic → section types
    section_types = set()
    for keyword, sections in TOPIC_TO_SECTIONS.items():
        if keyword in q_lower:
            section_types.update(sections)
    # Default: broad search
    if not section_types:
        section_types = {"business_overview", "mda", "financial_statements", "risk_factors"}

    return {
        "companies": companies,
        "years": years,
        "section_types": list(section_types),
        "raw_query": query,
    }


def step1_neo4j_lookup(parsed: Dict) -> Dict:
    """Step 1: Neo4j → find company/year/sections (table of contents)."""
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    result = {"companies": [], "documents": [], "sections": []}

    with driver.session(database=NEO4J_DATABASE) as session:
        # Use parsed companies, or if none specified, search top 5
        companies = parsed["companies"]
        
        # If no company found in query, still search broadly
        if not companies:
            rows = session.run("MATCH (c:Company) RETURN c.name AS name").values()
            companies = [r[0] for r in rows]
            result["companies"] = companies[:5]  # limit to 5
            logger.info(f"   No company specified, searching: {result['companies']}")
        else:
            result["companies"] = companies
            logger.info(f"   Extracted companies: {companies}")

        # Find matching documents
        for company in result["companies"]:
            cypher = "MATCH (c:Company {name: $company})-[:FILED]->(d:Document)"
            params = {"company": company}
            if parsed["years"]:
                cypher += " WHERE d.year IN $years"
                params["years"] = parsed["years"]
            cypher += " RETURN d.doc_id AS doc_id, d.year AS year, d.doc_type AS doc_type"

            docs = session.run(cypher, **params).data()
            for doc in docs:
                doc["company"] = company
                result["documents"].append(doc)

        # Find matching sections for those documents
        for doc in result["documents"]:
            section_filter = parsed["section_types"]
            rows = session.run("""
                MATCH (d:Document {doc_id: $doc_id})-[:CONTAINS]->(s:Section)
                WHERE s.section_type IN $types
                RETURN s.section_id AS section_id, s.section_type AS section_type,
                       s.text_length AS text_length
                ORDER BY s.text_length DESC
                LIMIT 20
            """, doc_id=doc["doc_id"], types=section_filter).data()

            for row in rows:
                row["company"] = doc["company"]
                row["year"] = doc["year"]
                row["doc_id"] = doc["doc_id"]
                result["sections"].append(row)

    driver.close()
    return result


def step2_chromadb_retrieve(neo4j_result: Dict, query: str, parsed: Dict) -> List[Dict]:
    """Step 2: ChromaDB → get text chunks using section_ids from Neo4j."""
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer

    # Some existing local Chroma DBs were created with older schemas; if that
    # mismatch occurs, continue without vector retrieval instead of raising 500.
    try:
        client = chromadb.PersistentClient(path=str(CHROMADB_PATH), settings=Settings(anonymized_telemetry=False))
    except Exception as e:
        logger.warning(f"  ChromaDB init failed, skipping vector retrieval: {e}")
        return []

    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        _EMBED_MODEL = SentenceTransformer("BAAI/bge-large-en-v1.5")
    query_embedding = _EMBED_MODEL.encode(query).tolist()

    results = []
    section_ids = [s["section_id"] for s in neo4j_result["sections"]]

    # Determine which collections to search based on section types
    target_collections = set()
    for s in neo4j_result["sections"]:
        st = s["section_type"]
        if st in ["business_overview", "risk_factors", "mda", "financial_statements"]:
            target_collections.add(st)
    target_collections.add("all_sections")  # always include as fallback

    try:
        listed = client.list_collections()
        # Chroma APIs may return either collection objects or plain names.
        available = {c.name if hasattr(c, "name") else str(c) for c in listed}
    except Exception as e:
        logger.warning(f"  ChromaDB list_collections failed, skipping vector retrieval: {e}")
        return []

    for col_name in target_collections:
        if col_name not in available:
            continue
        try:
            col = client.get_collection(col_name)
            if col.count() == 0:
                continue
        except Exception as e:
            logger.warning(f"  ChromaDB get_collection({col_name}) failed: {e}")
            continue

        # Build where filter for company/year
        # When multiple companies, query PER COMPANY to guarantee diversity
        query_targets = []  # list of (where_filter, n_results)

        # Use auto-tuned params if available
        try:
            from evals.feedback_tuner import get_params
            _tp = get_params()
            _tuned_top_k = _tp.get("top_k", 10)
        except Exception:
            _tuned_top_k = 10

        if parsed["companies"] and len(parsed["companies"]) > 1:
            per_company_n = max(3, _tuned_top_k // len(parsed["companies"]))
            for company in parsed["companies"]:
                where_clauses = [{"company": company}]
                if parsed["years"]:
                    if len(parsed["years"]) == 1:
                        where_clauses.append({"year": str(parsed["years"][0])})
                    else:
                        where_clauses.append({"year": {"$in": [str(y) for y in parsed["years"]]}})
                w = where_clauses[0] if len(where_clauses) == 1 else {"$and": where_clauses}
                query_targets.append((w, per_company_n))
            logger.info(f"   Per-company queries: {len(query_targets)} companies, {per_company_n} results each")
        else:
            where_clauses = []
            if parsed["companies"]:
                where_clauses.append({"company": parsed["companies"][0]})
            if parsed["years"]:
                if len(parsed["years"]) == 1:
                    where_clauses.append({"year": str(parsed["years"][0])})
                else:
                    where_clauses.append({"year": {"$in": [str(y) for y in parsed["years"]]}})
            w = None
            if len(where_clauses) == 1:
                w = where_clauses[0]
            elif len(where_clauses) > 1:
                w = {"$and": where_clauses}
            query_targets.append((w, _tuned_top_k))

        for where, n_res in query_targets:
            if where:
                logger.info(f"   ChromaDB where filter: {where}")

            try:
                kwargs = {
                    "query_embeddings": [query_embedding],
                    "n_results": min(n_res, col.count()),
                    "include": ["documents", "metadatas", "distances"],
                }
                if where:
                    kwargs["where"] = where

                res = col.query(**kwargs)

                docs = res["documents"][0] if res["documents"] else []
                metas = res["metadatas"][0] if res["metadatas"] else []
                dists = res["distances"][0] if res["distances"] else []
                ids = res["ids"][0] if res["ids"] else []

                for doc, meta, dist, chunk_id in zip(docs, metas, dists, ids):
                    results.append({
                        "text": doc,
                        "relevance": round(1 - dist, 3),
                        "collection": col_name,
                        "chunk_id": chunk_id,
                        "company": meta.get("company", ""),
                        "year": meta.get("year", ""),
                        "doc_id": meta.get("doc_id", ""),
                        "section_type": meta.get("section_type", ""),
                        "section_id": meta.get("section_id", ""),
                        "neo4j_matched": meta.get("section_id", "") in section_ids,
                    })
            except Exception as e:
                logger.warning(f"  ChromaDB {col_name} error: {e}")

    # Sort by relevance, prioritize neo4j-matched sections
    results.sort(key=lambda x: (x["neo4j_matched"], x["relevance"]), reverse=True)
    return results


def step3_duckdb_numericals(parsed: Dict) -> List[Dict]:
    """Step 3: DuckDB → get numerical signals and table metadata."""
    import duckdb

    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    results = []

    # Signals
    q = "SELECT signal_type, signal_text, context, company, year, doc_id, section_id FROM signals WHERE 1=1"
    params = []
    if parsed["companies"]:
        q += " AND company IN (" + ",".join(["?"] * len(parsed["companies"])) + ")"
        params.extend(parsed["companies"])
    if parsed["years"]:
        q += " AND year IN (" + ",".join(["?"] * len(parsed["years"])) + ")"
        params.extend(parsed["years"])
    q += " LIMIT 20"

    rows = conn.execute(q, params).fetchall()
    cols = ["signal_type", "signal_text", "context", "company", "year", "doc_id", "section_id"]
    for row in rows:
        d = dict(zip(cols, row))
        d["source"] = "duckdb_signals"
        results.append(d)

    # Tables metadata (for numerical context)
    q2 = "SELECT table_type, caption, company, year, doc_id, row_count, column_count FROM tables_metadata WHERE 1=1"
    params2 = []
    if parsed["companies"]:
        q2 += " AND company IN (" + ",".join(["?"] * len(parsed["companies"])) + ")"
        params2.extend(parsed["companies"])
    if parsed["years"]:
        q2 += " AND year IN (" + ",".join(["?"] * len(parsed["years"])) + ")"
        params2.extend(parsed["years"])

    # Filter by query keywords in caption
    keywords = [w for w in parsed["raw_query"].lower().split()
                if len(w) > 3 and w.upper() not in parsed["companies"]]
    if keywords:
        kw_clauses = " OR ".join(["caption ILIKE ?"] * min(len(keywords), 3))
        q2 += f" AND ({kw_clauses})"
        params2.extend([f"%{kw}%" for kw in keywords[:3]])

    q2 += " LIMIT 10"
    rows2 = conn.execute(q2, params2).fetchall()
    cols2 = ["table_type", "caption", "company", "year", "doc_id", "row_count", "column_count"]
    for row in rows2:
        d = dict(zip(cols2, row))
        d["source"] = "duckdb_tables"
        results.append(d)

    conn.close()
    return results


def build_citations(text_results: List[Dict], numerical_results: List[Dict]) -> List[Citation]:
    """Build citation list from all results (unique by doc_id)."""
    citations = []
    seen_docs = set()

    # Add text results — one citation per unique document
    for r in text_results:
        doc_id = r.get("doc_id", "")
        if doc_id and doc_id not in seen_docs:
            seen_docs.add(doc_id)
            citations.append(Citation(
                company=r["company"],
                year=int(r["year"]) if r.get("year") else 0,
                doc_id=doc_id,
                section_type=r.get("section_type", ""),
                section_id=r.get("section_id", ""),
                source_db="chromadb",
            ))

    # Add numerical results — one citation per unique document
    for r in numerical_results:
        doc_id = r.get("doc_id", "")
        if doc_id and doc_id not in seen_docs:
            seen_docs.add(doc_id)
            citations.append(Citation(
                company=r["company"],
                year=r.get("year", 0),
                doc_id=r.get("doc_id", ""),
                section_type=r.get("signal_type", r.get("table_type", "")),
                section_id=r.get("section_id", ""),
                source_db="duckdb",
            ))

    return citations


def smart_retrieve(query: str) -> RetrievalResult:
    """Full retrieval pipeline: Neo4j → ChromaDB → DuckDB → Citations."""
    result = RetrievalResult(query=query)

    # Step 0: Parse query
    logger.info(f"\n{'='*80}")
    logger.info(f"🔍 SMART RETRIEVER")
    logger.info(f"   Query: '{query}'")
    logger.info(f"{'='*80}")

    parsed = parse_query(query)
    logger.info(f"\n📋 Parsed:")
    logger.info(f"   Companies: {parsed['companies'] or '(auto-detect)'}")
    logger.info(f"   Years: {parsed['years'] or '(all)'}")
    logger.info(f"   Section types: {parsed['section_types']}")

    # Step 1: Neo4j — graph lookup
    logger.info(f"\n🔗 Step 1: Neo4j Graph Lookup")
    logger.info("-" * 60)
    neo4j_result = step1_neo4j_lookup(parsed)

    result.companies_found = [d["company"] for d in neo4j_result["documents"]]
    result.years_found = list(set(d["year"] for d in neo4j_result["documents"]))
    result.matched_sections = list(set(s["section_type"] for s in neo4j_result["sections"]))
    result.neo4j_documents_count = len(neo4j_result["documents"])  # Store actual Neo4j count

    logger.info(f"   Documents: {len(neo4j_result['documents'])}")
    for d in neo4j_result["documents"]:
        logger.info(f"     • {d['company']} {d['year']} ({d['doc_type']})")
    logger.info(f"   Sections matched: {len(neo4j_result['sections'])}")
    section_summary = {}
    for s in neo4j_result["sections"]:
        key = s["section_type"]
        section_summary[key] = section_summary.get(key, 0) + 1
    for st, cnt in sorted(section_summary.items(), key=lambda x: -x[1]):
        logger.info(f"     • {st}: {cnt} sections")

    # Step 2: ChromaDB — semantic retrieval
    logger.info(f"\n📚 Step 2: ChromaDB Semantic Retrieval")
    logger.info("-" * 60)
    text_results = step2_chromadb_retrieve(neo4j_result, query, parsed)
    result.text_results = text_results[:15]

    logger.info(f"   Results: {len(text_results)}")
    for i, r in enumerate(text_results[:10], 1):
        matched = "✓ neo4j-matched" if r["neo4j_matched"] else ""
        logger.info(f"   {i}. [{r['relevance']:.2f}] {r['company']} {r['year']} | {r['section_type']} | {r['collection']} {matched}")
        logger.info(f"      {r['text'][:120]}...")

    # Step 3: DuckDB — numerical data
    logger.info(f"\n📊 Step 3: DuckDB Numerical Data")
    logger.info("-" * 60)
    numerical_results = step3_duckdb_numericals(parsed)
    result.numerical_results = numerical_results

    signals = [r for r in numerical_results if r["source"] == "duckdb_signals"]
    tables = [r for r in numerical_results if r["source"] == "duckdb_tables"]
    logger.info(f"   Signals: {len(signals)}")
    for s in signals[:5]:
        ctx = (s.get("context") or "")[:80]
        logger.info(f"     • [{s['signal_type']}] {s['signal_text']} — {ctx}")
    logger.info(f"   Tables: {len(tables)}")
    for t in tables[:5]:
        logger.info(f"     • [{t['table_type']}] {t.get('caption', '')[:80]} ({t['row_count']}x{t['column_count']})")

    # Step 4: Citations
    result.citations = build_citations(text_results, numerical_results)
    logger.info(f"\n📎 Citations ({len(result.citations)}):")
    for c in result.citations:
        logger.info(f"   {c}")

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 RETRIEVAL SUMMARY")
    logger.info(f"   Neo4j:    {len(neo4j_result['documents'])} docs, {len(neo4j_result['sections'])} sections")
    logger.info(f"   ChromaDB: {len(text_results)} text chunks")
    logger.info(f"   DuckDB:   {len(signals)} signals, {len(tables)} tables")
    logger.info(f"   Citations: {len(result.citations)}")
    logger.info(f"{'='*80}\n")

    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="What was AMD's revenue in 2021?")
    args = parser.parse_args()
    smart_retrieve(args.query)
