"""
Stage 1 — Vendor Master Extraction
===================================
Parses pages 3–4 of the PDF and returns a dict keyed by vendor_id:
  {
    "V001": {
      "name": "Acme Supplies Pvt Ltd",
      "gstin": "29AABCA1234F1Z5",
      "state_code": "29",
      "state": "Karnataka",
      "ifsc": "HDFC0001234",
      "bank_account": "...",
    },
    ...
  }
"""

import json
import logging
import hashlib
from pathlib import Path

import fitz  # PyMuPDF — used only for page-to-image conversion

log = logging.getLogger(__name__)

# HSN/SAC state code → state name lookup (subset)
STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana",
    "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
    "13": "Nagaland", "14": "Manipur", "15": "Mizoram",
    "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra & Nagar Haveli / Daman & Diu",
    "27": "Maharashtra", "28": "Andhra Pradesh", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala",
    "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman & Nicobar",
    "36": "Telangana", "37": "Andhra Pradesh (New)",
}

_EXTRACTION_PROMPT = """
You are extracting a Vendor Master table from a financial document.
Return ONLY a JSON array — no markdown, no commentary.

Each element must have these fields (use null if not found):
  vendor_id, name, gstin, bank_account, ifsc, state, address

Example:
[
  {
    "vendor_id": "V001",
    "name": "Acme Supplies Pvt Ltd",
    "gstin": "29AABCA1234F1Z5",
    "bank_account": "1234567890",
    "ifsc": "HDFC0001234",
    "state": "Karnataka",
    "address": "12, MG Road, Bengaluru"
  }
]
"""


def _page_to_image(pdf_path: Path, page_no: int, dpi: int = 200) -> Path:
    """Render a single PDF page to a PNG and return its path."""
    doc = fitz.open(str(pdf_path))
    page = doc[page_no - 1]                    # 0-indexed
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    out = Path(f"/tmp/page_{page_no:04d}.png")
    pix.save(str(out))
    doc.close()
    return out


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{hashlib.md5(key.encode()).hexdigest()}.json"


def extract_vendor_master(client, pdf_path: Path, cache_dir: Path) -> dict:
    """
    Parse pages 3–4, extract vendor records, return vendor_master dict.
    """
    cache_file = _cache_path(cache_dir, "vendor_master_v1")
    if cache_file.exists():
        log.info("  [cache hit] vendor master")
        return json.loads(cache_file.read_text())

    vendor_master = {}

    for page_no in [3, 4]:
        img_path = _page_to_image(pdf_path, page_no)

        # Step 1 — OCR
        ocr_result = client.parse(str(img_path))
        ocr_text = ocr_result["ocr"]

        # Step 2 — Structured extraction
        # We pass the extraction prompt inside the OCR text as a directive
        extraction_input = _EXTRACTION_PROMPT + "\n\nDocument text:\n" + ocr_text
        extracted = client.extract(extraction_input)

        # `data` may be a list or dict depending on SDK version
        data = extracted.get("data", [])
        if isinstance(data, dict):
            data = data.get("vendors", []) or data.get("line_items", []) or [data]

        for vendor in data:
            if not isinstance(vendor, dict):
                continue
            vid   = str(vendor.get("vendor_id") or vendor.get("name", "UNKNOWN"))
            gstin = (vendor.get("gstin") or "").strip().upper()
            state_code = gstin[:2] if len(gstin) >= 2 else ""
            vendor_master[vid] = {
                "name":         (vendor.get("name") or "").strip(),
                "gstin":        gstin,
                "state_code":   state_code,
                "state":        STATE_CODES.get(state_code, vendor.get("state", "")),
                "ifsc":         (vendor.get("ifsc") or "").strip().upper(),
                "bank_account": (vendor.get("bank_account") or "").strip(),
                "address":      (vendor.get("address") or "").strip(),
                "source_page":  page_no,
            }

    # Also build secondary indices for faster lookups downstream
    by_name  = {v["name"].lower(): k for k, v in vendor_master.items() if v["name"]}
    by_gstin = {v["gstin"]: k       for k, v in vendor_master.items() if v["gstin"]}
    result = {
        "vendors":  vendor_master,
        "by_name":  by_name,
        "by_gstin": by_gstin,
    }

    cache_file.write_text(json.dumps(result, indent=2))
    log.info(f"  Extracted {len(vendor_master)} vendors from pages 3–4")
    return result
