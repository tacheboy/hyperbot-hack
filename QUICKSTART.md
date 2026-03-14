# Quick Start Guide

## Prerequisites

1. Python 3.8 or higher
2. HyperAPI credentials (API key and URL)
3. The gauntlet.pdf file (1,000-page financial document bundle)

## Installation

### Step 1: Clone or download the repository

```bash
cd /path/to/project
```

### Step 2: Install dependencies

```bash
# Install required packages
pip install -r requirements.txt

# Install HyperAPI SDK in development mode
pip install -e hyperapi-sdk/
```

This will install:
- `pymupdf>=1.23.0` - PDF rendering and text extraction
- `httpx>=0.27.0` - HTTP client for API calls
- `hyperapi` SDK - Custom SDK for HyperAPI endpoints

## Configuration

### Step 3: Set environment variables

Create a `.env` file or export variables:

```bash
# Required
export HYPERAPI_KEY="your-api-key-here"
export HYPERAPI_URL="https://your-hyperapi-endpoint.com"
export TEAM_ID="your_team_name"

# Optional (defaults shown)
export GAUNTLET_PDF="gauntlet.pdf"
export CACHE_DIR=".cache"
export OUTPUT_FILE="findings.json"
```

Or create a `.env` file:

```bash
cat > .env << EOF
HYPERAPI_KEY=your-api-key-here
HYPERAPI_URL=https://your-hyperapi-endpoint.com
TEAM_ID=your_team_name
GAUNTLET_PDF=gauntlet.pdf
CACHE_DIR=.cache
OUTPUT_FILE=findings.json
EOF
```

Then load it:

```bash
source .env
```

## Testing

### Step 4: Test API connection

Before running the full pipeline, verify your API credentials work:

```bash
python test_api.py
```

This will test all 4 endpoints:
- ✓ `/api/v1/parse` - OCR extraction
- ✓ `/api/v1/extract` - Structured data extraction
- ✓ `/api/v1/classify` - Document classification
- ✓ `/api/v1/split` - Document splitting

Expected output:
```
============================================================
HyperAPI Endpoint Tests
============================================================
✓ HYPERAPI_KEY: sk-1234567...
✓ HYPERAPI_URL: https://api.example.com

============================================================
Testing /api/v1/parse endpoint
============================================================
✓ Rendered test page to /tmp/test_page_5.png
✓ Parse successful
  OCR text length: 1234 characters
  First 200 chars: TAX INVOICE...

============================================================
Testing /api/v1/extract endpoint
============================================================
✓ Extract successful
  Extracted data keys: ['invoice_number', 'vendor_name', 'total', 'line_items']
  Invoice Number: INV-2025-0001
  Vendor Name: Acme Supplies Pvt Ltd
  Total: 1475.00
  Line Items: 2 items

============================================================
Test Summary
============================================================
✓ PASS: parse
✓ PASS: extract
✓ PASS: classify
✓ PASS: split

Total: 4/4 tests passed
```

## Running the Pipeline

### Step 5: Run the full pipeline

```bash
python -m logic.pipeline
```

Or:

```bash
python logic/pipeline.py
```

### What happens during execution:

**First Run (Cold Cache):**
```
=== Financial Gauntlet Pipeline starting ===
PDF      : gauntlet.pdf
Cache    : .cache
Output   : findings.json
Team ID  : your_team_name

Stage 1 — Vendor Master
  Loaded 35 vendors
  Stage 1 completed in 15.2s

Stage 2 — Document splitting
  Found 753 document segments
  Stage 2 completed in 8.4s

Stage 3 — Parsing documents
  Parsing 753 segments with 8 concurrent workers…
  Progress: 50/753 segments parsed
  Progress: 100/753 segments parsed
  ...
  Completed parsing 753 segments
  Stage 3 completed in 612.3s (~10 minutes)

Stage 4 — Needle detection
  Running EASY detectors…
  Running MEDIUM detectors…
  Running EVIL detectors…
  Total raw findings: 247
  After deduplication: 198
  Stage 4 completed in 4.2s

Stage 5 — Writing output
  Written 198 findings → findings.json
  Stage 5 completed in 0.3s

=== Pipeline completed successfully ===
Total execution time: 640.4s (10.7 minutes)
Final output: 198 findings in findings.json
```

**Subsequent Runs (Warm Cache):**
```
Stage 3 — Parsing documents
  [cache hit] All segments cached
  Stage 3 completed in 28.1s

Total execution time: 45.2s
```

## Understanding the Output

### Step 6: Review findings.json

The pipeline generates `findings.json` with this structure:

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
    },
    {
      "finding_id": "F-002",
      "category": "vendor_name_typo",
      "pages": [52],
      "document_refs": ["INV-2025-0045"],
      "description": "Vendor 'Acme Suplies' looks like a misspelling of 'acme supplies' (similarity=0.92)",
      "reported_value": "Acme Suplies",
      "correct_value": "Acme Supplies"
    }
  ]
}
```

### Error Categories

**EASY (5 types, ~40 points):**
- `arithmetic_error` - Calculation mistakes
- `billing_typo` - Time notation errors (0.15 vs 0:15)
- `duplicate_line_item` - Repeated lines
- `invalid_date` - Impossible dates
- `wrong_tax_rate` - Incorrect GST rates

**MEDIUM (7 types, ~180 points):**
- `po_invoice_mismatch` - PO vs invoice discrepancies
- `vendor_name_typo` - Misspelled vendor names
- `double_payment` - Duplicate payments
- `ifsc_mismatch` - Bank code errors
- `duplicate_expense` - Repeated expense claims
- `date_cascade` - Date ordering issues
- `gstin_state_mismatch` - Tax ID state mismatches

**EVIL (8 types, ~700 points):**
- `quantity_accumulation` - Cumulative quantity overruns
- `price_escalation` - Systematic overcharging
- `balance_drift` - Bank balance inconsistencies
- `circular_reference` - Credit/debit note loops
- `triple_expense_claim` - Multiple expense claims
- `employee_id_collision` - ID conflicts
- `fake_vendor` - Unregistered vendors
- `phantom_po_reference` - Non-existent PO references

## Troubleshooting

### API Connection Errors

```
❌ Parse failed: Connection refused (status: None)
```

**Solution:** Check your `HYPERAPI_URL` is correct and accessible.

```bash
curl -X POST $HYPERAPI_URL/api/v1/parse \
  -H "X-API-Key: $HYPERAPI_KEY" \
  -F "file=@test.png"
```

### Authentication Errors

```
❌ Parse failed: Invalid API key (status: 401)
```

**Solution:** Verify your `HYPERAPI_KEY` is correct.

### Cache Issues

If you want to force a fresh run:

```bash
rm -rf .cache/
python -m logic.pipeline
```

### PDF Not Found

```
ERROR: PDF file not found: gauntlet.pdf
```

**Solution:** Ensure `gauntlet.pdf` is in the current directory or set `GAUNTLET_PDF` to the correct path.

## Performance Tips

1. **First run takes ~10 minutes** - This is normal as it OCRs 1,000 pages
2. **Subsequent runs take <1 minute** - Cache is used
3. **Clear cache to re-process** - `rm -rf .cache/`
4. **Adjust workers** - Edit `MAX_WORKERS=8` in `parser.py` for your CPU
5. **Monitor logs** - Check `pipeline.log` for detailed progress

## Next Steps

- Review `findings.json` for detected errors
- Tune detector thresholds in `logic/detectors.py`
- Add custom HSN/SAC codes to `HSN_TAX_RATE` dict
- Adjust fuzzy matching thresholds for vendor names
- Modify detection logic for your specific use case

## Support

For issues:
1. Check `pipeline.log` for detailed error messages
2. Run `python test_api.py` to isolate API issues
3. Verify environment variables are set correctly
4. Ensure `gauntlet.pdf` is the correct 1,000-page file
