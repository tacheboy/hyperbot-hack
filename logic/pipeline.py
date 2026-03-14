"""
Financial Gauntlet — HyperAPI Pipeline
=======================================
Entry point. Orchestrates all stages:
  1. Vendor Master extraction (pages 3–4)
  2. Document splitting & classification (pages 5–1000)
  3. Per-doc parsing + extraction (with caching)
  4. Needle detection across all 20 categories
  5. Deduplication + JSON output
"""

import os
import sys
import json
import logging
from pathlib import Path

from hyperapi import HyperAPIClient

from stages.vendor_master   import extract_vendor_master
from stages.splitter        import split_and_classify
from stages.parser          import parse_all_docs
from stages.detectors       import run_all_detectors
from stages.output          import build_findings_json

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log"),
    ],
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
PDF_PATH   = Path(os.getenv("GAUNTLET_PDF",  "gauntlet.pdf"))
CACHE_DIR  = Path(os.getenv("CACHE_DIR",     ".cache"))
OUTPUT     = Path(os.getenv("OUTPUT_FILE",   "findings.json"))
TEAM_ID    = os.getenv("TEAM_ID", "your_team_name")

CACHE_DIR.mkdir(exist_ok=True)


def main():
    log.info("=== Financial Gauntlet Pipeline starting ===")
    log.info(f"PDF      : {PDF_PATH}")
    log.info(f"Cache    : {CACHE_DIR}")
    log.info(f"Output   : {OUTPUT}")

    # ── 0. HyperAPI client ────────────────────────────────────────────────────
    client = HyperAPIClient(
        api_key=os.environ["HYPERAPI_KEY"],
        base_url=os.environ["HYPERAPI_URL"],
        timeout=180.0,          # generous for dense pages
    )

    # ── 1. Vendor Master (pages 3–4) ─────────────────────────────────────────
    log.info("Stage 1 — Vendor Master")
    vendor_master = extract_vendor_master(client, PDF_PATH, CACHE_DIR)
    log.info(f"  Loaded {len(vendor_master)} vendors")

    # ── 2. Split & classify pages 5–1000 ────────────────────────────────────
    log.info("Stage 2 — Document splitting")
    doc_segments = split_and_classify(PDF_PATH, page_start=5, page_end=1000)
    log.info(f"  Found {len(doc_segments)} document segments")

    # ── 3. Parse every segment via HyperAPI (cached) ────────────────────────
    log.info("Stage 3 — Parsing documents")
    parsed_docs = parse_all_docs(client, PDF_PATH, doc_segments, CACHE_DIR)
    log.info(f"  Parsed {len(parsed_docs)} documents")

    # ── 4. Needle detection ──────────────────────────────────────────────────
    log.info("Stage 4 — Needle detection")
    findings = run_all_detectors(parsed_docs, vendor_master)
    log.info(f"  Raw findings : {len(findings)}")

    # ── 5. Output ────────────────────────────────────────────────────────────
    log.info("Stage 5 — Writing output")
    result = build_findings_json(TEAM_ID, findings)
    OUTPUT.write_text(json.dumps(result, indent=2))
    log.info(f"  Written {len(result['findings'])} findings → {OUTPUT}")
    log.info("=== Done ===")


if __name__ == "__main__":
    main()
