"""
Stage 2 — Document Splitting & Classification
==============================================
The 1,000-page PDF is a bundle of ~750 mixed documents.
We scan the raw text layer (fast, no API calls) and detect
document boundaries by looking for header keywords.

Returns a list of DocSegment objects:
  [
    DocSegment(doc_type="invoice",    pages=[47,48],    doc_id="INV-2025-0042"),
    DocSegment(doc_type="po",         pages=[49],       doc_id="PO-2025-0017"),
    ...
  ]
"""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF

log = logging.getLogger(__name__)

# ── Document type signatures ──────────────────────────────────────────────────
# Each entry: (doc_type, list_of_regex_patterns_that_signal_a_new_doc_start)
DOC_SIGNATURES = [
    ("invoice",         [r"tax\s+invoice", r"invoice\s+(no|number|#)\s*[:\-]?\s*\S+"]),
    ("po",              [r"purchase\s+order", r"p\.?o\.?\s+(no|number|#)\s*[:\-]?\s*\S+"]),
    ("bank_statement",  [r"bank\s+statement", r"account\s+statement", r"opening\s+balance"]),
    ("expense_report",  [r"expense\s+report", r"expense\s+claim", r"reimbursement\s+request"]),
    ("credit_note",     [r"credit\s+note", r"credit\s+memo"]),
    ("debit_note",      [r"debit\s+note", r"debit\s+memo"]),
    ("receipt",         [r"payment\s+receipt", r"official\s+receipt"]),
    ("delivery_note",   [r"delivery\s+note", r"goods\s+receipt\s+note", r"grn\b"]),
    ("quotation",       [r"quotation", r"proforma\s+invoice", r"pro.?forma"]),
    ("terms",           [r"terms\s+(and|&)\s+conditions", r"t\s*&\s*c\b"]),
]

# ID patterns per doc type
ID_PATTERNS = {
    "invoice":        r"(INV[-/]\d{4}[-/]\d+)",
    "po":             r"(PO[-/]\d{4}[-/]\d+)",
    "bank_statement": r"(BS[-/]\d{4}[-/]\d+|Statement\s+[A-Z0-9\-]+)",
    "expense_report": r"(EXP[-/]\d{4}[-/]\d+|ER[-/]\d{4}[-/]\d+)",
    "credit_note":    r"(CN[-/]\d{4}[-/]\d+)",
    "debit_note":     r"(DN[-/]\d{4}[-/]\d+)",
}


@dataclass
class DocSegment:
    doc_type:   str
    pages:      List[int] = field(default_factory=list)
    doc_id:     Optional[str] = None
    raw_text:   str = ""          # concatenated text of all pages — filled by parser


def _extract_doc_id(text: str, doc_type: str) -> Optional[str]:
    pattern = ID_PATTERNS.get(doc_type)
    if not pattern:
        return None
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _classify_page(text: str) -> Optional[str]:
    """Return the best-matching doc_type for a page or None."""
    text_lower = text.lower()
    for doc_type, patterns in DOC_SIGNATURES:
        for pat in patterns:
            if re.search(pat, text_lower):
                return doc_type
    return None


def split_and_classify(
    pdf_path: Path,
    page_start: int = 5,
    page_end: int = 1000,
) -> List[DocSegment]:
    """
    Iterate through pages using the fast PyMuPDF text layer.
    Build segments by detecting document boundaries.
    """
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    end = min(page_end, total_pages)

    segments: List[DocSegment] = []
    current: Optional[DocSegment] = None

    for page_idx in range(page_start - 1, end):   # 0-indexed
        page_no = page_idx + 1
        text = doc[page_idx].get_text("text")

        detected_type = _classify_page(text)

        # If we see a new doc type keyword, start a new segment
        if detected_type and (current is None or detected_type != current.doc_type):
            if current is not None:
                segments.append(current)
            doc_id = _extract_doc_id(text, detected_type)
            current = DocSegment(doc_type=detected_type, pages=[page_no], doc_id=doc_id)
        elif current is not None:
            # Continuation page — check for embedded new doc signals
            new_id = _extract_doc_id(text, current.doc_type)
            if new_id and new_id != current.doc_id and current.doc_id is not None:
                # Same type but different ID = new document
                segments.append(current)
                current = DocSegment(doc_type=current.doc_type, pages=[page_no], doc_id=new_id)
            else:
                current.pages.append(page_no)
                if not current.doc_id and new_id:
                    current.doc_id = new_id
        else:
            # Filler / unclassified — lump into a generic segment
            current = DocSegment(doc_type="other", pages=[page_no], doc_id=None)

    if current is not None:
        segments.append(current)

    doc.close()

    # Stats
    type_counts: dict = {}
    for s in segments:
        type_counts[s.doc_type] = type_counts.get(s.doc_type, 0) + 1
    log.info(f"  Segment breakdown: {type_counts}")

    return segments
