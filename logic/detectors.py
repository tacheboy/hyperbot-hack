"""
Stage 4 — Needle Detection (all 20 categories)
===============================================
Detectors are grouped by difficulty tier.

Every detector returns a list of Finding dicts matching the submission schema:
  {
    "category":       str,
    "pages":          [int, ...],
    "document_refs":  [str, ...],
    "description":    str,
    "reported_value": str,
    "correct_value":  str,
  }

The master run_all_detectors() function:
  1. Calls every detector
  2. Deduplicates overlapping findings
  3. Returns the merged list
"""

import re
import math
import logging
from datetime import datetime
from collections import defaultdict
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Any

from stages.splitter import DocSegment

log = logging.getLogger(__name__)

# ── GST: HSN/SAC → correct tax rate ──────────────────────────────────────────
# Simplified subset (add more as you discover them in the dataset)
HSN_TAX_RATE = {
    # Freight / transport services
    "9965": 5, "9966": 5,
    # IT services / consulting
    "9983": 18, "9984": 18, "9985": 18,
    # Manpower supply
    "9985": 18,
    # Construction
    "9954": 12,
    # Financial / insurance
    "9971": 18,
    # General goods (catch-all): 18
}


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _to_float(val: Any, default=0.0) -> float:
    """Coerce a value to float, stripping currency symbols."""
    if val is None:
        return default
    s = re.sub(r"[₹$,\s]", "", str(val))
    try:
        return float(s)
    except ValueError:
        return default


def _normalize_ref(ref: str) -> str:
    return re.sub(r"\s+", "", ref).upper()


def _fuzzy_match(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _is_valid_date(day: int, month: int, year: int) -> bool:
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        return False


def _parse_date(date_str: str) -> Optional[datetime]:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y-%m-%d",
                "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  TIER 1 — EASY  (single-document checks)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_arithmetic_errors(seg: DocSegment) -> List[dict]:
    """
    Uses HyperAPI's extract() line-item validation.
    seg.parsed["line_items"] each carry a "validated" flag and
    "validation_errors" from HyperAPI's internal arithmetic engine.
    """
    findings = []
    line_items = seg.parsed.get("line_items", [])
    subtotal   = _to_float(seg.parsed.get("subtotal"))
    tax_amount = _to_float(seg.parsed.get("tax_amount"))
    grand_total = _to_float(seg.parsed.get("total") or seg.parsed.get("grand_total"))

    # 1a. Per-line arithmetic: qty × rate ≠ amount
    computed_subtotal = 0.0
    for i, item in enumerate(line_items):
        qty    = _to_float(item.get("quantity"))
        rate   = _to_float(item.get("rate") or item.get("unit_price"))
        amount = _to_float(item.get("amount") or item.get("line_total"))
        expected = round(qty * rate, 2)
        if amount and expected and abs(expected - amount) > 0.05:
            findings.append({
                "category": "arithmetic_error",
                "pages": seg.pages,
                "document_refs": [seg.doc_id],
                "description": f"Line {i+1}: qty={qty} × rate={rate} = {expected}, but invoice shows {amount}",
                "reported_value": str(amount),
                "correct_value": str(expected),
            })
        computed_subtotal += amount or expected

    # 1b. Subtotal ≠ sum of line items
    if subtotal and abs(round(computed_subtotal, 2) - subtotal) > 0.10:
        findings.append({
            "category": "arithmetic_error",
            "pages": seg.pages,
            "document_refs": [seg.doc_id],
            "description": f"Subtotal mismatch: sum of lines={computed_subtotal:.2f}, stated subtotal={subtotal:.2f}",
            "reported_value": str(subtotal),
            "correct_value": str(round(computed_subtotal, 2)),
        })

    # 1c. Grand total ≠ subtotal + tax
    if subtotal and tax_amount and grand_total:
        expected_gt = round(subtotal + tax_amount, 2)
        if abs(expected_gt - grand_total) > 0.10:
            findings.append({
                "category": "arithmetic_error",
                "pages": seg.pages,
                "document_refs": [seg.doc_id],
                "description": f"Grand total: subtotal({subtotal}) + tax({tax_amount}) = {expected_gt}, but stated {grand_total}",
                "reported_value": str(grand_total),
                "correct_value": str(expected_gt),
            })

    # 1d. HyperAPI's own validation errors (billing_typo surface here too)
    for err in seg.parsed.get("validation_errors", []):
        if err.get("type") == "arithmetic":
            findings.append({
                "category": "arithmetic_error",
                "pages": seg.pages,
                "document_refs": [seg.doc_id],
                "description": err.get("message", "HyperAPI arithmetic error"),
                "reported_value": str(err.get("reported_value", "")),
                "correct_value": str(err.get("correct_value", "")),
            })
    return findings


def detect_billing_typos(seg: DocSegment) -> List[dict]:
    """
    HyperAPI's extract() returns validation_errors with type="billing_typo"
    when it detects that a decimal quantity like 0.15 should be 0:15 = 0.25 hrs.
    """
    findings = []
    for err in seg.parsed.get("validation_errors", []):
        if err.get("type") == "billing_typo":
            findings.append({
                "category": "billing_typo",
                "pages": seg.pages,
                "document_refs": [seg.doc_id],
                "description": err.get("message", "Decimal time notation used instead of HH:MM"),
                "reported_value": str(err.get("reported_value", "")),
                "correct_value": str(err.get("correct_value", "")),
            })

    # Fallback heuristic when SDK doesn't flag it
    for item in seg.parsed.get("line_items", []):
        activity = str(item.get("activity") or item.get("description") or "").lower()
        if "hour" not in activity and "time" not in activity:
            continue
        qty = _to_float(item.get("quantity"))
        if 0 < qty < 0.5 and (qty * 100) % 5 == 0:   # e.g. 0.15, 0.30, 0.45
            # Could be HH:MM mistyped as decimal
            minutes = round(qty * 100)
            corrected = round(minutes / 60, 4)
            rate   = _to_float(item.get("rate") or item.get("unit_price"))
            amount = _to_float(item.get("amount") or item.get("line_total"))
            if rate and amount and abs(corrected * rate - amount) < abs(qty * rate - amount):
                findings.append({
                    "category": "billing_typo",
                    "pages": seg.pages,
                    "document_refs": [seg.doc_id],
                    "description": (
                        f"Quantity {qty} looks like {minutes} minutes (0:{minutes:02d}) = {corrected} hrs; "
                        f"{corrected} × {rate} = {corrected*rate:.2f} matches amount {amount}"
                    ),
                    "reported_value": str(qty),
                    "correct_value": str(corrected),
                })
    return findings


def detect_duplicate_line_items(seg: DocSegment) -> List[dict]:
    findings = []
    seen: dict = {}
    for i, item in enumerate(seg.parsed.get("line_items", [])):
        key = (
            str(item.get("description") or "").strip().lower(),
            str(item.get("quantity") or ""),
            str(item.get("rate") or item.get("unit_price") or ""),
        )
        if key in seen:
            prev_i = seen[key]
            findings.append({
                "category": "duplicate_line_item",
                "pages": seg.pages,
                "document_refs": [seg.doc_id],
                "description": f"Line {prev_i+1} and line {i+1} are identical: {item.get('description')}",
                "reported_value": str(item.get("amount") or ""),
                "correct_value": "Remove duplicate line",
            })
        else:
            seen[key] = i
    return findings


def detect_invalid_dates(seg: DocSegment) -> List[dict]:
    """Check all date fields extracted from the document."""
    findings = []
    date_fields = ["invoice_date", "date", "po_date", "due_date", "delivery_date",
                   "period_start", "period_end", "statement_date"]

    for field in date_fields:
        raw = seg.parsed.get(field)
        if not raw:
            continue
        dt = _parse_date(str(raw))
        if dt is None:
            # Could not parse at all — try to extract day/month/year manually
            m = re.search(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})", str(raw))
            if m:
                day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if year < 100:
                    year += 2000
                if not _is_valid_date(day, month, year):
                    findings.append({
                        "category": "invalid_date",
                        "pages": seg.pages,
                        "document_refs": [seg.doc_id],
                        "description": f"Field '{field}' contains impossible date: {raw}",
                        "reported_value": str(raw),
                        "correct_value": "N/A — date does not exist",
                    })
    return findings


def detect_wrong_tax_rates(seg: DocSegment) -> List[dict]:
    """Cross-reference GST rate on invoice vs expected rate for the HSN/SAC code."""
    findings = []
    for item in seg.parsed.get("line_items", []):
        hsn = str(item.get("hsn") or item.get("sac") or item.get("hsn_sac") or "").strip()
        if not hsn:
            continue
        stated_rate = _to_float(item.get("tax_rate") or item.get("gst_rate"))
        expected    = HSN_TAX_RATE.get(hsn[:4])
        if expected and stated_rate and abs(stated_rate - expected) > 0.5:
            findings.append({
                "category": "wrong_tax_rate",
                "pages": seg.pages,
                "document_refs": [seg.doc_id],
                "description": (
                    f"HSN/SAC {hsn}: expected GST {expected}%, "
                    f"invoice shows {stated_rate}%"
                ),
                "reported_value": str(stated_rate),
                "correct_value": str(expected),
            })
    return findings


# ═══════════════════════════════════════════════════════════════════════════════
#  TIER 2 — MEDIUM  (cross-document checks)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_po_invoice_mismatches(
    invoices: List[DocSegment],
    pos: List[DocSegment],
) -> List[dict]:
    """Compare each invoice's qty/rate against its linked PO."""
    findings = []
    po_map = {s.doc_id: s for s in pos if s.doc_id}

    for inv in invoices:
        po_ref = inv.parsed.get("po_number") or inv.parsed.get("po_reference")
        if not po_ref:
            continue
        po = po_map.get(_normalize_ref(po_ref))
        if not po:
            continue

        for i, inv_item in enumerate(inv.parsed.get("line_items", [])):
            desc = str(inv_item.get("description") or "").lower()
            # Find matching line in PO by description
            po_item = next(
                (p for p in po.parsed.get("line_items", [])
                 if _fuzzy_match(desc, str(p.get("description") or "")) > 0.8),
                None,
            )
            if not po_item:
                continue

            inv_qty  = _to_float(inv_item.get("quantity"))
            po_qty   = _to_float(po_item.get("quantity"))
            inv_rate = _to_float(inv_item.get("rate") or inv_item.get("unit_price"))
            po_rate  = _to_float(po_item.get("rate") or po_item.get("unit_price"))

            if po_qty and abs(inv_qty - po_qty) / max(po_qty, 1) > 0.01:
                findings.append({
                    "category": "po_invoice_mismatch",
                    "pages": sorted(set(inv.pages + po.pages)),
                    "document_refs": [inv.doc_id, po_ref],
                    "description": f"Line {i+1} qty: invoice={inv_qty}, PO={po_qty}",
                    "reported_value": str(inv_qty),
                    "correct_value": str(po_qty),
                })
            if po_rate and abs(inv_rate - po_rate) / max(po_rate, 1) > 0.01:
                findings.append({
                    "category": "po_invoice_mismatch",
                    "pages": sorted(set(inv.pages + po.pages)),
                    "document_refs": [inv.doc_id, po_ref],
                    "description": f"Line {i+1} rate: invoice={inv_rate}, PO={po_rate}",
                    "reported_value": str(inv_rate),
                    "correct_value": str(po_rate),
                })
    return findings


def detect_vendor_name_typos(
    segments: List[DocSegment],
    vendor_master: dict,
) -> List[dict]:
    """Fuzzy-match vendor names against the Vendor Master."""
    findings = []
    known_names = list(vendor_master["by_name"].keys())  # all lowercase

    for seg in segments:
        inv_vendor = str(seg.parsed.get("vendor_name") or seg.parsed.get("supplier_name") or "").strip()
        if not inv_vendor:
            continue
        inv_lower = inv_vendor.lower()

        # Exact match → fine
        if inv_lower in vendor_master["by_name"]:
            continue

        # Find best fuzzy match
        best_score = 0.0
        best_name  = ""
        for name in known_names:
            score = _fuzzy_match(inv_lower, name)
            if score > best_score:
                best_score = score
                best_name  = name

        # 0.75–0.99 similarity = likely typo; <0.75 = possibly fake vendor
        if 0.75 <= best_score < 1.0:
            findings.append({
                "category": "vendor_name_typo",
                "pages": seg.pages,
                "document_refs": [seg.doc_id],
                "description": (
                    f"Vendor '{inv_vendor}' looks like a misspelling of '{best_name}' "
                    f"(similarity={best_score:.2f})"
                ),
                "reported_value": inv_vendor,
                "correct_value": best_name.title(),
            })
    return findings


def detect_double_payments(bank_statements: List[DocSegment]) -> List[dict]:
    """
    A double payment = same (vendor, amount, reference) appearing in two
    different bank statements.
    """
    findings = []
    payment_index: dict = {}   # key → (doc_id, page_no)

    for stmt in bank_statements:
        for txn in stmt.parsed.get("transactions", []):
            vendor = str(txn.get("payee") or txn.get("vendor") or "").strip().lower()
            amount = _to_float(txn.get("amount"))
            ref    = str(txn.get("reference") or txn.get("utr") or "").strip()
            if not (vendor and amount):
                continue
            key = (vendor, round(amount, 2), ref)
            if key in payment_index:
                prev_doc, prev_page = payment_index[key]
                findings.append({
                    "category": "double_payment",
                    "pages": sorted(set(stmt.pages + [prev_page])),
                    "document_refs": [stmt.doc_id, prev_doc],
                    "description": f"Payment to '{vendor}' of {amount} (ref={ref}) duplicated across two statements",
                    "reported_value": str(amount),
                    "correct_value": "Should appear only once",
                })
            else:
                payment_index[key] = (stmt.doc_id, stmt.pages[0])
    return findings


def detect_ifsc_mismatches(
    segments: List[DocSegment],
    vendor_master: dict,
) -> List[dict]:
    findings = []
    vendors = vendor_master["vendors"]
    by_name = vendor_master["by_name"]

    for seg in segments:
        inv_ifsc   = str(seg.parsed.get("bank_ifsc") or seg.parsed.get("ifsc") or "").strip().upper()
        inv_vendor = str(seg.parsed.get("vendor_name") or seg.parsed.get("supplier_name") or "").strip()
        if not inv_ifsc or not inv_vendor:
            continue
        vid = by_name.get(inv_vendor.lower())
        if not vid:
            continue
        expected_ifsc = vendors[vid]["ifsc"]
        if expected_ifsc and inv_ifsc != expected_ifsc:
            findings.append({
                "category": "ifsc_mismatch",
                "pages": seg.pages,
                "document_refs": [seg.doc_id],
                "description": f"IFSC on invoice ({inv_ifsc}) ≠ Vendor Master ({expected_ifsc})",
                "reported_value": inv_ifsc,
                "correct_value": expected_ifsc,
            })
    return findings


def detect_duplicate_expenses(expense_reports: List[DocSegment]) -> List[dict]:
    """Same expense line (description, amount, date) in two expense reports."""
    findings = []
    expense_index: dict = {}

    for er in expense_reports:
        for item in er.parsed.get("line_items", []):
            desc   = str(item.get("description") or "").strip().lower()
            amount = round(_to_float(item.get("amount")), 2)
            date   = str(item.get("date") or "")
            emp_id = str(er.parsed.get("employee_id") or er.parsed.get("employee") or "")
            key    = (emp_id, desc, amount, date)
            if key in expense_index:
                prev_doc = expense_index[key]
                findings.append({
                    "category": "duplicate_expense",
                    "pages": er.pages,
                    "document_refs": [er.doc_id, prev_doc],
                    "description": f"Expense '{desc}' ₹{amount} on {date} claimed in {prev_doc} and {er.doc_id}",
                    "reported_value": str(amount),
                    "correct_value": "Should appear in only one expense report",
                })
            else:
                expense_index[key] = er.doc_id
    return findings


def detect_date_cascade(
    invoices: List[DocSegment],
    pos: List[DocSegment],
) -> List[dict]:
    """Invoice date must not be earlier than its linked PO date."""
    findings = []
    po_map = {s.doc_id: s for s in pos if s.doc_id}

    for inv in invoices:
        po_ref = inv.parsed.get("po_number") or inv.parsed.get("po_reference")
        if not po_ref:
            continue
        po = po_map.get(_normalize_ref(po_ref))
        if not po:
            continue
        inv_date = _parse_date(str(inv.parsed.get("invoice_date") or ""))
        po_date  = _parse_date(str(po.parsed.get("po_date") or po.parsed.get("date") or ""))
        if inv_date and po_date and inv_date < po_date:
            findings.append({
                "category": "date_cascade",
                "pages": sorted(set(inv.pages + po.pages)),
                "document_refs": [inv.doc_id, po_ref],
                "description": (
                    f"Invoice date {inv_date.date()} is before PO date {po_date.date()}"
                ),
                "reported_value": str(inv_date.date()),
                "correct_value": f"Invoice date must be ≥ {po_date.date()}",
            })
    return findings


def detect_gstin_state_mismatch(
    segments: List[DocSegment],
    vendor_master: dict,
) -> List[dict]:
    """First 2 digits of GSTIN must match the state code for the vendor's state."""
    findings = []
    vendors  = vendor_master["vendors"]
    by_gstin = vendor_master["by_gstin"]

    for seg in segments:
        gstin = str(seg.parsed.get("gstin") or seg.parsed.get("vendor_gstin") or "").strip().upper()
        if not gstin or len(gstin) < 2:
            continue
        doc_state_code = gstin[:2]
        # Look up in vendor master
        vid = by_gstin.get(gstin)
        if not vid:
            continue
        master_state_code = vendors[vid]["state_code"]
        if master_state_code and doc_state_code != master_state_code:
            findings.append({
                "category": "gstin_state_mismatch",
                "pages": seg.pages,
                "document_refs": [seg.doc_id],
                "description": (
                    f"GSTIN {gstin} starts with '{doc_state_code}' but vendor is from "
                    f"state code '{master_state_code}'"
                ),
                "reported_value": doc_state_code,
                "correct_value": master_state_code,
            })
    return findings


# ═══════════════════════════════════════════════════════════════════════════════
#  TIER 3 — EVIL  (aggregated, multi-document)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_quantity_accumulation(
    invoices: List[DocSegment],
    pos: List[DocSegment],
    threshold: float = 1.20,
) -> List[dict]:
    """
    Sum qty across all invoices for a given (PO, line description).
    Flag if cumulative quantity exceeds PO quantity by >20%.
    """
    findings = []
    po_map = {s.doc_id: s for s in pos if s.doc_id}

    # Accumulate per (po_id, description)
    # Structure: { (po_id, desc_key): {"po_qty": float, "inv_qty": float, "docs": [...], "pages": [...]} }
    accumulator: Dict = defaultdict(lambda: {"po_qty": 0.0, "inv_qty": 0.0, "docs": [], "pages": []})

    for inv in invoices:
        po_ref = _normalize_ref(str(inv.parsed.get("po_number") or inv.parsed.get("po_reference") or ""))
        if not po_ref or po_ref not in po_map:
            continue
        po = po_map[po_ref]

        for item in inv.parsed.get("line_items", []):
            desc = str(item.get("description") or "").strip()
            if not desc:
                continue
            desc_key = desc.lower()[:50]
            key = (po_ref, desc_key)

            # Find PO qty for this line (only set once)
            if accumulator[key]["po_qty"] == 0.0:
                po_item = next(
                    (p for p in po.parsed.get("line_items", [])
                     if _fuzzy_match(desc_key, str(p.get("description") or "").lower()) > 0.8),
                    None,
                )
                if po_item:
                    accumulator[key]["po_qty"] = _to_float(po_item.get("quantity"))

            accumulator[key]["inv_qty"] += _to_float(item.get("quantity"))
            if inv.doc_id not in accumulator[key]["docs"]:
                accumulator[key]["docs"].append(inv.doc_id)
            accumulator[key]["pages"].extend(inv.pages)

    for (po_ref, desc_key), acc in accumulator.items():
        po_qty  = acc["po_qty"]
        inv_qty = acc["inv_qty"]
        if po_qty > 0 and inv_qty > po_qty * threshold:
            findings.append({
                "category": "quantity_accumulation",
                "pages": sorted(set(acc["pages"])),
                "document_refs": acc["docs"] + [po_ref],
                "description": (
                    f"PO {po_ref} '{desc_key}': PO qty={po_qty}, "
                    f"cumulative invoiced qty={inv_qty:.2f} ({inv_qty/po_qty*100:.1f}% of PO)"
                ),
                "reported_value": str(round(inv_qty, 2)),
                "correct_value": str(po_qty),
            })
    return findings


def detect_price_escalation(
    invoices: List[DocSegment],
    pos: List[DocSegment],
) -> List[dict]:
    """All invoices against a PO charge rates exceeding the contracted PO rate."""
    findings = []
    po_map = {s.doc_id: s for s in pos if s.doc_id}

    # Group invoices by PO
    inv_by_po: Dict[str, List] = defaultdict(list)
    for inv in invoices:
        po_ref = _normalize_ref(str(inv.parsed.get("po_number") or inv.parsed.get("po_reference") or ""))
        if po_ref:
            inv_by_po[po_ref].append(inv)

    for po_ref, po_invoices in inv_by_po.items():
        if len(po_invoices) < 2:   # need at least 2 to call it a pattern
            continue
        po = po_map.get(po_ref)
        if not po:
            continue

        for po_item in po.parsed.get("line_items", []):
            desc    = str(po_item.get("description") or "").lower()
            po_rate = _to_float(po_item.get("rate") or po_item.get("unit_price"))
            if not po_rate:
                continue

            escalated_docs  = []
            escalated_pages = []
            for inv in po_invoices:
                inv_item = next(
                    (i for i in inv.parsed.get("line_items", [])
                     if _fuzzy_match(desc, str(i.get("description") or "").lower()) > 0.8),
                    None,
                )
                if not inv_item:
                    continue
                inv_rate = _to_float(inv_item.get("rate") or inv_item.get("unit_price"))
                if inv_rate > po_rate * 1.001:
                    escalated_docs.append(inv.doc_id)
                    escalated_pages.extend(inv.pages)

            # Flag only if ALL invoices for this line exceeded the PO rate
            if len(escalated_docs) == len(po_invoices) and len(escalated_docs) >= 2:
                findings.append({
                    "category": "price_escalation",
                    "pages": sorted(set(escalated_pages + po.pages)),
                    "document_refs": escalated_docs + [po_ref],
                    "description": (
                        f"All {len(escalated_docs)} invoices against PO {po_ref} "
                        f"charge above contracted rate {po_rate} for '{desc}'"
                    ),
                    "reported_value": f"rates > {po_rate}",
                    "correct_value": str(po_rate),
                })
    return findings


def detect_balance_drift(bank_statements: List[DocSegment]) -> List[dict]:
    """
    Sort bank statements by period. Flag where opening balance of month N
    ≠ closing balance of month N-1.
    """
    findings = []

    # Sort by statement date
    def _stmt_date(s):
        d = _parse_date(str(s.parsed.get("statement_date") or s.parsed.get("date") or ""))
        return d or datetime(2000, 1, 1)

    sorted_stmts = sorted(bank_statements, key=_stmt_date)

    prev_closing: Optional[float] = None
    prev_doc: Optional[str] = None
    prev_page: Optional[int] = None

    for stmt in sorted_stmts:
        opening = _to_float(stmt.parsed.get("opening_balance"))
        closing = _to_float(stmt.parsed.get("closing_balance"))
        if prev_closing is not None and opening and abs(opening - prev_closing) > 0.50:
            findings.append({
                "category": "balance_drift",
                "pages": sorted(set(stmt.pages + [prev_page])),
                "document_refs": [stmt.doc_id, prev_doc],
                "description": (
                    f"Opening balance of {stmt.doc_id} ({opening}) ≠ "
                    f"closing balance of {prev_doc} ({prev_closing})"
                ),
                "reported_value": str(opening),
                "correct_value": str(prev_closing),
            })
        if closing:
            prev_closing = closing
            prev_doc     = stmt.doc_id
            prev_page    = stmt.pages[0]
    return findings


def detect_circular_references(
    credit_notes: List[DocSegment],
    debit_notes:  List[DocSegment],
) -> List[dict]:
    """
    Build a directed graph of credit/debit note references.
    A cycle = circular reference.
    """
    findings = []
    all_notes = credit_notes + debit_notes

    # Build graph: doc_id → [referenced doc_ids]
    graph: Dict[str, List[str]] = defaultdict(list)
    doc_map: Dict[str, DocSegment] = {}

    for note in all_notes:
        if note.doc_id:
            doc_map[note.doc_id] = note
            refs = (
                note.parsed.get("references", [])
                or note.parsed.get("against_invoice", [])
                or []
            )
            if isinstance(refs, str):
                refs = [refs]
            graph[note.doc_id].extend(refs)

    # DFS cycle detection
    def dfs(node, visited, stack, path):
        visited.add(node)
        stack.add(node)
        path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                result = dfs(neighbor, visited, stack, path)
                if result:
                    return result
            elif neighbor in stack:
                cycle_start = path.index(neighbor)
                return path[cycle_start:]
        stack.remove(node)
        path.pop()
        return None

    visited: set = set()
    for node in graph:
        if node not in visited:
            cycle = dfs(node, visited, set(), [])
            if cycle:
                cycle_docs = [d for d in cycle if d in doc_map]
                cycle_pages = []
                for d in cycle_docs:
                    cycle_pages.extend(doc_map[d].pages)
                findings.append({
                    "category": "circular_reference",
                    "pages": sorted(set(cycle_pages)),
                    "document_refs": cycle_docs,
                    "description": " → ".join(cycle) + " → (loop)",
                    "reported_value": " → ".join(cycle),
                    "correct_value": "All notes must trace to a real invoice",
                })
    return findings


def detect_triple_expense_claims(expense_reports: List[DocSegment]) -> List[dict]:
    """Same hotel/stay claimed in 3 or more expense reports."""
    findings = []
    claim_index: Dict = defaultdict(list)   # key → list of (doc_id, pages)

    for er in expense_reports:
        emp_id = str(er.parsed.get("employee_id") or "").strip()
        for item in er.parsed.get("line_items", []):
            desc   = str(item.get("description") or "").strip().lower()
            # Heuristic: hotel-related lines
            if not any(kw in desc for kw in ["hotel", "stay", "accommodation", "lodge", "room"]):
                continue
            amount = round(_to_float(item.get("amount")), 2)
            date   = str(item.get("date") or "")
            key    = (emp_id, desc[:40], amount, date)
            claim_index[key].append((er.doc_id, er.pages))

    for key, occurrences in claim_index.items():
        if len(occurrences) >= 3:
            all_docs  = [o[0] for o in occurrences]
            all_pages = [p for o in occurrences for p in o[1]]
            findings.append({
                "category": "triple_expense_claim",
                "pages": sorted(set(all_pages)),
                "document_refs": all_docs,
                "description": (
                    f"Hotel expense '{key[1]}' ₹{key[2]} on {key[3]} "
                    f"claimed in {len(occurrences)} expense reports"
                ),
                "reported_value": str(key[2]),
                "correct_value": "Should appear in only one expense report",
            })
    return findings


def detect_employee_id_collision(expense_reports: List[DocSegment]) -> List[dict]:
    """Same Employee ID used by two different employee names."""
    findings = []
    emp_id_to_name: Dict[str, tuple] = {}   # emp_id → (name, doc_id, page)

    for er in expense_reports:
        emp_id   = str(er.parsed.get("employee_id") or "").strip()
        emp_name = str(er.parsed.get("employee_name") or er.parsed.get("employee") or "").strip().lower()
        if not emp_id or not emp_name:
            continue

        if emp_id in emp_id_to_name:
            known_name, known_doc, known_page = emp_id_to_name[emp_id]
            if _fuzzy_match(emp_name, known_name) < 0.85:
                findings.append({
                    "category": "employee_id_collision",
                    "pages": sorted(set(er.pages + [known_page])),
                    "document_refs": [er.doc_id, known_doc],
                    "description": (
                        f"Employee ID {emp_id} used by '{emp_name}' ({er.doc_id}) "
                        f"and '{known_name}' ({known_doc})"
                    ),
                    "reported_value": f"{emp_id} → {emp_name}",
                    "correct_value": f"{emp_id} should map to only one person",
                })
        else:
            emp_id_to_name[emp_id] = (emp_name, er.doc_id, er.pages[0])
    return findings


def detect_fake_vendors(
    segments: List[DocSegment],
    vendor_master: dict,
) -> List[dict]:
    """Invoice from a vendor whose name is not in the Vendor Master (low fuzzy similarity)."""
    findings = []
    known_names = list(vendor_master["by_name"].keys())
    by_gstin    = vendor_master["by_gstin"]

    for seg in segments:
        if seg.doc_type not in ("invoice", "receipt"):
            continue
        inv_vendor = str(seg.parsed.get("vendor_name") or seg.parsed.get("supplier_name") or "").strip()
        inv_gstin  = str(seg.parsed.get("gstin") or seg.parsed.get("vendor_gstin") or "").strip().upper()
        if not inv_vendor:
            continue

        # If GSTIN is known, it's a real vendor
        if inv_gstin and inv_gstin in by_gstin:
            continue

        # Check name similarity
        best_score = max((_fuzzy_match(inv_vendor.lower(), n) for n in known_names), default=0.0)
        if best_score < 0.70:
            findings.append({
                "category": "fake_vendor",
                "pages": seg.pages,
                "document_refs": [seg.doc_id],
                "description": (
                    f"Vendor '{inv_vendor}' not found in Vendor Master "
                    f"(best match similarity={best_score:.2f})"
                ),
                "reported_value": inv_vendor,
                "correct_value": "Vendor not registered in master",
            })
    return findings


def detect_phantom_po_references(
    invoices: List[DocSegment],
    pos: List[DocSegment],
) -> List[dict]:
    """Invoice cites a PO number that doesn't exist in the dataset."""
    findings = []
    known_po_ids = {_normalize_ref(s.doc_id) for s in pos if s.doc_id}

    for inv in invoices:
        po_ref = str(inv.parsed.get("po_number") or inv.parsed.get("po_reference") or "").strip()
        if not po_ref:
            continue
        if _normalize_ref(po_ref) not in known_po_ids:
            findings.append({
                "category": "phantom_po_reference",
                "pages": inv.pages,
                "document_refs": [inv.doc_id],
                "description": f"Invoice references PO '{po_ref}' which does not exist in the dataset",
                "reported_value": po_ref,
                "correct_value": "No matching PO found",
            })
    return findings


# ═══════════════════════════════════════════════════════════════════════════════
#  MASTER ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def run_all_detectors(
    parsed_docs: List[DocSegment],
    vendor_master: dict,
) -> List[dict]:
    """
    Run every detector and return a deduplicated list of findings.
    """
    # ── Partition by doc type ─────────────────────────────────────────────────
    invoices        = [d for d in parsed_docs if d.doc_type == "invoice"]
    pos             = [d for d in parsed_docs if d.doc_type == "po"]
    bank_statements = [d for d in parsed_docs if d.doc_type == "bank_statement"]
    expense_reports = [d for d in parsed_docs if d.doc_type == "expense_report"]
    credit_notes    = [d for d in parsed_docs if d.doc_type == "credit_note"]
    debit_notes     = [d for d in parsed_docs if d.doc_type == "debit_note"]
    all_segments    = parsed_docs

    log.info(f"  Invoices={len(invoices)} POs={len(pos)} BankStmts={len(bank_statements)} "
             f"ExpReps={len(expense_reports)} CN={len(credit_notes)} DN={len(debit_notes)}")

    all_findings: List[dict] = []

    # ── EASY ─────────────────────────────────────────────────────────────────
    log.info("  Running EASY detectors…")
    for seg in parsed_docs:
        all_findings += detect_arithmetic_errors(seg)
        all_findings += detect_billing_typos(seg)
        all_findings += detect_duplicate_line_items(seg)
        all_findings += detect_invalid_dates(seg)
        if seg.doc_type == "invoice":
            all_findings += detect_wrong_tax_rates(seg)

    # ── MEDIUM ───────────────────────────────────────────────────────────────
    log.info("  Running MEDIUM detectors…")
    all_findings += detect_po_invoice_mismatches(invoices, pos)
    all_findings += detect_vendor_name_typos(all_segments, vendor_master)
    all_findings += detect_double_payments(bank_statements)
    all_findings += detect_ifsc_mismatches(all_segments, vendor_master)
    all_findings += detect_duplicate_expenses(expense_reports)
    all_findings += detect_date_cascade(invoices, pos)
    all_findings += detect_gstin_state_mismatch(all_segments, vendor_master)

    # ── EVIL ─────────────────────────────────────────────────────────────────
    log.info("  Running EVIL detectors…")
    all_findings += detect_quantity_accumulation(invoices, pos)
    all_findings += detect_price_escalation(invoices, pos)
    all_findings += detect_balance_drift(bank_statements)
    all_findings += detect_circular_references(credit_notes, debit_notes)
    all_findings += detect_triple_expense_claims(expense_reports)
    all_findings += detect_employee_id_collision(expense_reports)
    all_findings += detect_fake_vendors(all_segments, vendor_master)
    all_findings += detect_phantom_po_references(invoices, pos)

    log.info(f"  Total raw findings: {len(all_findings)}")

    # ── Deduplication ─────────────────────────────────────────────────────────
    deduped = _deduplicate(all_findings)
    log.info(f"  After deduplication: {len(deduped)}")
    return deduped


def _deduplicate(findings: List[dict]) -> List[dict]:
    """
    Remove near-duplicate findings.
    Two findings are duplicates if they share:
      - same category
      - ≥50% overlap in document_refs
    """
    kept = []
    for f in findings:
        is_dup = False
        f_refs = set(_normalize_ref(r) for r in f.get("document_refs", []))
        for k in kept:
            if k["category"] != f["category"]:
                continue
            k_refs = set(_normalize_ref(r) for r in k.get("document_refs", []))
            if not f_refs or not k_refs:
                continue
            overlap = len(f_refs & k_refs) / max(len(f_refs | k_refs), 1)
            if overlap >= 0.5:
                is_dup = True
                # Keep the one with more info (longer description)
                if len(f.get("description", "")) > len(k.get("description", "")):
                    kept.remove(k)
                    kept.append(f)
                break
        if not is_dup:
            kept.append(f)
    return kept
