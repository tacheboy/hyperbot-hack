"""
Stage 5 — Output Formatter
===========================
Converts raw findings list into the exact submission JSON schema.
"""

import re
import json
import logging
from typing import List, Dict, Any

log = logging.getLogger(__name__)

VALID_CATEGORIES = {
    # Easy
    "arithmetic_error", "billing_typo", "duplicate_line_item",
    "invalid_date", "wrong_tax_rate",
    # Medium
    "po_invoice_mismatch", "vendor_name_typo", "double_payment",
    "ifsc_mismatch", "duplicate_expense", "date_cascade", "gstin_state_mismatch",
    # Evil
    "quantity_accumulation", "price_escalation", "balance_drift",
    "circular_reference", "triple_expense_claim", "employee_id_collision",
    "fake_vendor", "phantom_po_reference",
}


def _clean_value(val: Any) -> str:
    """Normalize a reported/correct value to a clean string."""
    if val is None:
        return ""
    s = str(val).strip()
    # Remove excessive whitespace
    s = re.sub(r"\s+", " ", s)
    return s


def build_findings_json(team_id: str, findings: List[dict]) -> dict:
    """
    Build the final submission dict.

    Each finding gets:
      finding_id     : F-001, F-002, ...
      category       : validated against allowed set
      pages          : sorted list of ints
      document_refs  : list of str (exact IDs)
      description    : free text
      reported_value : string
      correct_value  : string
    """
    output_findings = []
    skipped = 0

    for idx, f in enumerate(findings, start=1):
        category = f.get("category", "")
        if category not in VALID_CATEGORIES:
            log.warning(f"  Skipping finding {idx}: unknown category '{category}'")
            skipped += 1
            continue

        doc_refs = f.get("document_refs", [])
        if not doc_refs:
            log.warning(f"  Skipping finding {idx} ({category}): no document_refs")
            skipped += 1
            continue

        pages = sorted(set(int(p) for p in f.get("pages", []) if p))

        output_findings.append({
            "finding_id":     f"F-{idx:03d}",
            "category":       category,
            "pages":          pages,
            "document_refs":  [str(r).strip() for r in doc_refs if r],
            "description":    _clean_value(f.get("description", "")),
            "reported_value": _clean_value(f.get("reported_value", "")),
            "correct_value":  _clean_value(f.get("correct_value", "")),
        })

    log.info(f"  Valid findings: {len(output_findings)}, skipped: {skipped}")

    return {
        "team_id":  team_id,
        "findings": output_findings,
    }
