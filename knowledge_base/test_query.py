"""
Knowledge Base Unified Query Test

Query all three storage backends (Neo4j, ChromaDB, DuckDB) for comprehensive results.

Usage:
    python knowledge_base/test_query.py --query "revenue growth"
    python knowledge_base/test_query.py --company "AMD" --year 2021
    python knowledge_base/test_query.py --interactive
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Optional
import argparse

sys.path.append(str(Path(__file__).parent.parent))

from knowledge_base.storage.duckdb_handler import init_duckdb
from knowledge_base.storage.chromadb_handler import init_chromadb
from knowledge_base.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE, DUCKDB_PATH, CHROMADB_PATH

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False


class UnifiedQueryEngine:
    """Query across all three storage backends."""

    def __init__(self):
        self.neo4j_driver = None
        self.embed_model = None
        self._init_backends()

    def _init_backends(self):
        """Initialize all backends."""
        logger.info("🔧 Initializing storage backends...\n")

        # DuckDB
        try:
            init_duckdb()
            logger.info("✅ DuckDB ready")
        except Exception as e:
            logger.warning(f"⚠️  DuckDB error: {e}")

        # ChromaDB
        try:
            init_chromadb()
            from sentence_transformers import SentenceTransformer
            self.embed_model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("✅ ChromaDB ready")
        except Exception as e:
            logger.warning(f"⚠️  ChromaDB error: {e}")

        # Neo4j
        if NEO4J_AVAILABLE:
            try:
                self.neo4j_driver = GraphDatabase.driver(
                    NEO4J_URI,
                    auth=(NEO4J_USER, NEO4J_PASSWORD),
                )
                with self.neo4j_driver.session(database=NEO4J_DATABASE) as session:
                    session.run("RETURN 1")
                logger.info("✅ Neo4j ready")
            except Exception as e:
                logger.warning(f"⚠️  Neo4j unavailable: {e}")
                self.neo4j_driver = None
        else:
            logger.warning("⚠️  Neo4j driver not installed")

        logger.info("✅ All backends initialized")

    # ── DuckDB ───────────────────────────────────────────────────────────

    def query_duckdb(self, company: str = None, fiscal_year: int = None,
                     query_text: str = None) -> Dict:
        """Query structured data from DuckDB (populated tables)."""
        logger.info("📊 DuckDB (Structured Data)")
        logger.info("-" * 80)

        import duckdb
        results = {'documents': [], 'signals': [], 'sections': [], 'tables': [],
                   'kpis': [], 'risks': [], 'promises': [], 'anomalies': []}

        try:
            conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)

            # --- Documents ---
            q = "SELECT * FROM documents WHERE 1=1"
            p = []
            if company:
                q += " AND company ILIKE ?"
                p.append(f"%{company}%")
            if fiscal_year:
                q += " AND year = ?"
                p.append(fiscal_year)
            rows = (conn.execute(q, p) if p else conn.execute(q)).fetchall()
            cols = [d[0] for d in conn.description]
            results['documents'] = [dict(zip(cols, r)) for r in rows]
            if results['documents']:
                logger.info(f"  Documents: {len(results['documents'])} found")
                for d in results['documents'][:5]:
                    logger.info(f"    • {d['company']} {d['year']} ({d['doc_type']})")

            # --- Signals (search signal_text + context) ---
            q = "SELECT * FROM signals WHERE 1=1"
            p = []
            if company:
                q += " AND company ILIKE ?"
                p.append(f"%{company}%")
            if fiscal_year:
                q += " AND year = ?"
                p.append(fiscal_year)
            if query_text:
                q += " AND (signal_text ILIKE ? OR context ILIKE ?)"
                p.extend([f"%{query_text}%", f"%{query_text}%"])
            q += " LIMIT 20"
            rows = (conn.execute(q, p) if p else conn.execute(q)).fetchall()
            cols = [d[0] for d in conn.description]
            results['signals'] = [dict(zip(cols, r)) for r in rows]
            if results['signals']:
                logger.info(f"  Signals: {len(results['signals'])} found")
                for s in results['signals'][:5]:
                    ctx = (s.get('context') or '')[:80]
                    logger.info(f"    • [{s['signal_type']}] {s['company']} {s['year']}: {s['signal_text']} — {ctx}")

            # --- Sections metadata (filter by company/year only, not free text) ---
            q = "SELECT * FROM sections_metadata WHERE 1=1"
            p = []
            if company:
                q += " AND company ILIKE ?"
                p.append(f"%{company}%")
            if fiscal_year:
                q += " AND year = ?"
                p.append(fiscal_year)
            q += " LIMIT 20"
            rows = (conn.execute(q, p) if p else conn.execute(q)).fetchall()
            cols = [d[0] for d in conn.description]
            results['sections'] = [dict(zip(cols, r)) for r in rows]
            if results['sections']:
                logger.info(f"  Sections: {len(results['sections'])} found")
                for s in results['sections'][:5]:
                    logger.info(f"    • {s['company']} {s['year']}: {s['section_type']} (level {s.get('level', '?')})")

            # --- Tables metadata ---
            q = "SELECT table_type, company, year, caption, row_count, column_count FROM tables_metadata WHERE 1=1"
            p = []
            if company:
                q += " AND company ILIKE ?"
                p.append(f"%{company}%")
            if fiscal_year:
                q += " AND year = ?"
                p.append(fiscal_year)
            if query_text:
                q += " AND (table_type ILIKE ? OR caption ILIKE ?)"
                p.extend([f"%{query_text}%", f"%{query_text}%"])
            q += " LIMIT 20"
            rows = (conn.execute(q, p) if p else conn.execute(q)).fetchall()
            cols = [d[0] for d in conn.description]
            results['tables'] = [dict(zip(cols, r)) for r in rows]
            if results['tables']:
                logger.info(f"  Tables: {len(results['tables'])} found")
                for t in results['tables'][:5]:
                    cap = (t.get('caption') or t['table_type'])[:80]
                    logger.info(f"    • {t['company']} {t['year']}: {cap} ({t['row_count']}x{t['column_count']})")

            # --- Knowledge tables (if populated) ---
            for tbl, key in [('knowledge_kpis', 'kpis'), ('knowledge_risks', 'risks'),
                             ('knowledge_promises', 'promises'), ('knowledge_anomalies', 'anomalies')]:
                try:
                    q = f"SELECT * FROM {tbl} WHERE 1=1"
                    p = []
                    if company:
                        q += " AND company ILIKE ?"
                        p.append(f"%{company}%")
                    if fiscal_year:
                        q += " AND fiscal_year = ?"
                        p.append(fiscal_year)
                    q += " LIMIT 20"
                    rows = (conn.execute(q, p) if p else conn.execute(q)).fetchall()
                    if rows:
                        cols = [d[0] for d in conn.description]
                        results[key] = [dict(zip(cols, r)) for r in rows]
                        logger.info(f"  {key.title()}: {len(results[key])} found")
                except Exception:
                    pass

            if not any(results.values()):
                logger.info("  No results found in DuckDB")

            conn.close()
        except Exception as e:
            logger.error(f"DuckDB error: {e}")

        return results

    # ── ChromaDB ─────────────────────────────────────────────────────────

    def query_chromadb(self, query_text: str, n_results: int = 5) -> Dict:
        """Query semantic search across ALL ChromaDB collections."""
        logger.info("\n🔍 ChromaDB (Semantic Search)")
        logger.info("-" * 80)

        import chromadb
        all_results = {}

        try:
            client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
            collection_names = client.list_collections()

            # Encode query with the same model used to build the collections
            if self.embed_model is None:
                logger.warning("  Embedding model not loaded — cannot query ChromaDB")
                return {}
            query_embedding = self.embed_model.encode(query_text).tolist()

            for col_name in collection_names:
                col = client.get_collection(col_name)
                if col.count() == 0:
                    continue
                try:
                    res = col.query(
                        query_embeddings=[query_embedding],
                        n_results=min(n_results, col.count()),
                    )
                    docs = res['documents'][0] if res['documents'] else []
                    metas = res['metadatas'][0] if res['metadatas'] else []
                    dists = res['distances'][0] if res['distances'] else []

                    if docs:
                        all_results[col_name] = {
                            'documents': docs, 'metadata': metas, 'distances': dists
                        }
                        logger.info(f"\n  📂 Collection: {col_name} ({col.count()} total)")
                        for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists), 1):
                            relevance = 1 - dist
                            logger.info(f"    {i}. (relevance: {relevance:.2f})")
                            logger.info(f"       {doc[:120]}...")
                            if meta:
                                parts = []
                                if 'company' in meta:
                                    parts.append(meta['company'])
                                if 'year' in meta:
                                    parts.append(str(meta['year']))
                                if 'type' in meta:
                                    parts.append(meta['type'])
                                if parts:
                                    logger.info(f"       [{' | '.join(parts)}]")
                except Exception as e:
                    logger.warning(f"  ⚠️  {col_name}: {e}")

            if not all_results:
                logger.info(f"  Query: '{query_text}'")
                logger.info("  No results found across any collection")

        except Exception as e:
            logger.error(f"ChromaDB error: {e}")

        return all_results

    # ── Neo4j ────────────────────────────────────────────────────────────

    def query_neo4j(self, company: str = None, fiscal_year: int = None) -> Dict:
        """Query knowledge graph from Neo4j."""
        logger.info("\n🔗 Neo4j (Knowledge Graph)")
        logger.info("-" * 80)

        if not self.neo4j_driver:
            logger.warning("  Neo4j not available (server not running or driver not installed)")
            return {}

        try:
            results = {'companies': [], 'documents': [], 'relationships': []}

            with self.neo4j_driver.session(database=NEO4J_DATABASE) as session:
                try:
                    nodes = session.run("MATCH (c:Company) RETURN c.name as name LIMIT 10").data()
                    if nodes:
                        results['companies'] = [n['name'] for n in nodes]
                        logger.info(f"  Companies: {len(results['companies'])} found")
                        for name in results['companies']:
                            logger.info(f"    • {name}")
                except Exception as e:
                    logger.warning(f"  Company query error: {e}")

                if company:
                    try:
                        docs = session.run("""
                            MATCH (c:Company {name: $company})-[:FILED]->(d:Document)
                            RETURN d.doc_id as doc_id, d.year as year LIMIT 10
                        """, company=company).data()
                        if docs:
                            results['documents'] = docs
                            logger.info(f"\n  Documents for {company}: {len(docs)} found")
                            for doc in docs:
                                logger.info(f"    • {doc['doc_id']} ({doc['year']})")
                    except Exception as e:
                        logger.warning(f"  Document query error: {e}")

                try:
                    rels = session.run("""
                        MATCH ()-[r]->()
                        RETURN type(r) as relationship, count(*) as count
                    """).data()
                    if rels:
                        results['relationships'] = rels
                        logger.info(f"\n  Relationships: {len(rels)} types")
                        for rel in rels:
                            logger.info(f"    • {rel['relationship']}: {rel['count']} edges")
                except Exception as e:
                    logger.warning(f"  Relationship query error: {e}")

            return results
        except Exception as e:
            logger.error(f"Neo4j error: {e}")
            return {}

    # ── Unified ──────────────────────────────────────────────────────────

    def unified_query(self, query_text: str = None, company: str = None,
                      fiscal_year: int = None) -> None:
        """Run unified query across all backends."""
        logger.info("\n" + "=" * 80)
        logger.info("🔍 UNIFIED KNOWLEDGE BASE QUERY")
        if query_text:
            logger.info(f"   Query: '{query_text}'")
        if company:
            logger.info(f"   Company: {company}")
        if fiscal_year:
            logger.info(f"   Year: {fiscal_year}")
        logger.info("=" * 80 + "\n")

        # DuckDB
        duckdb_results = self.query_duckdb(company=company, fiscal_year=fiscal_year,
                                           query_text=query_text)

        # ChromaDB
        chromadb_results = {}
        if query_text:
            chromadb_results = self.query_chromadb(query_text)

        # Neo4j
        neo4j_results = self.query_neo4j(company=company, fiscal_year=fiscal_year)

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 SUMMARY")
        logger.info("=" * 80)
        logger.info(f"DuckDB:   {len(duckdb_results.get('documents', []))} docs, "
                     f"{len(duckdb_results.get('signals', []))} signals, "
                     f"{len(duckdb_results.get('sections', []))} sections")
        if chromadb_results:
            total_hits = sum(len(v['documents']) for v in chromadb_results.values())
            logger.info(f"ChromaDB: {total_hits} results across {len(chromadb_results)} collections")
        else:
            logger.info("ChromaDB: no query / no results")
        logger.info(f"Neo4j:    {len(neo4j_results.get('companies', []))} companies, "
                     f"{len(neo4j_results.get('documents', []))} documents, "
                     f"{len(neo4j_results.get('relationships', []))} relationship types")
        logger.info("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Knowledge Base Unified Query Test")
    parser.add_argument("--query", type=str, help="Semantic search query")
    parser.add_argument("--company", type=str, help="Filter by company")
    parser.add_argument("--year", type=int, help="Filter by fiscal year")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")

    args = parser.parse_args()
    engine = UnifiedQueryEngine()

    if args.interactive:
        logger.info("\n📚 Interactive Query Mode")
        logger.info("Type 'exit' to quit\n")
        while True:
            user_input = input("Enter query (or 'company:AMD year:2021'): ").strip()
            if user_input.lower() == 'exit':
                break
            company, year, query_text = None, None, user_input
            if "company:" in user_input:
                parts = user_input.split("company:")
                query_text = parts[0].strip()
                company = parts[1].split()[0]
            if "year:" in user_input:
                parts = user_input.split("year:")
                try:
                    year = int(parts[1].split()[0])
                except ValueError:
                    pass
            engine.unified_query(query_text=query_text or None, company=company, fiscal_year=year)
    else:
        if args.query or args.company or args.year:
            engine.unified_query(query_text=args.query, company=args.company, fiscal_year=args.year)
        else:
            logger.info("No query specified. Running discovery...\n")
            engine.unified_query()


if __name__ == "__main__":
    main()
