# Quick Reference Card

## 🚀 Quick Start

```bash
# 1. Validate setup
./validate_setup.sh

# 2. Test API (if available)
python test_api.py

# 3. Run pipeline
python -m logic.pipeline

# 4. Check results
cat findings.json | python3 -m json.tool
```

## 📋 Environment Variables

```bash
export HYPERAPI_KEY="your-api-key"
export HYPERAPI_URL="https://your-api-endpoint"
export TEAM_ID="your_team_name"

# Optional
export GAUNTLET_PDF="gauntlet.pdf"
export CACHE_DIR=".cache"
export OUTPUT_FILE="findings.json"
```

## 🔧 Common Commands

### Run Pipeline
```bash
python -m logic.pipeline
# or
python logic/pipeline.py
```

### Clear Cache
```bash
rm -rf .cache/
```

### View Logs
```bash
tail -f pipeline.log
# or
cat pipeline.log | grep ERROR
```

### Check Findings
```bash
# Count findings
cat findings.json | python3 -c "import json,sys; print(len(json.load(sys.stdin)['findings']))"

# View first finding
cat findings.json | python3 -c "import json,sys; data=json.load(sys.stdin); print(json.dumps(data['findings'][0], indent=2)) if data['findings'] else print('No findings')"

# Group by category
cat findings.json | python3 -c "
import json, sys
from collections import Counter
data = json.load(sys.stdin)
cats = [f['category'] for f in data['findings']]
for cat, count in Counter(cats).most_common():
    print(f'{cat}: {count}')
"
```

## 📊 Pipeline Stages

| Stage | Time (Cold) | Time (Warm) | Description |
|-------|-------------|-------------|-------------|
| 1 | ~15s | ~15s | Vendor Master extraction |
| 2 | ~8s | ~8s | Document splitting |
| 3 | ~10min | ~30s | OCR + extraction (cached) |
| 4 | ~5s | ~5s | Error detection |
| 5 | <1s | <1s | Output formatting |

## 🐛 Troubleshooting

### API Connection Failed
```bash
# Check environment
echo $HYPERAPI_URL
echo $HYPERAPI_KEY

# Test connectivity
curl -I $HYPERAPI_URL

# Run with mock API
unset HYPERAPI_URL
python -m logic.pipeline
```

### Import Errors
```bash
# Reinstall dependencies
pip3 install -r requirements.txt
pip3 install hyperapi-sdk/

# Verify imports
python3 -c "import pymupdf, httpx, hyperapi"
```

### Permission Errors
```bash
# Check permissions
ls -ld . .cache

# Fix if needed
chmod 755 .
chmod 755 .cache
```

### Out of Memory
```bash
# Reduce workers in logic/parser.py
# Change: MAX_WORKERS = 8
# To:     MAX_WORKERS = 4
```

## 📁 File Structure

```
.
├── logic/              # Pipeline implementation
│   ├── pipeline.py     # Main entry point
│   ├── vendor_master.py
│   ├── splitter.py
│   ├── parser.py
│   ├── detectors.py
│   └── output.py
├── hyperapi-sdk/       # HyperAPI SDK
├── test_api.py         # API testing
├── validate_setup.sh   # Setup validation
├── gauntlet.pdf        # Input (1,000 pages)
├── findings.json       # Output
├── pipeline.log        # Logs
└── .cache/             # Cache directory
```

## 🎯 Error Categories

### EASY (5 types, ~40 pts)
- arithmetic_error
- billing_typo
- duplicate_line_item
- invalid_date
- wrong_tax_rate

### MEDIUM (7 types, ~180 pts)
- po_invoice_mismatch
- vendor_name_typo
- double_payment
- ifsc_mismatch
- duplicate_expense
- date_cascade
- gstin_state_mismatch

### EVIL (8 types, ~700 pts)
- quantity_accumulation
- price_escalation
- balance_drift
- circular_reference
- triple_expense_claim
- employee_id_collision
- fake_vendor
- phantom_po_reference

## 🔍 Useful Checks

### Check PDF
```bash
python3 -c "import fitz; doc=fitz.open('gauntlet.pdf'); print(f'Pages: {len(doc)}')"
```

### Check Cache
```bash
find .cache -name "ocr_*.json" | wc -l
find .cache -name "extract_*.json" | wc -l
du -sh .cache
```

### Check Python Version
```bash
python3 --version
```

### Check Installed Packages
```bash
pip3 list | grep -E "pymupdf|httpx|hyperapi"
```

## 📖 Documentation

- **README.md** - Main documentation
- **QUICKSTART.md** - Step-by-step guide
- **ARCHITECTURE.md** - System design
- **IMPLEMENTATION_SUMMARY.md** - Complete summary
- **RUN_SUMMARY.md** - Latest run details
- **CHECKLIST.md** - Pre-flight checklist
- **CHANGES.md** - API corrections

## 💡 Tips

1. **First run takes ~10 minutes** - Be patient, it's caching everything
2. **Subsequent runs take <1 minute** - Cache makes it fast
3. **Clear cache to re-process** - `rm -rf .cache/`
4. **Monitor with logs** - `tail -f pipeline.log`
5. **Tune detectors** - Edit `logic/detectors.py`
6. **Adjust workers** - Edit `MAX_WORKERS` in `logic/parser.py`

## 🆘 Getting Help

1. Check `pipeline.log` for errors
2. Run `./validate_setup.sh`
3. Run `python test_api.py`
4. Review documentation files
5. Check environment variables

## ✅ Success Indicators

- ✅ `findings.json` exists
- ✅ No ERROR in `pipeline.log`
- ✅ "Pipeline completed successfully" in logs
- ✅ Cache directory has files
- ✅ Findings count is reasonable (150-250)

---

**Quick Help:**
```bash
# Full validation
./validate_setup.sh && python test_api.py && python -m logic.pipeline

# Check everything
ls -lh findings.json pipeline.log && find .cache -type f | wc -l
```
