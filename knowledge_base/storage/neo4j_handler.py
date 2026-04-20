"""
Neo4j Handler: Store knowledge graph in Neo4j
"""

import logging
from typing import Dict
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

from knowledge_base.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional Neo4j import - graceful handling if not installed
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("Neo4j driver not installed - graph storage will be skipped")


def init_neo4j():
    """Initialize Neo4j and create constraints."""
    if not NEO4J_AVAILABLE:
        logger.warning("Neo4j not available")
        return None
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        with driver.session(database=NEO4J_DATABASE) as session:
            # Create constraints
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (k:KPI) REQUIRE k.kpi_id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (r:Risk) REQUIRE r.risk_id IS UNIQUE")
        
        logger.info("✅ Neo4j initialized with constraints")
        return driver
    except Exception as e:
        logger.error(f"Error initializing Neo4j: {e}")
        return None


def store_knowledge_graph(
    company: str,
    fiscal_year: int,
    doc_id: str,
    kpis: Dict,
    risks: Dict,
    promises: Dict
):
    """Store knowledge graph in Neo4j."""
    if not NEO4J_AVAILABLE:
        logger.warning("Neo4j not available - skipping graph storage")
        return
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        with driver.session(database=NEO4J_DATABASE) as session:
            # Create company node
            session.run("""
                MERGE (c:Company {name: $company})
                SET c.sector = 'Technology', c.updated_at = timestamp()
            """, company=company)
            
            # Create year node
            session.run("""
                MERGE (y:Year {year: $fiscal_year})
            """, fiscal_year=fiscal_year)
            
            # Create document node
            session.run("""
                MERGE (d:Document {doc_id: $doc_id})
                SET d.company = $company, d.fiscal_year = $fiscal_year
            """, doc_id=doc_id, company=company, fiscal_year=fiscal_year)
            
            # Link Company -> Year
            session.run("""
                MATCH (c:Company {name: $company})
                MATCH (y:Year {year: $fiscal_year})
                MERGE (c)-[:YEAR]->(y)
            """, company=company, fiscal_year=fiscal_year)
            
            # Link Company -> Document
            session.run("""
                MATCH (c:Company {name: $company})
                MATCH (d:Document {doc_id: $doc_id})
                MERGE (c)-[:HAS_DOCUMENT]->(d)
            """, company=company, doc_id=doc_id)
            
            # Create KPI nodes
            for metric, data in kpis.items():
                if metric not in ['company', 'fiscal_year', 'extraction_metadata'] and isinstance(data, dict) and 'value' in data:
                    kpi_id = f"{doc_id}_{metric}"
                    session.run("""
                        MERGE (k:KPI {kpi_id: $kpi_id})
                        SET k.metric = $metric, k.value = $value, k.company = $company, k.fiscal_year = $fiscal_year
                    """, kpi_id=kpi_id, metric=metric, value=data.get('value'), company=company, fiscal_year=fiscal_year)
                    
                    # Link Document -> KPI
                    session.run("""
                        MATCH (d:Document {doc_id: $doc_id})
                        MATCH (k:KPI {kpi_id: $kpi_id})
                        MERGE (d)-[:CONTAINS_KPI]->(k)
                    """, doc_id=doc_id, kpi_id=kpi_id)
            
            # Create Risk nodes
            for i, risk in enumerate(risks.get('risks', [])):
                risk_id = f"{doc_id}_risk_{i}"
                session.run("""
                    MERGE (r:Risk {risk_id: $risk_id})
                    SET r.category = $category, r.description = $description, r.severity = $severity,
                        r.company = $company, r.fiscal_year = $fiscal_year
                """, risk_id=risk_id, category=risk.get('category', ''),
                    description=risk.get('description', ''), severity=risk.get('severity', ''),
                    company=company, fiscal_year=fiscal_year)
                
                # Link Document -> Risk
                session.run("""
                    MATCH (d:Document {doc_id: $doc_id})
                    MATCH (r:Risk {risk_id: $risk_id})
                    MERGE (d)-[:CONTAINS_RISK]->(r)
                """, doc_id=doc_id, risk_id=risk_id)
        
        logger.info(f"✅ Stored knowledge graph for {company} {fiscal_year}")
        driver.close()
        
    except Exception as e:
        logger.error(f"Error storing knowledge graph: {e}")


if __name__ == "__main__":
    if NEO4J_AVAILABLE:
        init_neo4j()
        logger.info("Neo4j handler ready")
    else:
        logger.warning("Neo4j handler available but Neo4j driver not installed")
