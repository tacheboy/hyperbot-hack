# Financial Gauntlet — HyperAPI Pipeline

## Architecture

```
gauntlet.pdf
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ Stage 1: Vendor Master (pages 3–4)                      │
│   client.parse(page_img) → OCR text                     │
│   client.extract(ocr)    → 35 vendor records + indices  │
└────────────────────────┬────────────────────────────────┘
                         │  vendor_master dict
    ┌────────────────────▼────────────────────────────────┐
    │ Stage 2: Document Splitter (pages 5–1000)           │
    │   PyMuPDF fast text layer (no API calls)            │
    │   Regex signatures → ~750 DocSegment objects        │
    └────────────────────┬────────────────────────────────┘
                         │  List[DocSegment]
    ┌────────────────────▼────────────────────────────────┐
    │ Stage 3: HyperAPI Parser (cached)                   │
    │   Per page  : client.parse(img)   → OCR text        │
    │   Per doc   : client.extract(ocr) → structured dict │
    │   Cache     : .cache/ocr_NNNN.json                  │
    │               .cache/extract_<hash>.json            │
    └────────────────────┬────────────────────────────────┘
                         │  parsed_docs (segments with .parsed)
    ┌────────────────────▼────────────────────────────────┐
    │ Stage 4: Needle Detectors                           │
    │  EASY   (5 types)  — single-doc checks              │
    │  MEDIUM (7 types)  — cross-doc checks               │
    │  EVIL   (8 types)  — aggregated / multi-doc         │
    │  → deduplication                                    │
    └────────────────────┬────────────────────────────────┘
                         │  List[Finding]
    ┌────────────────────▼────────────────────────────────┐
    │ Stage 5: Output                                     │
    │   Validates categories, assigns F-NNN IDs           │
    │   → findings.json                                   │
    └─────────────────────────────────────────────────────┘
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables
export HYPERAPI_KEY="your-key-here"
export HYPERAPI_URL="https://your-hyperapi-endpoint"
export TEAM_ID="your_team_name"

# 3. Run
python pipeline.py
```

Optional env vars:
```
GAUNTLET_PDF=gauntlet.pdf   # path to PDF
CACHE_DIR=.cache            # where to store OCR/extraction cache
OUTPUT_FILE=findings.json   # output path
```

## Caching

On first run, every page is rendered to PNG and OCR'd via HyperAPI. Results
are saved in `.cache/`. On subsequent runs (e.g. after tweaking a detector),
all OCR calls are skipped — only the detectors re-run.

To force a full re-parse: `rm -rf .cache/`

## File Layout

```
gauntlet_pipeline/
├── pipeline.py               # entry point
├── requirements.txt
├── stages/
│   ├── __init__.py
│   ├── vendor_master.py      # Stage 1
│   ├── splitter.py           # Stage 2
│   ├── parser.py             # Stage 3
│   ├── detectors.py          # Stage 4 — all 20 needle detectors
│   └── output.py             # Stage 5
└── README.md
```

## Scoring Strategy

| Tier   | Points  | Strategy                                           |
|--------|---------|----------------------------------------------------|
| Easy   | 40 pts  | Run first — fast wins, validate arithmetic dates   |
| Medium | 180 pts | PO↔Invoice cross-ref + vendor fuzzy match          |
| Evil   | 700 pts | Quantity accumulation + balance drift are highest  |

**False positive penalty**: −0.5 per unmatched finding, capped at 20% of
earned score. Only report findings where confidence is high.

## Tuning Tips

- `HSN_TAX_RATE` dict in `detectors.py` — add more HSN codes as you see them
- `threshold=1.20` in `detect_quantity_accumulation` — lower to catch more
- `best_score < 0.70` in `detect_fake_vendors` — raise to reduce false positives
- `_fuzzy_match > 0.8` line-item matching — lower to be more lenient on PO matching
