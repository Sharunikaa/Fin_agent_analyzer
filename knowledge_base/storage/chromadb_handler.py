"""
ChromaDB Handler: Store knowledge insights in ChromaDB for semantic search
"""

import chromadb
import logging
from typing import Dict, List
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

from knowledge_base.config import CHROMADB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_chromadb():
    """Initialize ChromaDB and create collections."""
    try:
        client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
        
        # Try to get collection, if it fails, create it
        try:
            collection = client.get_collection("knowledge_insights")
            logger.info("✅ Using existing ChromaDB collection")
        except:
            # Collection doesn't exist, create it
            collection = client.create_collection(
                name="knowledge_insights",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("✅ Created new ChromaDB collection")
        
        return client
    except Exception as e:
        logger.error(f"Error initializing ChromaDB: {e}")
        # Continue without ChromaDB
        return None


def store_insights(
    kpis: Dict,
    risks: Dict,
    promises: Dict,
    sentiment: Dict,
    doc_id: str
):
    """Store all insights in ChromaDB."""
    try:
        client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
        
        try:
            collection = client.get_collection("knowledge_insights")
        except:
            collection = client.create_collection(
                name="knowledge_insights",
                metadata={"hnsw:space": "cosine"}
            )
        
        company = kpis.get('company', 'Unknown')
        fiscal_year = kpis.get('fiscal_year')
        
        documents = []
        metadatas = []
        ids = []
        
        # KPI insights
        for metric, data in kpis.items():
            if metric not in ['company', 'fiscal_year', 'extraction_metadata'] and isinstance(data, dict):
                if 'value' in data and data['value']:
                    doc_text = f"{company} {fiscal_year}: {metric} = {data['value']} {data.get('unit', '')}"
                    documents.append(doc_text)
                    metadatas.append({
                        'type': 'kpi',
                        'company': company,
                        'fiscal_year': fiscal_year,
                        'metric': metric,
                        'value': str(data['value'])
                    })
                    ids.append(f"{doc_id}_kpi_{metric}")
        
        # Risk insights
        for i, risk in enumerate(risks.get('risks', [])):
            doc_text = f"{company} {fiscal_year} Risk: {risk.get('description', '')} (Severity: {risk.get('severity', '')})"
            documents.append(doc_text)
            metadatas.append({
                'type': 'risk',
                'company': company,
                'fiscal_year': fiscal_year,
                'category': risk.get('category', ''),
                'severity': risk.get('severity', '')
            })
            ids.append(f"{doc_id}_risk_{i}")
        
        # Promise insights
        for i, promise in enumerate(promises.get('promises', [])):
            doc_text = f"{company} {fiscal_year} Promise: {promise.get('text', '')} (Target: {promise.get('target_year', '')})"
            documents.append(doc_text)
            metadatas.append({
                'type': 'promise',
                'company': company,
                'fiscal_year': fiscal_year,
                'category': promise.get('category', ''),
                'target_year': str(promise.get('target_year', ''))
            })
            ids.append(f"{doc_id}_promise_{i}")
        
        # Sentiment insights
        doc_text = f"{company} {fiscal_year} Sentiment: {sentiment.get('overall_sentiment', '')} - {sentiment.get('tone_summary', '')}"
        documents.append(doc_text)
        metadatas.append({
            'type': 'sentiment',
            'company': company,
            'fiscal_year': fiscal_year,
            'sentiment': sentiment.get('overall_sentiment', '')
        })
        ids.append(f"{doc_id}_sentiment")
        
        # Add to collection
        if documents:
            try:
                collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
                logger.info(f"✅ Stored {len(documents)} insights in ChromaDB for {company}")
            except Exception as e:
                logger.warning(f"Could not store insights in ChromaDB: {e}")
    except Exception as e:
        logger.warning(f"ChromaDB not available: {e}")


def query_insights(query_text: str, n_results: int = 5):
    """Query ChromaDB for relevant insights."""
    client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
    collection = client.get_collection("knowledge_insights")
    
    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return results
    except Exception as e:
        logger.error(f"Error querying insights: {e}")
        return None


if __name__ == "__main__":
    init_chromadb()
    logger.info("ChromaDB handler ready")
