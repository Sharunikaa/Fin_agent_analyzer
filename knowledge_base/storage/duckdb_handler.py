"""
DuckDB Handler: Store extracted knowledge in DuckDB
"""

import duckdb
import logging
from typing import Dict, List
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

from knowledge_base.config import DUCKDB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_duckdb():
    """Initialize DuckDB and create knowledge tables."""
    conn = duckdb.connect(str(DUCKDB_PATH))
    
    # Create KPIs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_kpis (
            kpi_id VARCHAR PRIMARY KEY,
            doc_id VARCHAR,
            company VARCHAR,
            fiscal_year INTEGER,
            metric_name VARCHAR,
            value DOUBLE,
            unit VARCHAR,
            page_ref VARCHAR,
            extraction_confidence DOUBLE,
            created_at TIMESTAMP
        )
    """)
    
    # Create risks table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_risks (
            risk_id VARCHAR PRIMARY KEY,
            doc_id VARCHAR,
            company VARCHAR,
            fiscal_year INTEGER,
            risk_category VARCHAR,
            risk_description TEXT,
            severity VARCHAR,
            language_quote TEXT,
            page_ref VARCHAR,
            is_new_vs_prior_year BOOLEAN,
            language_intensity VARCHAR,
            created_at TIMESTAMP
        )
    """)
    
    # Create promises table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_promises (
            promise_id VARCHAR PRIMARY KEY,
            doc_id VARCHAR,
            company VARCHAR,
            fiscal_year INTEGER,
            promise_text TEXT,
            exact_quote TEXT,
            category VARCHAR,
            target_year INTEGER,
            is_quantified BOOLEAN,
            page_ref VARCHAR,
            delivery_status VARCHAR,
            created_at TIMESTAMP
        )
    """)
    
    # Create anomalies table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_anomalies (
            anomaly_id VARCHAR PRIMARY KEY,
            doc_id VARCHAR,
            company VARCHAR,
            fiscal_year INTEGER,
            anomaly_type VARCHAR,
            description TEXT,
            magnitude VARCHAR,
            severity VARCHAR,
            page_ref VARCHAR,
            created_at TIMESTAMP
        )
    """)
    
    conn.close()
    logger.info("✅ DuckDB initialized with knowledge tables")


def store_kpis(kpis: Dict, doc_id: str):
    """Store KPIs in DuckDB."""
    conn = duckdb.connect(str(DUCKDB_PATH))
    
    company = kpis.get('company', 'Unknown')
    fiscal_year = kpis.get('fiscal_year')
    
    for metric_name, metric_data in kpis.items():
        if metric_name in ['company', 'fiscal_year', 'extraction_metadata']:
            continue
        
        if isinstance(metric_data, dict) and 'value' in metric_data:
            kpi_id = f"{doc_id}_{metric_name}"
            
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO knowledge_kpis 
                    (kpi_id, doc_id, company, fiscal_year, metric_name, value, unit, page_ref, extraction_confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    kpi_id,
                    doc_id,
                    company,
                    fiscal_year,
                    metric_name,
                    metric_data.get('value'),
                    metric_data.get('unit', 'unknown'),
                    metric_data.get('page_ref', ''),
                    0.85
                ))
            except Exception as e:
                logger.error(f"Error storing KPI {metric_name}: {e}")
    
    conn.close()
    logger.info(f"✅ Stored KPIs for {company} {fiscal_year}")


def store_risks(risks: Dict, doc_id: str):
    """Store risks in DuckDB."""
    conn = duckdb.connect(str(DUCKDB_PATH))
    
    company = risks.get('company', 'Unknown')
    fiscal_year = risks.get('fiscal_year')
    
    for i, risk in enumerate(risks.get('risks', [])):
        risk_id = f"{doc_id}_risk_{i}"
        
        try:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_risks
                (risk_id, doc_id, company, fiscal_year, risk_category, risk_description, 
                 severity, language_quote, page_ref, is_new_vs_prior_year, language_intensity, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                risk_id,
                doc_id,
                company,
                fiscal_year,
                risk.get('category', 'other'),
                risk.get('description', ''),
                risk.get('severity', 'medium'),
                risk.get('quote', ''),
                risk.get('page_ref', ''),
                risk.get('is_new_vs_prior_year', False),
                risk.get('language_intensity', 'moderate')
            ))
        except Exception as e:
            logger.error(f"Error storing risk: {e}")
    
    conn.close()
    logger.info(f"✅ Stored {len(risks.get('risks', []))} risks for {company}")


def store_promises(promises: Dict, doc_id: str):
    """Store promises in DuckDB."""
    conn = duckdb.connect(str(DUCKDB_PATH))
    
    company = promises.get('company', 'Unknown')
    fiscal_year = promises.get('fiscal_year')
    
    for i, promise in enumerate(promises.get('promises', [])):
        promise_id = f"{doc_id}_promise_{i}"
        
        try:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_promises
                (promise_id, doc_id, company, fiscal_year, promise_text, exact_quote,
                 category, target_year, is_quantified, page_ref, delivery_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                promise_id,
                doc_id,
                company,
                fiscal_year,
                promise.get('text', ''),
                promise.get('exact_quote', ''),
                promise.get('category', 'other'),
                promise.get('target_year'),
                promise.get('is_quantified', False),
                promise.get('page_ref', ''),
                promise.get('delivery_status', 'pending')
            ))
        except Exception as e:
            logger.error(f"Error storing promise: {e}")
    
    conn.close()
    logger.info(f"✅ Stored {len(promises.get('promises', []))} promises for {company}")


def store_anomalies(anomalies: Dict, doc_id: str):
    """Store anomalies in DuckDB."""
    conn = duckdb.connect(str(DUCKDB_PATH))
    
    company = anomalies.get('company', 'Unknown')
    fiscal_year = anomalies.get('fiscal_year')
    
    for i, anomaly in enumerate(anomalies.get('anomalies', [])):
        anomaly_id = f"{doc_id}_anomaly_{i}"
        
        try:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_anomalies
                (anomaly_id, doc_id, company, fiscal_year, anomaly_type, description, magnitude, severity, page_ref, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                anomaly_id,
                doc_id,
                company,
                fiscal_year,
                anomaly.get('type', 'unknown'),
                anomaly.get('description', ''),
                anomaly.get('magnitude', ''),
                anomaly.get('severity', 'medium'),
                anomaly.get('page_ref', '')
            ))
        except Exception as e:
            logger.error(f"Error storing anomaly: {e}")
    
    conn.close()
    logger.info(f"✅ Stored {len(anomalies.get('anomalies', []))} anomalies for {company}")


def query_kpis(company: str = None, fiscal_year: int = None):
    """Query KPIs from DuckDB."""
    conn = duckdb.connect(str(DUCKDB_PATH))
    
    query = "SELECT * FROM knowledge_kpis WHERE 1=1"
    params = []
    
    if company:
        query += " AND company = ?"
        params.append(company)
    
    if fiscal_year:
        query += " AND fiscal_year = ?"
        params.append(fiscal_year)
    
    result = conn.execute(query, params).fetchdf() if params else conn.execute(query).fetchdf()
    conn.close()
    return result


if __name__ == "__main__":
    init_duckdb()
    logger.info("DuckDB handler ready")
