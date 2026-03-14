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
import time
from pathlib import Path

from hyperapi import HyperAPIClient

from logic.vendor_master import extract_vendor_master
from logic.splitter import split_and_classify
from logic.parser import parse_all_docs
from logic.detectors import run_all_detectors
from logic.output import build_findings_json

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
    """Main pipeline orchestration with error handling and timing."""
    start_time = time.time()
    
    log.info("=== Financial Gauntlet Pipeline starting ===")
    log.info(f"PDF      : {PDF_PATH}")
    log.info(f"Cache    : {CACHE_DIR}")
    log.info(f"Output   : {OUTPUT}")
    log.info(f"Team ID  : {TEAM_ID}")
    
    # Validate PDF exists
    if not PDF_PATH.exists():
        log.error(f"PDF file not found: {PDF_PATH}")
        sys.exit(1)
    
    # Validate API credentials
    if not os.environ.get("HYPERAPI_KEY"):
        log.error("HYPERAPI_KEY environment variable not set")
        sys.exit(1)
    if not os.environ.get("HYPERAPI_URL"):
        log.error("HYPERAPI_URL environment variable not set")
        sys.exit(1)

    try:
        # ── 0. HyperAPI client ────────────────────────────────────────────────
        log.info("Initializing HyperAPI client…")
        client = HyperAPIClient(
            api_key=os.environ["HYPERAPI_KEY"],
            base_url=os.environ["HYPERAPI_URL"],
            timeout=180.0,          # generous for dense pages
        )

        # ── 1. Vendor Master (pages 3–4) ─────────────────────────────────────
        stage_start = time.time()
        log.info("Stage 1 — Vendor Master")
        vendor_master = extract_vendor_master(client, PDF_PATH, CACHE_DIR)
        
        if not vendor_master or not vendor_master.get("vendors"):
            raise RuntimeError("Vendor master extraction returned empty result")
        
        vendor_count = len(vendor_master["vendors"])
        log.info(f"  Loaded {vendor_count} vendors")
        
        if vendor_count < 30:
            log.warning(f"  WARNING: Only {vendor_count} vendors extracted (expected ≥30)")
        
        log.info(f"  Stage 1 completed in {time.time() - stage_start:.1f}s")

        # ── 2. Split & classify pages 5–1000 ────────────────────────────────
        stage_start = time.time()
        log.info("Stage 2 — Document splitting")
        doc_segments = split_and_classify(PDF_PATH, page_start=5, page_end=1000)
        log.info(f"  Found {len(doc_segments)} document segments")
        log.info(f"  Stage 2 completed in {time.time() - stage_start:.1f}s")

        # ── 3. Parse every segment via HyperAPI (cached) ────────────────────
        stage_start = time.time()
        log.info("Stage 3 — Parsing documents")
        parsed_docs = parse_all_docs(client, PDF_PATH, doc_segments, CACHE_DIR)
        log.info(f"  Parsed {len(parsed_docs)} documents")
        log.info(f"  Stage 3 completed in {time.time() - stage_start:.1f}s")

        # ── 4. Needle detection ──────────────────────────────────────────────
        stage_start = time.time()
        log.info("Stage 4 — Needle detection")
        findings = run_all_detectors(parsed_docs, vendor_master)
        log.info(f"  Final findings count: {len(findings)}")
        log.info(f"  Stage 4 completed in {time.time() - stage_start:.1f}s")

        # ── 5. Output ────────────────────────────────────────────────────────
        stage_start = time.time()
        log.info("Stage 5 — Writing output")
        result = build_findings_json(TEAM_ID, findings)
        
        try:
            OUTPUT.write_text(json.dumps(result, indent=2))
            log.info(f"  Written {len(result['findings'])} findings → {OUTPUT}")
        except IOError as e:
            log.error(f"  Failed to write findings.json: {e}")
            raise
        
        log.info(f"  Stage 5 completed in {time.time() - stage_start:.1f}s")
        
        # ── Summary ──────────────────────────────────────────────────────────
        total_time = time.time() - start_time
        log.info("=== Pipeline completed successfully ===")
        log.info(f"Total execution time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
        log.info(f"Final output: {len(result['findings'])} findings in {OUTPUT}")
        
    except KeyboardInterrupt:
        log.warning("Pipeline interrupted by user")
        sys.exit(130)
    except Exception as e:
        log.error(f"Pipeline failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
