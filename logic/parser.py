"""
Stage 3 — Parsing with HyperAPI (parse + extract)
==================================================
For each DocSegment:
  1. Render every page to a PNG (via PyMuPDF)
  2. Call client.parse()   → OCR text  (cached per page)
  3. Call client.extract() → structured dict with entities + line_items (cached per doc)
  4. Merge all results and attach to segment.parsed

Cache layout:
  .cache/ocr_<page_no>.json              raw OCR text per page
  .cache/extract_<doc_id_hash>.json      structured extraction per doc (entities + line_items)
"""

import json
import time
import hashlib
import logging
import threading
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz
import httpx

from logic.splitter import DocSegment

log = logging.getLogger(__name__)

# Rate-limit / retry settings
MAX_RETRIES      = 4
RETRY_BACKOFF_S  = [2, 5, 15, 30]   # seconds between retries
_API_SEMAPHORE   = threading.Semaphore(8)  # max 8 concurrent API calls


def _img_path(page_no: int) -> Path:
    """Generate path for rendered page image."""
    return Path(f"/tmp/page_{page_no:04d}.png")


def _render_page(pdf_doc, page_no: int, dpi: int = 200) -> Optional[Path]:
    """
    Render a PDF page to PNG. Returns None on failure.
    Thread-safe: each thread should have its own pdf_doc handle.
    """
    path = _img_path(page_no)
    if path.exists():
        return path
    
    try:
        page = pdf_doc[page_no - 1]  # 0-indexed
        mat  = fitz.Matrix(dpi / 72, dpi / 72)
        pix  = page.get_pixmap(matrix=mat)
        pix.save(str(path))
        return path
    except Exception as e:
        log.error(f"  Failed to render page {page_no}: {e}")
        return None


def _ocr_cache_path(cache_dir: Path, page_no: int) -> Path:
    """Generate cache path for OCR result."""
    return cache_dir / f"ocr_{page_no:04d}.json"


def _extract_cache_path(cache_dir: Path, doc_hash: str, cache_type: str) -> Path:
    """Generate cache path for extraction results."""
    return cache_dir / f"{cache_type}_{doc_hash}.json"


def _call_with_retry(fn, *args, label="API call"):
    """
    Wrap any HyperAPI call with exponential-backoff retry.
    Handles ParseError, ExtractError, and connection errors.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
            wait = RETRY_BACKOFF_S[min(attempt, len(RETRY_BACKOFF_S) - 1)]
            log.warning(f"  [{label}] attempt {attempt+1} connection error: {e}. Retrying in {wait}s…")
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)
        except Exception as e:
            wait = RETRY_BACKOFF_S[min(attempt, len(RETRY_BACKOFF_S) - 1)]
            log.warning(f"  [{label}] attempt {attempt+1} failed: {e}. Retrying in {wait}s…")
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)
    
    log.error(f"  [{label}] failed after {MAX_RETRIES} attempts")
    return None


def _parse_pages(client, pdf_doc, pages: List[int], cache_dir: Path) -> str:
    """
    OCR each page (cached). Concatenate and return full text.
    """
    texts = []
    for page_no in pages:
        cache_file = _ocr_cache_path(cache_dir, page_no)
        
        # Check cache first
        if cache_file.exists():
            try:
                ocr_text = json.loads(cache_file.read_text())["ocr"]
                texts.append(f"--- Page {page_no} ---\n{ocr_text}")
                continue
            except Exception as e:
                log.warning(f"  Cache read failed for page {page_no}: {e}")
        
        # Render page
        img_path = _render_page(pdf_doc, page_no)
        if not img_path:
            log.warning(f"  Skipping page {page_no} due to render failure")
            continue
        
        # Call API with retry
        result = _call_with_retry(client.parse, str(img_path), label=f"parse p{page_no}")
        if result is None:
            log.warning(f"  Skipping page {page_no} due to API failure")
            continue
        
        # Validate response
        if "ocr" not in result:
            log.warning(f"  Invalid parse response for page {page_no}: missing 'ocr' key")
            continue
        
        ocr_text = result["ocr"]
        
        # Write to cache
        try:
            cache_file.write_text(json.dumps({"ocr": ocr_text}))
        except Exception as e:
            log.warning(f"  Cache write failed for page {page_no}: {e}")
        
        texts.append(f"--- Page {page_no} ---\n{ocr_text}")
    
    return "\n\n".join(texts)


def _extract_all(client, ocr_text: str, doc_hash: str, cache_dir: Path) -> dict:
    """
    Run HyperAPI extract endpoint on OCR text.
    
    The extract endpoint takes OCR text and returns structured data.
    
    Returns merged dict with all extracted fields.
    """
    extract_cache = _extract_cache_path(cache_dir, doc_hash, "extract")
    
    # Check cache first
    if extract_cache.exists():
        try:
            return json.loads(extract_cache.read_text())
        except Exception as e:
            log.warning(f"  Extract cache read failed for {doc_hash[:8]}: {e}")
    
    # Call extract API with OCR text
    result = _call_with_retry(client.extract, ocr_text, label=f"extract {doc_hash[:8]}")
    
    if result:
        # The new SDK returns {"data": {...}, "validation_errors": [...]}
        parsed = result.get("data", {})
        validation_errors = result.get("validation_errors", [])
        
        # Merge validation errors into the parsed data
        if validation_errors:
            parsed["validation_errors"] = validation_errors
        
        # Write to cache
        try:
            extract_cache.write_text(json.dumps(parsed))
        except Exception as e:
            log.warning(f"  Extract cache write failed for {doc_hash[:8]}: {e}")
        
        return parsed
    
    return {}


def _parse_one(client, pdf_path: Path, seg: DocSegment, cache_dir: Path) -> DocSegment:
    """
    Parse a single document segment with API rate limiting.
    Opens its own PDF handle for thread safety.
    """
    with _API_SEMAPHORE:
        try:
            # Open PDF (thread-safe)
            pdf_doc = fitz.open(str(pdf_path))
            
            # OCR all pages
            seg.raw_text = _parse_pages(client, pdf_doc, seg.pages, cache_dir)
            
            # Structured extraction using OCR text
            key_str  = f"{seg.doc_id}|{seg.pages}"
            doc_hash = hashlib.md5(key_str.encode()).hexdigest()
            seg.parsed = _extract_all(client, seg.raw_text, doc_hash, cache_dir)
            
            # Patch missing doc_id from structured data
            if not seg.doc_id:
                seg.doc_id = (
                    seg.parsed.get("invoice_number")
                    or seg.parsed.get("po_number")
                    or seg.parsed.get("document_number")
                    or f"{seg.doc_type.upper()}-P{seg.pages[0]}"
                )
            
            pdf_doc.close()
            
        except Exception as e:
            log.error(f"  Failed to parse segment {seg.doc_id} pages {seg.pages}: {e}")
            seg.parsed = {}
    
    return seg


def parse_all_docs(
    client,
    pdf_path: Path,
    segments: List[DocSegment],
    cache_dir: Path,
) -> List[DocSegment]:
    """
    Parse and extract every segment using ThreadPoolExecutor.
    Mutates each segment in-place:
      segment.raw_text  = full OCR text
      segment.parsed    = structured dict from client.extract()
    Returns the same list (for chaining).
    """
    total = len(segments)
    log.info(f"  Parsing {total} segments with 8 concurrent workers…")
    
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_parse_one, client, pdf_path, seg, cache_dir): seg
            for seg in segments
        }
        
        completed = 0
        for fut in as_completed(futures):
            try:
                fut.result()  # re-raises exceptions
                completed += 1
                if completed % 50 == 0:
                    log.info(f"  Progress: {completed}/{total} segments parsed")
            except Exception as e:
                seg = futures[fut]
                log.error(f"  Segment {seg.doc_id} failed: {e}")
                seg.parsed = {}
    
    log.info(f"  Completed parsing {total} segments")
    return segments
