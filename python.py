"""
Financial PDF Extraction Pipeline
==================================
Processes 250+ annual reports / 10-Ks into a hybrid storage system
(DuckDB + ChromaDB + Parquet) ready for RAG-based financial intelligence.

QUICK START (Local Testing):
    # Default: prepares local PDFs and runs test
    python python.py
    
    # Or place PDFs in ./local_pdfs/ and run:
    python python.py --local_dir ./local_pdfs
    
    # Or test specific PDFs directly:
    python python.py --test ./my_pdf1.pdf ./my_pdf2.pdf

FULL PIPELINE (Process directory):
    python python.py --pdf_dir ./pdfs --output_dir ./output

CUSTOM SETUP:
    python python.py --pdf_dir ./pdfs --output_dir ./output --workers 8

Requirements:
    pip install pdfplumber pymupdf duckdb chromadb sentence-transformers tqdm

Optional (for chart extraction):
    pip install google-generativeai        # Gemini Flash (free tier, best for charts)
    pip install camelot-py[cv] ghostscript # better table extraction fallback
"""

import os
import re
import json
import hashlib
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool, cpu_count
from typing import Optional
import urllib.request
import urllib.error

import pdfplumber
import duckdb
import chromadb
from tqdm import tqdm

# ─────────────────────────────────────────────
# OPTIONAL: sentence-transformers for embeddings
# If not installed, embeddings are skipped and
# ChromaDB is populated without vectors.
# ─────────────────────────────────────────────
try:
    from sentence_transformers import SentenceTransformer
    EMBED_MODEL = SentenceTransformer("BAAI/bge-large-en-v1.5")
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False
    EMBED_MODEL = None

# ─────────────────────────────────────────────
# OPTIONAL: Gemini Flash for chart extraction
# Get free API key: https://aistudio.google.com
# ─────────────────────────────────────────────
try:
    import google.generativeai as genai
    _KEY = os.environ.get("GEMINI_API_KEY", "")
    if _KEY:
        genai.configure(api_key=_KEY)
        GEMINI = genai.GenerativeModel("gemini-2.5-flash")
        HAS_GEMINI = True
    else:
        HAS_GEMINI = False
        GEMINI = None
except ImportError:
    HAS_GEMINI = False
    GEMINI = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# CONSTANTS & CONFIGURATION
# ══════════════════════════════════════════════════════════════════

CHUNK_SIZE   = 512   # words per chunk
CHUNK_OVERLAP = 64   # word overlap between chunks
CHART_TEXT_THRESHOLD = 80  # pages with fewer words are chart candidates
DPI = 150            # rasterisation DPI for chart pages

# Section detection — maps page content → canonical section type
# Each tuple is (regex_pattern, section_label)
SECTION_RULES = [
    (r"(letter|message)\s+to\s+(shareholder|investor|stockholder)", "ceo_letter"),
    (r"(dear\s+shareholder|fellow\s+shareholder)",                    "ceo_letter"),
    (r"item\s*1a[\.\s]|risk\s+factor",                               "risk_factors"),
    (r"item\s*7[\.\s]|management.{0,20}discussion\s+and\s+analysis", "mda"),
    (r"consolidated\s+statement.{0,30}(income|operation|earning)",   "income_statement"),
    (r"consolidated\s+(balance\s+sheet|statement.{0,20}financial)",  "balance_sheet"),
    (r"consolidated\s+statement.{0,20}cash\s+flow",                  "cashflow"),
    (r"note\s*\d+[\.\s]|footnote",                                   "footnotes"),
    (r"(esg|environmental|sustainability|carbon\s+emission)",        "esg"),
    (r"item\s*1[\.\s]|business\s+overview|our\s+business",          "business"),
]

# KPI extraction — maps canonical name → regex to match in table rows
KPI_PATTERNS = {
    "total_revenue":       r"total\s+net\s+revenue|total\s+revenue|net\s+revenue",
    "gross_profit":        r"^gross\s+profit$|gross\s+profit\s*$",
    "gross_margin_pct":    r"gross\s+margin",
    "operating_income":    r"operating\s+income|income\s+from\s+operations",
    "operating_expenses":  r"total\s+operating\s+expenses",
    "net_income":          r"net\s+income",
    "r_and_d":             r"research\s+and\s+development",
    "sga":                 r"selling,\s*general|marketing,\s*general",
    "cash_ops":            r"operating\s+activities",
    "cash_invest":         r"investing\s+activities",
    "cash_finance":        r"financing\s+activities",
    "capex":               r"capital\s+expenditure|purchase.{0,20}property",
    "total_debt":          r"total\s+(long.term\s+)?debt|long.term\s+debt",
    "cash_and_equiv":      r"cash\s+and\s+cash\s+equivalents?\s*$",
    "total_assets":        r"total\s+assets",
    "total_liabilities":   r"total\s+liabilities",
    "shareholders_equity": r"total\s+(stockholders?|shareholders?)\s+equity",
}

# CEO promise patterns — sentence-level extraction
PROMISE_PATTERNS = [
    r"(?:we|our\s+company)\s+(?:expect|plan|intend|target|aim|commit|will)\s+.{15,140}?"
    r"(?:by|in|through|during)\s+(?:fiscal\s+)?(?:year\s+)?\d{4}[^.]*\.",
    r"our\s+(?:goal|objective|target|commitment)\s+.{10,120}?"
    r"(?:\d{4}|\d+\s*(?:percent|%))[^.]*\.",
    r"(?:100|50|75|80|90)\s*(?:percent|%)\s+(?:renewable|clean|carbon.neutral)"
    r".{5,80}(?:by|in)\s+\d{4}[^.]*\.",
    r"(?:achieve|reach|deliver)\s+.{10,100}?(?:by|in)\s+\d{4}[^.]*\.",
]


# ══════════════════════════════════════════════════════════════════
# PDF DOWNLOAD & LOCAL MANAGEMENT
# ══════════════════════════════════════════════════════════════════

def download_pdf(url: str, output_path: str, timeout: int = 30) -> bool:
    """
    Download a PDF from a URL and save to local path.
    Returns True if successful, False otherwise.
    """
    try:
        output_path = str(Path(output_path).resolve())
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        log.info(f"  Downloading: {url}")
        urllib.request.urlretrieve(url, output_path)
        file_size = os.path.getsize(output_path) / (1024 * 1024)
        log.info(f"  ✓ Saved to {output_path} ({file_size:.2f} MB)")
        return True
    except urllib.error.URLError as e:
        log.error(f"  ✗ Download failed: {e}")
        return False
    except Exception as e:
        log.error(f"  ✗ Error saving PDF: {e}")
        return False


def prepare_sample_pdfs(pdf_dir: str = "./local_pdfs") -> list:
    """
    Check for sample PDFs locally. If not found, provide instructions.
    Currently configured for AMD 10-Ks but can be extended.
    
    Returns list of available PDF paths.
    """
    pdf_dir = str(Path(pdf_dir).resolve())
    os.makedirs(pdf_dir, exist_ok=True)
    
    # Sample PDF sources (can be updated with real URLs)
    # Note: These are placeholder URLs — replace with actual accessible sources
    samples = {
        "AMD_2021_10K.pdf": None,  # Add URL here if available
        "AMD_2022_10K.pdf": None,  # Add URL here if available
    }
    
    log.info(f"Checking for sample PDFs in {pdf_dir}...")
    available = []
    
    for filename, url in samples.items():
        pdf_path = os.path.join(pdf_dir, filename)
        
        if os.path.exists(pdf_path):
            log.info(f"  ✓ Found: {filename}")
            available.append(pdf_path)
        elif url:
            log.info(f"  Attempting to download: {filename}")
            if download_pdf(url, pdf_path):
                available.append(pdf_path)
        else:
            log.warning(f"  ✗ Not found: {filename} (no download URL configured)")
    
    if not available:
        log.warning(
            f"\nNo sample PDFs found in {pdf_dir}.\n"
            "To get started, either:\n"
            f"  1. Place PDF files in: {pdf_dir}/\n"
            f"  2. Download from your data source and add to that directory\n"
            f"  3. Use --pdf_dir to specify a custom directory\n"
            f"  4. Use --download to fetch from configured sources\n"
        )
    
    return available


# ══════════════════════════════════════════════════════════════════
# UTILITY HELPERS
# ══════════════════════════════════════════════════════════════════

def clean_number(s) -> Optional[float]:
    """Convert a raw table cell string to float, or None if not numeric."""
    if s is None:
        return None
    s = str(s).strip().replace(",", "").replace("$", "").replace("%", "")
    # Handle parentheses as negative: (123) → -123
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return None


def detect_section(page_text: str) -> str:
    """Return canonical section label for a page based on its first 400 chars."""
    snippet = page_text.lower()[:400]
    for pattern, label in SECTION_RULES:
        if re.search(pattern, snippet, re.IGNORECASE):
            return label
    return "general"


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Split text into overlapping word-based chunks. Yields (chunk_index, chunk_text)."""
    words = text.split()
    step = size - overlap
    for idx, start in enumerate(range(0, len(words), step)):
        chunk = " ".join(words[start : start + size])
        if len(chunk.strip()) > 60:   # skip near-empty chunks
            yield idx, chunk


def pdf_hash(pdf_path: str) -> str:
    """Short stable ID for a PDF based on its file hash."""
    h = hashlib.md5(open(pdf_path, "rb").read()).hexdigest()
    return h[:12]


def parse_filename_metadata(pdf_path: str) -> dict:
    """
    Best-effort extraction of company + year from filename.
    Expected patterns:
        AMD_2021_10K.pdf  →  company=AMD, year=2021, doc_type=10K
        Apple_2022_annualreport.pdf → company=Apple, year=2022, doc_type=annual_report
    """
    stem = Path(pdf_path).stem.replace("-", "_")
    year_match = re.search(r"(20\d{2})", stem)
    year = int(year_match.group(1)) if year_match else None
    # Remove year from stem to get company + doc type
    parts = re.sub(r"20\d{2}", "", stem).strip("_").split("_")
    company = parts[0] if parts else "unknown"
    doc_type = "_".join(parts[1:]).lower() if len(parts) > 1 else "unknown"
    # Normalise common doc type aliases
    if re.search(r"10.?k", doc_type):
        doc_type = "10K"
    elif re.search(r"annual", doc_type):
        doc_type = "annual_report"
    elif re.search(r"esg|sustain", doc_type):
        doc_type = "esg_report"
    elif re.search(r"proxy", doc_type):
        doc_type = "proxy"
    return {"company": company, "year": year, "doc_type": doc_type}


# ══════════════════════════════════════════════════════════════════
# PHASE 1 — PDF INSPECTION
# ══════════════════════════════════════════════════════════════════

def inspect_pdf(pdf_path: str) -> dict:
    """
    Run pdfinfo + quick text check to classify the PDF before full extraction.
    Returns a metadata dict with page_count, is_scanned, file_size, creator.
    """
    info = {"pdf_path": pdf_path, "is_scanned": False}
    try:
        r = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15)
        for line in r.stdout.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip().lower().replace(" ", "_"), v.strip()
                if k == "pages":
                    info["page_count"] = int(v)
                elif k == "file_size":
                    info["file_size"] = v
                elif k == "creator":
                    info["creator"] = v
    except Exception as e:
        log.warning(f"pdfinfo failed for {pdf_path}: {e}")

    # Quick text extractability check (first page)
    try:
        r2 = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "1", pdf_path, "-"],
            capture_output=True, text=True, timeout=10
        )
        info["is_scanned"] = len(r2.stdout.strip()) < 50
    except Exception:
        pass

    return info


# ══════════════════════════════════════════════════════════════════
# PHASE 2 — EXTRACTION (text + tables + chart detection)
# ══════════════════════════════════════════════════════════════════

def extract_kpis_from_tables(tables: list, year: Optional[int]) -> dict:
    """Scan all tables on a page and pull recognised KPI values."""
    kpis = {}
    for table in tables:
        for row in table:
            row_str = " ".join(str(c) for c in row if c is not None).strip()
            row_lower = row_str.lower()
            for kpi_key, pattern in KPI_PATTERNS.items():
                if kpi_key in kpis:
                    continue   # already found — keep first match
                if re.search(pattern, row_lower):
                    # Grab all numeric values from this row
                    nums = [clean_number(c) for c in row if clean_number(c) is not None]
                    if nums:
                        # For multi-year rows: nums[0] = most recent, nums[1] = prior year
                        kpis[kpi_key] = nums[0]
                        if len(nums) > 1:
                            kpis[f"{kpi_key}_prior"] = nums[1]
    return kpis


def extract_promises(text: str, company: str, year: Optional[int]) -> list:
    """Extract trackable CEO commitments from page text."""
    found = []
    for pat in PROMISE_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE | re.DOTALL):
            sentence = m.group(0).strip()[:300]
            # Pull target year if mentioned
            yr_match = re.search(r"\b(20\d{2})\b", sentence)
            found.append({
                "company":     company,
                "year_made":   year,
                "target_year": int(yr_match.group(1)) if yr_match else None,
                "statement":   sentence,
                "met_flag":    None,   # filled later by cross-reference agent
                "actual_value": None,
            })
    return found


def rasterize_page(pdf_path: str, page_num: int, out_dir: str, dpi: int = DPI) -> Optional[str]:
    """
    Rasterize a single page to JPEG using pdftoppm.
    Returns file path or None on failure.
    """
    prefix = os.path.join(out_dir, f"pg_{page_num:04d}")
    try:
        subprocess.run(
            ["pdftoppm", "-jpeg", "-r", str(dpi),
             "-f", str(page_num), "-l", str(page_num),
             pdf_path, prefix],
            capture_output=True, timeout=30
        )
        # pdftoppm zero-pads suffix based on total page count
        candidates = sorted(Path(out_dir).glob(f"pg_{page_num:04d}*.jpg"))
        return str(candidates[0]) if candidates else None
    except Exception as e:
        log.warning(f"Rasterize failed page {page_num}: {e}")
        return None


def extract_chart_with_gemini(image_path: str) -> Optional[dict]:
    """
    Send a rasterised chart page to Gemini 1.5 Flash.
    Returns structured JSON or None.
    """
    if not HAS_GEMINI or not image_path:
        return None
    try:
        import PIL.Image
        img = PIL.Image.open(image_path)
        prompt = (
            "This is a page from a financial annual report. "
            "If it contains a chart or graph, extract the data as JSON with keys: "
            "chart_type (bar/line/pie/table), title, x_axis_label, y_axis_label, "
            "series (array of {name, values array}). "
            "If no chart is present, return {\"chart_type\": \"none\"}. "
            "Respond with ONLY valid JSON, no markdown fences."
        )
        resp = GEMINI.generate_content([prompt, img])
        raw = resp.text.strip().lstrip("```json").rstrip("```").strip()
        return json.loads(raw)
    except Exception as e:
        log.warning(f"Gemini chart extraction failed: {e}")
        return None


def extract_pdf(pdf_path: str, output_dir: str) -> dict:
    """
    Main extraction function for a single PDF.
    Returns a result dict containing text chunks, KPIs, promises, table rows,
    chart data, and section map.

    Called by the worker pool — must be top-level (picklable).
    """
    meta = parse_filename_metadata(pdf_path)
    company = meta["company"]
    year    = meta["year"]
    doc_type = meta["doc_type"]
    doc_id  = pdf_hash(pdf_path)

    charts_dir = os.path.join(output_dir, "chart_images", doc_id)
    os.makedirs(charts_dir, exist_ok=True)

    result = {
        "doc_id":    doc_id,
        "pdf_path":  pdf_path,
        "company":   company,
        "year":      year,
        "doc_type":  doc_type,
        "chunks":    [],   # list of {chunk_id, text, section, page, metadata}
        "kpis":      {},   # merged KPI dict across all pages
        "promises":  [],   # list of promise dicts
        "tables":    [],   # raw table rows for Parquet archival
        "charts":    [],   # chart JSON dicts
        "sections":  {},   # section_type → page_count
        "errors":    [],
    }

    try:
        with pdfplumber.open(pdf_path) as doc:
            page_count = len(doc.pages)
            log.info(f"  Processing {page_count} pages...")

            for page_num, page in enumerate(doc.pages, 1):
                try:
                    # Extract text with timeout-like behavior via careful error handling
                    page_text = page.extract_text() or ""
                except Exception as e:
                    log.warning(f"  Page {page_num}: text extraction failed ({type(e).__name__}), skipping text")
                    page_text = ""

                section   = detect_section(page_text) if page_text else "general"

                # ── Track section distribution ──────────────────
                result["sections"][section] = result["sections"].get(section, 0) + 1

                # ── Text chunking ────────────────────────────────
                if len(page_text.split()) > 30:
                    for chunk_idx, chunk in chunk_text(page_text):
                        chunk_id = f"{doc_id}_p{page_num}_c{chunk_idx}"
                        result["chunks"].append({
                            "chunk_id": chunk_id,
                            "text":     chunk,
                            "section":  section,
                            "page":     page_num,
                            "company":  company,
                            "year":     year,
                            "doc_type": doc_type,
                            "doc_id":   doc_id,
                        })

                # ── Table extraction ─────────────────────────────
                try:
                    tables = page.extract_tables()
                except Exception as e:
                    log.warning(f"  Page {page_num}: table extraction failed ({type(e).__name__})")
                    tables = None

                if tables:
                    page_kpis = extract_kpis_from_tables(tables, year)
                    result["kpis"].update(page_kpis)

                    for t_idx, table in enumerate(tables):
                        for row in table:
                            result["tables"].append({
                                "doc_id":   doc_id,
                                "company":  company,
                                "year":     year,
                                "page":     page_num,
                                "section":  section,
                                "table_idx": t_idx,
                                "row":      [str(c) if c else "" for c in row],
                            })

                # ── Promise extraction (CEO letter + MDA pages) ──
                if section in ("ceo_letter", "mda", "business") and page_text:
                    promises = extract_promises(page_text, company, year)
                    result["promises"].extend(promises)

                # ── Chart detection ──────────────────────────────
                word_count = len(page_text.split())
                is_chart_candidate = (
                    word_count < CHART_TEXT_THRESHOLD
                    or (page.images and word_count < 200)
                )
                if is_chart_candidate and page_num > 3:
                    img_path = rasterize_page(pdf_path, page_num, charts_dir)
                    if img_path:
                        chart_data = extract_chart_with_gemini(img_path)
                        if chart_data and chart_data.get("chart_type", "none") != "none":
                            chart_data.update({
                                "doc_id":    doc_id,
                                "company":   company,
                                "year":      year,
                                "page":      page_num,
                                "image_path": img_path,
                            })
                            result["charts"].append(chart_data)

    except Exception as e:
        result["errors"].append(f"PDF processing failed: {str(e)}")
        log.error(f"Failed to extract {pdf_path}: {e}")

    return result


# ══════════════════════════════════════════════════════════════════
# PHASE 3 — STORAGE (DuckDB + ChromaDB + Parquet)
# ══════════════════════════════════════════════════════════════════

def init_duckdb(db_path: str):
    """Create all required DuckDB tables."""
    con = duckdb.connect(db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id       VARCHAR PRIMARY KEY,
            pdf_path     VARCHAR,
            company      VARCHAR,
            year         INTEGER,
            doc_type     VARCHAR,
            page_count   INTEGER,
            ingested_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS kpis (
            doc_id                  VARCHAR,
            company                 VARCHAR,
            year                    INTEGER,
            total_revenue           DOUBLE,
            total_revenue_prior     DOUBLE,
            gross_profit            DOUBLE,
            gross_profit_prior      DOUBLE,
            gross_margin_pct        DOUBLE,
            gross_margin_pct_prior  DOUBLE,
            operating_income        DOUBLE,
            operating_income_prior  DOUBLE,
            operating_expenses      DOUBLE,
            operating_expenses_prior DOUBLE,
            net_income              DOUBLE,
            net_income_prior        DOUBLE,
            r_and_d                 DOUBLE,
            r_and_d_prior           DOUBLE,
            sga                     DOUBLE,
            sga_prior               DOUBLE,
            capex                   DOUBLE,
            capex_prior             DOUBLE,
            total_debt              DOUBLE,
            total_debt_prior        DOUBLE,
            cash_and_equiv          DOUBLE,
            cash_and_equiv_prior    DOUBLE,
            total_assets            DOUBLE,
            total_assets_prior      DOUBLE,
            total_liabilities       DOUBLE,
            total_liabilities_prior DOUBLE,
            shareholders_equity     DOUBLE,
            shareholders_equity_prior DOUBLE,
            cash_ops                DOUBLE,
            cash_ops_prior          DOUBLE,
            cash_invest             DOUBLE,
            cash_invest_prior       DOUBLE,
            cash_finance            DOUBLE,
            cash_finance_prior      DOUBLE,
            PRIMARY KEY (doc_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS promises (
            promise_id   VARCHAR,
            company      VARCHAR,
            year_made    INTEGER,
            target_year  INTEGER,
            statement    VARCHAR,
            met_flag     BOOLEAN,
            actual_value DOUBLE,
            doc_id       VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS risk_factors (
            rf_id        VARCHAR,
            doc_id       VARCHAR,
            company      VARCHAR,
            year         INTEGER,
            page         INTEGER,
            text         VARCHAR,
            section_hash VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS charts (
            chart_id     VARCHAR,
            doc_id       VARCHAR,
            company      VARCHAR,
            year         INTEGER,
            page         INTEGER,
            chart_type   VARCHAR,
            title        VARCHAR,
            data_json    VARCHAR,
            image_path   VARCHAR
        )
    """)
    return con


def store_to_duckdb(con, result: dict):
    """Persist one PDF's extraction result into DuckDB."""
    doc_id  = result["doc_id"]
    company = result["company"]
    year    = result["year"]

    # ── documents ────────────────────────────────────────────────
    con.execute(
        "INSERT OR REPLACE INTO documents (doc_id, pdf_path, company, year, doc_type) "
        "VALUES (?, ?, ?, ?, ?)",
        [doc_id, result["pdf_path"], company, year, result["doc_type"]]
    )

    # ── kpis ─────────────────────────────────────────────────────
    k = result["kpis"]
    if k:
        cols = ["doc_id", "company", "year"] + list(KPI_PATTERNS.keys())
        vals = [doc_id, company, year] + [k.get(c) for c in KPI_PATTERNS]
        placeholders = ", ".join(["?"] * len(vals))
        col_names    = ", ".join(cols)
        con.execute(
            f"INSERT OR REPLACE INTO kpis ({col_names}) VALUES ({placeholders})", vals
        )

    # ── promises ─────────────────────────────────────────────────
    for p in result["promises"]:
        pid = hashlib.md5((doc_id + p["statement"][:60]).encode()).hexdigest()[:12]
        con.execute(
            "INSERT OR IGNORE INTO promises "
            "(promise_id, company, year_made, target_year, statement, met_flag, actual_value, doc_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [pid, company, p["year_made"], p["target_year"],
             p["statement"], p["met_flag"], p["actual_value"], doc_id]
        )

    # ── risk factor chunks ────────────────────────────────────────
    for chunk in result["chunks"]:
        if chunk["section"] == "risk_factors":
            rf_id = hashlib.md5(chunk["chunk_id"].encode()).hexdigest()[:12]
            sh    = hashlib.md5(chunk["text"][:100].encode()).hexdigest()[:8]
            con.execute(
                "INSERT OR IGNORE INTO risk_factors "
                "(rf_id, doc_id, company, year, page, text, section_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [rf_id, doc_id, company, year, chunk["page"], chunk["text"][:2000], sh]
            )

    # ── charts ───────────────────────────────────────────────────
    for ch in result["charts"]:
        chart_id = hashlib.md5(
            (doc_id + str(ch.get("page", ""))).encode()
        ).hexdigest()[:12]
        con.execute(
            "INSERT OR IGNORE INTO charts "
            "(chart_id, doc_id, company, year, page, chart_type, title, data_json, image_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [chart_id, doc_id, company, year,
             ch.get("page"), ch.get("chart_type"), ch.get("title"),
             json.dumps(ch.get("series", [])), ch.get("image_path")]
        )


def store_to_chromadb(collection, result: dict):
    """Upsert text chunks into ChromaDB with metadata filters."""
    if not result["chunks"]:
        return

    ids        = []
    texts      = []
    metadatas  = []
    embeddings = []

    for chunk in result["chunks"]:
        ids.append(chunk["chunk_id"])
        texts.append(chunk["text"])
        metadatas.append({
            "company":  chunk["company"] or "",
            "year":     str(chunk["year"]) if chunk["year"] else "",
            "section":  chunk["section"],
            "page":     chunk["page"],
            "doc_type": chunk["doc_type"],
            "doc_id":   chunk["doc_id"],
        })

    if HAS_EMBEDDINGS and EMBED_MODEL:
        vecs = EMBED_MODEL.encode(texts, batch_size=64, show_progress_bar=False)
        embeddings = [v.tolist() for v in vecs]

    # ChromaDB upsert in batches of 500
    batch = 500
    for i in range(0, len(ids), batch):
        kwargs = dict(
            ids=ids[i:i+batch],
            documents=texts[i:i+batch],
            metadatas=metadatas[i:i+batch],
        )
        if embeddings:
            kwargs["embeddings"] = embeddings[i:i+batch]
        collection.upsert(**kwargs)


def save_tables_parquet(result: dict, output_dir: str):
    """Save raw extracted table rows to Parquet via DuckDB."""
    if not result["tables"]:
        return
    try:
        parquet_dir = os.path.join(output_dir, "parquet")
        os.makedirs(parquet_dir, exist_ok=True)
        out_file = os.path.join(
            parquet_dir,
            f"{result['company']}_{result['year']}_{result['doc_id']}.parquet"
        )
        rows = result["tables"]
        tmp = duckdb.connect()
        tmp.execute(f"""
            COPY (SELECT * FROM (VALUES {','.join(
                [f"('{r['doc_id']}', '{r['company']}', {r['year'] or 'NULL'}, "
                 f"{r['page']}, '{r['section']}', {r['table_idx']}, '{json.dumps(r['row'])}')"
                 for r in rows]
            )}) t(doc_id, company, year, page, section, table_idx, row_json))
            TO '{out_file}' (FORMAT PARQUET)
        """)
        tmp.close()
    except Exception as e:
        log.warning(f"Parquet save failed for {result['doc_id']}: {e}")


# ══════════════════════════════════════════════════════════════════
# PHASE 4 — RETRIEVAL HELPERS (query-time)
# ══════════════════════════════════════════════════════════════════

class FinancialKnowledgeBase:
    """
    Query interface over the stored pipeline output.
    Exposes the three retrieval patterns used by the LangGraph agents.
    """

    def __init__(self, db_path: str, chroma_path: str):
        self.con = duckdb.connect(db_path, read_only=True)
        self.chroma = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.chroma.get_or_create_collection("financial_docs")

    # ── Module 1: Trend & peer comparison ────────────────────────

    def get_kpi_trend(self, company: str, kpi: str, year_start: int, year_end: int) -> list:
        """SQL query: KPI values for a company across a year range."""
        rows = self.con.execute(
            f"SELECT year, {kpi} FROM kpis "
            "WHERE company = ? AND year BETWEEN ? AND ? "
            "ORDER BY year",
            [company, year_start, year_end]
        ).fetchall()
        return [{"year": r[0], kpi: r[1]} for r in rows]

    def compare_kpi_peers(self, companies: list, kpi: str, year: int) -> list:
        """Compare a KPI across multiple companies for a given year."""
        placeholders = ", ".join(["?"] * len(companies))
        rows = self.con.execute(
            f"SELECT company, {kpi} FROM kpis "
            f"WHERE company IN ({placeholders}) AND year = ? "
            "ORDER BY company",
            companies + [year]
        ).fetchall()
        return [{"company": r[0], kpi: r[1]} for r in rows]

    def semantic_search(
        self,
        query: str,
        company: Optional[str] = None,
        year: Optional[int] = None,
        section: Optional[str] = None,
        top_k: int = 8,
    ) -> list:
        """
        ChromaDB vector search with optional metadata filters.
        Falls back to keyword search if no embedding model is available.
        """
        where = {}
        if company:
            where["company"] = company
        if year:
            where["year"] = str(year)
        if section:
            where["section"] = section

        kwargs = dict(
            query_texts=[query],
            n_results=top_k,
        )
        if where:
            kwargs["where"] = where

        try:
            res = self.collection.query(**kwargs)
            docs  = res["documents"][0] if res["documents"] else []
            metas = res["metadatas"][0]  if res["metadatas"]  else []
            return [{"text": d, "metadata": m} for d, m in zip(docs, metas)]
        except Exception as e:
            log.warning(f"ChromaDB query failed: {e}")
            return []

    # ── Module 2: Auditor & visualizer ───────────────────────────

    def get_financial_health(self, company: str) -> dict:
        """Pull all KPIs for a company across all years — for dashboard generation."""
        rows = self.con.execute(
            "SELECT * FROM kpis WHERE company = ? ORDER BY year", [company]
        ).fetchdf()
        return rows.to_dict(orient="records")

    def get_charts(self, company: str, year: Optional[int] = None) -> list:
        """Retrieve stored chart data for a company."""
        if year:
            rows = self.con.execute(
                "SELECT * FROM charts WHERE company = ? AND year = ?",
                [company, year]
            ).fetchall()
        else:
            rows = self.con.execute(
                "SELECT * FROM charts WHERE company = ?", [company]
            ).fetchall()
        return [dict(zip([d[0] for d in self.con.description], r)) for r in rows]

    # ── Module 3: Forensic & anomaly detection ────────────────────

    def get_promises(self, company: str) -> list:
        """Retrieve all tracked CEO promises for a company."""
        rows = self.con.execute(
            "SELECT * FROM promises WHERE company = ? ORDER BY year_made",
            [company]
        ).fetchall()
        return [dict(zip([d[0] for d in self.con.description], r)) for r in rows]

    def get_risk_factor_diff(
        self, company: str, year_a: int, year_b: int
    ) -> dict:
        """Return risk factor texts for two years for diffing."""
        def get_risks(yr):
            rows = self.con.execute(
                "SELECT text FROM risk_factors WHERE company = ? AND year = ?",
                [company, yr]
            ).fetchall()
            return [r[0] for r in rows]
        return {
            "company": company,
            "year_a":  year_a,
            "year_b":  year_b,
            "risks_a": get_risks(year_a),
            "risks_b": get_risks(year_b),
        }


# ══════════════════════════════════════════════════════════════════
# MAIN PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════

def _worker(args):
    """Multiprocessing worker — must be a top-level function."""
    pdf_path, output_dir = args
    return extract_pdf(pdf_path, output_dir)


def run_pipeline(pdf_dir: str, output_dir: str, workers: int = 4):
    """
    Full pipeline:
        1. Discover PDFs
        2. Extract in parallel (workers × processes)
        3. Store into DuckDB + ChromaDB + Parquet
    """
    pdf_dir    = str(Path(pdf_dir).resolve())
    output_dir = str(Path(output_dir).resolve())
    os.makedirs(output_dir, exist_ok=True)

    db_path     = os.path.join(output_dir, "finance.duckdb")
    chroma_path = os.path.join(output_dir, "chroma")
    os.makedirs(chroma_path, exist_ok=True)

    # ── Discover PDFs ─────────────────────────────────────────────
    pdfs = sorted(Path(pdf_dir).glob("**/*.pdf"))
    if not pdfs:
        log.error(f"No PDFs found in {pdf_dir}")
        return
    log.info(f"Found {len(pdfs)} PDFs in {pdf_dir}")

    # ── Inspect (single-threaded, fast) ──────────────────────────
    log.info("Inspecting PDFs...")
    scanned = []
    for pdf in pdfs:
        info = inspect_pdf(str(pdf))
        if info.get("is_scanned"):
            scanned.append(str(pdf))
            log.warning(f"  [SCAN] {pdf.name} — needs OCR, will be skipped")
    if scanned:
        log.warning(
            f"{len(scanned)} scanned PDFs detected. "
            "Run pytesseract OCR on these separately."
        )

    processable = [p for p in pdfs if str(p) not in scanned]
    log.info(f"{len(processable)} PDFs ready for extraction")

    # ── Initialise storage ────────────────────────────────────────
    log.info("Initialising DuckDB schema...")
    con = init_duckdb(db_path)

    log.info("Initialising ChromaDB collection...")
    chroma_client = chromadb.PersistentClient(path=chroma_path)
    collection = chroma_client.get_or_create_collection(
        "financial_docs",
        metadata={"hnsw:space": "cosine"}
    )

    # ── Extract in parallel ───────────────────────────────────────
    worker_args = [(str(p), output_dir) for p in processable]
    actual_workers = min(workers, cpu_count(), len(processable))
    log.info(f"Starting extraction with {actual_workers} workers...")

    stats = {"success": 0, "failed": 0, "chunks": 0, "kpis": 0, "promises": 0}

    with Pool(processes=actual_workers) as pool:
        for result in tqdm(
            pool.imap_unordered(_worker, worker_args),
            total=len(worker_args),
            desc="Extracting",
        ):
            if result["errors"]:
                log.warning(f"Errors in {result['pdf_path']}: {result['errors']}")
                stats["failed"] += 1
            else:
                stats["success"] += 1

            # ── Store result ──────────────────────────────────────
            try:
                store_to_duckdb(con, result)
                store_to_chromadb(collection, result)
                save_tables_parquet(result, output_dir)
                stats["chunks"]   += len(result["chunks"])
                stats["kpis"]     += len(result["kpis"])
                stats["promises"] += len(result["promises"])
            except Exception as e:
                log.error(f"Storage failed for {result['pdf_path']}: {e}")

    con.close()

    # ── Summary ───────────────────────────────────────────────────
    log.info("=" * 55)
    log.info("Pipeline complete.")
    log.info(f"  PDFs processed:  {stats['success']} ok / {stats['failed']} failed")
    log.info(f"  Text chunks:     {stats['chunks']:,}")
    log.info(f"  KPI rows:        {stats['kpis']:,}")
    log.info(f"  CEO promises:    {stats['promises']:,}")
    log.info(f"  DuckDB:          {db_path}")
    log.info(f"  ChromaDB:        {chroma_path}")
    log.info(f"  Parquet tables:  {output_dir}/parquet/")
    log.info("=" * 55)

    return FinancialKnowledgeBase(db_path, chroma_path)


# ══════════════════════════════════════════════════════════════════
# QUICK TEST — runs against the two AMD sample PDFs
# ══════════════════════════════════════════════════════════════════

def quick_test(pdf_paths: list, output_dir: str = "./test_output"):
    """
    Run the pipeline on a small list of PDFs and print a summary.
    Useful for verifying extraction quality before full 250-PDF run.
    """
    os.makedirs(output_dir, exist_ok=True)
    db_path     = os.path.join(output_dir, "finance.duckdb")
    chroma_path = os.path.join(output_dir, "chroma")
    os.makedirs(chroma_path, exist_ok=True)

    con        = init_duckdb(db_path)
    chroma_c   = chromadb.PersistentClient(path=chroma_path)
    collection = chroma_c.get_or_create_collection("financial_docs")

    for pdf_path in pdf_paths:
        log.info(f"Extracting: {pdf_path}")
        result = extract_pdf(pdf_path, output_dir)

        print(f"\n{'='*55}")
        print(f"  PDF:      {Path(pdf_path).name}")
        print(f"  Company:  {result['company']}  |  Year: {result['year']}")
        print(f"  Chunks:   {len(result['chunks'])}")
        print(f"  Sections: {result['sections']}")
        print(f"  KPIs extracted:")
        for k, v in result["kpis"].items():
            if not k.endswith("_prior"):
                print(f"    {k:30s}: {v}")
        print(f"  CEO promises found: {len(result['promises'])}")
        for p in result["promises"][:3]:
            print(f"    [{p['target_year']}] {p['statement'][:90]}...")
        print(f"  Charts detected:    {len(result['charts'])}")
        print(f"  Errors:             {result['errors']}")

        store_to_duckdb(con, result)
        store_to_chromadb(collection, result)
        save_tables_parquet(result, output_dir)

    con.close()

    # ── Demo retrieval ────────────────────────────────────────────
    print(f"\n{'='*55}")
    print("RETRIEVAL DEMO")
    kb = FinancialKnowledgeBase(db_path, chroma_path)

    trend = kb.get_kpi_trend("AMD", "total_revenue", 2020, 2023)
    print(f"\nAMD revenue trend: {trend}")

    risks = kb.semantic_search("supply chain risk", company="AMD", section="risk_factors", top_k=2)
    print(f"\nTop risk factor chunk:\n  {risks[0]['text'][:200]}..." if risks else "\nNo risk chunks found.")


# ══════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Financial PDF extraction pipeline"
    )
    parser.add_argument(
        "--pdf_dir",
        help="Directory containing all PDF files (searched recursively)",
    )
    parser.add_argument(
        "--output_dir",
        default="./output",
        help="Output directory for DuckDB, ChromaDB, and Parquet files",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel extraction workers (default: 4)",
    )
    parser.add_argument(
        "--test",
        nargs="+",
        metavar="PDF",
        help="Quick-test mode: pass one or more PDF paths directly",
    )
    parser.add_argument(
        "--local_dir",
        default="./local_pdfs",
        help="Local directory to store/check for sample PDFs (default: ./local_pdfs)",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Attempt to download sample PDFs to local_dir before processing",
    )

    args = parser.parse_args()

    if args.test:
        # Direct PDF paths provided
        quick_test(args.test, args.output_dir)
    elif args.pdf_dir:
        # User specified a PDF directory
        run_pipeline(args.pdf_dir, args.output_dir, args.workers)
    else:
        # Default: prepare local PDFs and test
        log.info("=" * 55)
        log.info("LOCAL PDF SETUP & TEST MODE")
        log.info("=" * 55)
        
        samples = prepare_sample_pdfs(args.local_dir)
        
        if samples:
            log.info(f"\nRunning quick test on {len(samples)} local PDF(s)...")
            quick_test(samples, args.output_dir)
        else:
            log.error("\nNo PDFs available to test. Please:")
            log.error(f"  1. Add PDF files to: {args.local_dir}/")
            log.error(f"  2. Or use: python python.py --pdf_dir <path>")
            log.error(f"  3. Or use: python python.py --test <pdf1> <pdf2> ...")
            parser.print_help()