# Financial Gauntlet — HyperAPI Pipeline

An AI-powered 5-stage pipeline for detecting financial errors in documents. Processes a 1,000-page Accounts Payable bundle and identifies up to 200 deliberate errors across 20 categories.

## Architecture

```
gauntlet.pdf (1,000 pages)
    │
    ▼
Stage 1: Vendor Master (pages 3–4)
    │  → 35 vendor records + indices
    ▼
Stage 2: Document Splitter (pages 5–1000)
    │  → ~750 DocSegment objects
    ▼
Stage 3: HyperAPI Parser (cached)
    │  → OCR + structured extraction
    ▼
Stage 4: Needle Detectors
    │  → 20 error categories (Easy/Medium/Evil)
    ▼
Stage 5: Output
    │  → findings.json
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
pip install -e hyperapi-sdk/
```

### 2. Set Environment Variables

```bash
export HYPERAPI_KEY="your-key-here"
export HYPERAPI_URL="https://your-hyperapi-endpoint"
export TEAM_ID="your_team_name"
```

Optional:
```bash
export GAUNTLET_PDF="gauntlet.pdf"   # path to PDF
export CACHE_DIR=".cache"            # cache directory
export OUTPUT_FILE="findings.json"   # output path
```

### 3. Test API Connection

Before running the full pipeline, test your API connection:

```bash
python test_api.py
```

This will test all 4 API endpoints:
- `/api/v1/parse` - Extract text from documents
- `/api/v1/extract` - Extract structured data fields
- `/api/v1/classify` - Categorize document types
- `/api/v1/split` - Split multi-page documents

### 4. Run Pipeline

```bash
python -m logic.pipeline
```

Or:
```bash
python logic/pipeline.py
```

## Features

### HyperAPI Endpoints

The pipeline uses 4 main HyperAPI endpoints:

1. **POST /api/v1/parse** - Extract text from documents including PDFs and images. Optimized for financial documents, invoices, and forms.
   - Input: Document file (PNG, JPG, PDF)
   - Output: OCR text

2. **POST /api/v1/extract** - Extract structured data fields from documents using vision-language models for high accuracy.
   - Input: OCR text
   - Output: Structured fields (invoice_number, vendor_name, line_items, etc.) + validation_errors

3. **POST /api/v1/classify** - Categorize document types automatically — invoices, contracts, receipts, IDs, and more.
   - Input: Document file
   - Output: document_type + confidence score

4. **POST /api/v1/split** - Split multi-page documents into individual pages or logical sections for downstream processing.
   - Input: Multi-page PDF
   - Output: Pages and sections information

### Robust Error Handling
- Exponential backoff retry (2s, 5s, 15s, 30s)
- Connection error resilience (httpx.ConnectError, TimeoutException, NetworkError)
- Graceful degradation for missing fields
- PDF rendering error handling

### Caching Strategy
- Per-page OCR caching: `.cache/ocr_NNNN.json`
- Per-document extraction caching:
  - `.cache/extract_{hash}.json` (base extraction)
  - `.cache/entities_{hash}.json` (vendor/GSTIN/IFSC/dates)
  - `.cache/lineitems_{hash}.json` (validated line items for invoices)

### Parallelization
- ThreadPoolExecutor with 8 workers
- Semaphore-based API rate limiting (max 8 concurrent calls)
- Thread-safe PDF rendering

### 20 Error Detectors

**Easy (5 types, ~40 pts):**
1. `arithmetic_error` — qty×rate ≠ amount, subtotal mismatches
2. `billing_typo` — decimal time notation (0.15 vs 0:15)
3. `duplicate_line_item` — same line repeated
4. `invalid_date` — impossible calendar dates
5. `wrong_tax_rate` — GST rate doesn't match HSN/SAC

**Medium (7 types, ~180 pts):**
6. `po_invoice_mismatch` — invoice qty/rate differs from PO
7. `vendor_name_typo` — vendor name typos
8. `double_payment` — duplicate payments in bank statements
9. `ifsc_mismatch` — IFSC code mismatches
10. `duplicate_expense` — duplicate expense claims
11. `date_cascade` — invoice date before PO date
12. `gstin_state_mismatch` — GSTIN state code mismatches

**Evil (8 types, ~700 pts):**
13. `quantity_accumulation` — cumulative qty exceeds PO by >20%
14. `price_escalation` — all invoices charge above PO rate
15. `balance_drift` — bank statement balance inconsistencies
16. `circular_reference` — credit/debit note cycles
17. `triple_expense_claim` — hotel expenses claimed 3+ times
18. `employee_id_collision` — same ID with different names
19. `fake_vendor` — vendor not in master (low similarity)
20. `phantom_po_reference` — invoice references non-existent PO

## Performance

- **Cold cache (first run):** ~10 minutes for Stage 3 parsing
- **Warm cache (subsequent runs):** <30 seconds for Stage 3
- **Stage 2 (splitting):** <10 seconds
- **Stage 4 (detection):** <5 seconds
- **Stage 5 (output):** <1 second

## Output Format

```json
{
  "team_id": "your_team_name",
  "findings": [
    {
      "finding_id": "F-001",
      "category": "arithmetic_error",
      "pages": [47, 48],
      "document_refs": ["INV-2025-0042"],
      "description": "Line 3: qty=2 × rate=100 = 200, but invoice shows 150",
      "reported_value": "150",
      "correct_value": "200"
    }
  ]
}
```

## Logging

All logs are written to:
- Console (stdout)
- `pipeline.log` file

Log levels:
- INFO: Stage progress, document counts, timing
- WARNING: Cache failures, API retries, missing data
- ERROR: Fatal errors, API exhaustion

## Troubleshooting

### Quick Setup Validation

Run the validation script to check your setup:

```bash
./validate_setup.sh
```

This checks:
- Python version (>= 3.8)
- Required files exist
- Environment variables are set
- Python packages are installed
- PDF file is correct
- Cache directory status

### API Connection Errors
- Check `HYPERAPI_KEY` and `HYPERAPI_URL` environment variables
- Verify network connectivity
- Check API rate limits

### Cache Issues
- Clear cache: `rm -rf .cache/`
- Check disk space
- Verify write permissions

### PDF Rendering Errors
- Ensure PyMuPDF is installed: `pip install pymupdf>=1.23.0`
- Check PDF file integrity
- Verify sufficient memory

## Development

### Project Structure
```
.
├── logic/
│   ├── __init__.py
│   ├── pipeline.py        # Entry point
│   ├── vendor_master.py   # Stage 1
│   ├── splitter.py        # Stage 2
│   ├── parser.py          # Stage 3
│   ├── detectors.py       # Stage 4 (all 20 detectors)
│   └── output.py          # Stage 5
├── hyperapi-sdk/          # HyperAPI Python SDK
│   ├── hyperapi/
│   │   ├── __init__.py
│   │   ├── client.py      # API client with all 4 endpoints
│   │   └── exceptions.py  # Custom exceptions
│   └── pyproject.toml
├── test_api.py            # API endpoint testing script
├── validate_setup.sh      # Setup validation script
├── requirements.txt
├── README.md              # This file
├── QUICKSTART.md          # Step-by-step guide
├── CHANGES.md             # API endpoint corrections
├── .gitignore
└── gauntlet.pdf           # 1,000-page dataset

```

### Documentation

- **README.md** (this file) - Overview and reference
- **QUICKSTART.md** - Step-by-step setup and usage guide
- **CHANGES.md** - Detailed API endpoint corrections and migration guide

### Running Tests
```bash
# Validate setup
./validate_setup.sh

# Test API endpoints
python test_api.py

# Run full pipeline
python -m logic.pipeline

# Check for lint errors
# (No errors found in current implementation)
```

## License

MIT License
