"""
Stage 3 — Parsing with HyperAPI (parse + extract)
==================================================
For each DocSegment:
  1. Render every page to a PNG (via PyMuPDF)
  2. Call client.parse()   → OCR text  (cached per page)
  3. Call client.extract() → structured dict (cached per doc)
  4. Attach results back to the DocSegment as segment.parsed

Cache layout:
  .cache/ocr_<page_no>.json          raw OCR text per page
  .cache/extract_<doc_id_hash>.json  structured extraction per doc
"""

import json
import time
import hashlib
import logging
from pathlib import Path
from typing import List, Optional

import fitz

from stages.splitter import DocSegment

log = logging.getLogger(__name__)

# Rate-limit / retry settings
MAX_RETRIES      = 4
RETRY_BACKOFF_S  = [2, 5, 15, 30]   # seconds between retries


def _img_path(page_no: int) -> Path:
    p = Path(f"/tmp/page_{page_no:04d}.png")
    return p


def _render_page(pdf_doc, page_no: int, dpi: int = 200) -> Path:
    path = _img_path(page_no)
    if not path.exists():
        page = pdf_doc[page_no - 1]
        mat  = fitz.Matrix(dpi / 72, dpi / 72)
        pix  = page.get_pixmap(matrix=mat)
        pix.save(str(path))
    return path


def _ocr_cache_path(cache_dir: Path, page_no: int) -> Path:
    return cache_dir / f"ocr_{page_no:04d}.json"


def _extract_cache_path(cache_dir: Path, doc_hash: str) -> Path:
    return cache_dir / f"extract_{doc_hash}.json"


def _call_with_retry(fn, *args, label="API call"):
    """Wrap any HyperAPI call with exponential-backoff retry."""
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args)
        except Exception as e:
            wait = RETRY_BACKOFF_S[min(attempt, len(RETRY_BACKOFF_S) - 1)]
            log.warning(f"  [{label}] attempt {attempt+1} failed: {e}. Retrying in {wait}s…")
            time.sleep(wait)
    raise RuntimeError(f"{label} failed after {MAX_RETRIES} attempts")


def _parse_pages(client, pdf_doc, pages: List[int], cache_dir: Path) -> str:
    """
    OCR each page (cached). Concatenate and return full text.
    """
    texts = []
    for page_no in pages:
        cache_file = _ocr_cache_path(cache_dir, page_no)
        if cache_file.exists():
            ocr_text = json.loads(cache_file.read_text())["ocr"]
        else:
            img_path = _render_page(pdf_doc, page_no)
            result   = _call_with_retry(client.parse, str(img_path), label=f"parse p{page_no}")
            ocr_text = result["ocr"]
            cache_file.write_text(json.dumps({"ocr": ocr_text}))
        texts.append(f"--- Page {page_no} ---\n{ocr_text}")
    return "\n\n".join(texts)


def _extract_structured(client, ocr_text: str, doc_hash: str, cache_dir: Path) -> dict:
    """
    Run HyperAPI extract on full OCR text of a document (cached).
    """
    cache_file = _extract_cache_path(cache_dir, doc_hash)
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    result = _call_with_retry(client.extract, ocr_text, label=f"extract {doc_hash[:8]}")
    data   = result.get("data", {})
    cache_file.write_text(json.dumps(data))
    return data


def parse_all_docs(
    client,
    pdf_path: Path,
    segments: List[DocSegment],
    cache_dir: Path,
) -> List[DocSegment]:
    """
    Parse and extract every segment. Mutates each segment in-place:
      segment.raw_text  = full OCR text
      segment.parsed    = structured dict from client.extract()
    Returns the same list (for chaining).
    """
    pdf_doc = fitz.open(str(pdf_path))
    total   = len(segments)

    for idx, seg in enumerate(segments):
        if idx % 50 == 0:
            log.info(f"  Parsing segment {idx}/{total}…")

        # ── OCR ──────────────────────────────────────────────────────────────
        seg.raw_text = _parse_pages(client, pdf_doc, seg.pages, cache_dir)

        # ── Structured extraction ─────────────────────────────────────────────
        # Use doc_id + pages as a stable cache key
        key_str  = f"{seg.doc_id}|{seg.pages}"
        doc_hash = hashlib.md5(key_str.encode()).hexdigest()
        seg.parsed = _extract_structured(client, seg.raw_text, doc_hash, cache_dir)

        # ── Patch missing doc_id from structured data ────────────────────────
        if not seg.doc_id:
            seg.doc_id = (
                seg.parsed.get("invoice_number")
                or seg.parsed.get("po_number")
                or seg.parsed.get("document_number")
                or f"{seg.doc_type.upper()}-P{seg.pages[0]}"
            )

    pdf_doc.close()
    return segments
