# Pre-Flight Checklist

Use this checklist before running the Financial Gauntlet pipeline.

## ✅ Environment Setup

### Python Environment
- [ ] Python 3.8 or higher installed
  ```bash
  python3 --version
  ```
- [ ] pip is up to date
  ```bash
  pip install --upgrade pip
  ```

### Dependencies
- [ ] Core dependencies installed
  ```bash
  pip install -r requirements.txt
  ```
- [ ] HyperAPI SDK installed
  ```bash
  pip install -e hyperapi-sdk/
  ```
- [ ] Verify imports work
  ```bash
  python3 -c "import pymupdf, httpx, hyperapi"
  ```

## ✅ Configuration

### Environment Variables
- [ ] `HYPERAPI_KEY` is set
  ```bash
  echo $HYPERAPI_KEY
  ```
- [ ] `HYPERAPI_URL` is set
  ```bash
  echo $HYPERAPI_URL
  ```
- [ ] `TEAM_ID` is set
  ```bash
  echo $TEAM_ID
  ```

### Optional Variables
- [ ] `GAUNTLET_PDF` (default: gauntlet.pdf)
- [ ] `CACHE_DIR` (default: .cache)
- [ ] `OUTPUT_FILE` (default: findings.json)

## ✅ Files & Directories

### Required Files
- [ ] `gauntlet.pdf` exists
  ```bash
  ls -lh gauntlet.pdf
  ```
- [ ] PDF has 1,000 pages
  ```bash
  python3 -c "import fitz; print(len(fitz.open('gauntlet.pdf')))"
  ```

### Project Structure
- [ ] `logic/` directory exists with all modules
- [ ] `hyperapi-sdk/` directory exists
- [ ] `test_api.py` exists and is executable
- [ ] `validate_setup.sh` exists and is executable

## ✅ API Connectivity

### Test API Endpoints
- [ ] Run validation script
  ```bash
  ./validate_setup.sh
  ```
- [ ] Run API tests
  ```bash
  python test_api.py
  ```
- [ ] All 4 endpoints pass:
  - [ ] `/api/v1/parse` ✓
  - [ ] `/api/v1/extract` ✓
  - [ ] `/api/v1/classify` ✓
  - [ ] `/api/v1/split` ✓

### Manual API Test (Optional)
- [ ] Test parse endpoint manually
  ```bash
  curl -X POST $HYPERAPI_URL/api/v1/parse \
    -H "X-API-Key: $HYPERAPI_KEY" \
    -F "file=@test.png"
  ```

## ✅ Cache Management

### Cache Directory
- [ ] Cache directory exists or will be created
  ```bash
  mkdir -p .cache
  ```
- [ ] Check cache size (if exists)
  ```bash
  du -sh .cache 2>/dev/null || echo "No cache yet"
  ```
- [ ] Clear cache if needed (for fresh run)
  ```bash
  # rm -rf .cache/
  ```

## ✅ Disk Space

### Storage Requirements
- [ ] At least 500 MB free space for cache
  ```bash
  df -h .
  ```
- [ ] At least 100 MB free for temporary files
  ```bash
  df -h /tmp
  ```

## ✅ Performance Tuning (Optional)

### Adjust Workers
- [ ] Check CPU cores
  ```bash
  python3 -c "import os; print(f'CPU cores: {os.cpu_count()}')"
  ```
- [ ] Adjust `MAX_WORKERS` in `logic/parser.py` if needed
  - Default: 8 workers
  - Recommended: 1-2 workers per CPU core

### Network
- [ ] Stable internet connection
- [ ] Low latency to API endpoint
  ```bash
  ping -c 3 $(echo $HYPERAPI_URL | sed 's|https://||' | sed 's|/.*||')
  ```

## ✅ Pre-Run Verification

### Quick Tests
- [ ] Import all modules
  ```bash
  python3 -c "from logic import pipeline, vendor_master, splitter, parser, detectors, output"
  ```
- [ ] Check PDF can be opened
  ```bash
  python3 -c "import fitz; doc = fitz.open('gauntlet.pdf'); print(f'Pages: {len(doc)}')"
  ```
- [ ] Check write permissions
  ```bash
  touch findings.json && rm findings.json
  ```

## ✅ Run Pipeline

### Execute
- [ ] Run the pipeline
  ```bash
  python -m logic.pipeline
  ```
  Or:
  ```bash
  python logic/pipeline.py
  ```

### Monitor Progress
- [ ] Watch console output for stage progress
- [ ] Check `pipeline.log` for detailed logs
  ```bash
  tail -f pipeline.log
  ```

## ✅ Post-Run Verification

### Output Files
- [ ] `findings.json` exists
  ```bash
  ls -lh findings.json
  ```
- [ ] JSON is valid
  ```bash
  python3 -c "import json; json.load(open('findings.json'))"
  ```
- [ ] Has findings
  ```bash
  python3 -c "import json; data = json.load(open('findings.json')); print(f\"Findings: {len(data['findings'])}\")"
  ```

### Validate Output Format
- [ ] Has `team_id` field
- [ ] Has `findings` array
- [ ] Each finding has required fields:
  - [ ] `finding_id`
  - [ ] `category`
  - [ ] `pages`
  - [ ] `document_refs`
  - [ ] `description`
  - [ ] `reported_value`
  - [ ] `correct_value`

### Check Logs
- [ ] No ERROR messages in `pipeline.log`
  ```bash
  grep ERROR pipeline.log
  ```
- [ ] All stages completed
  ```bash
  grep "Stage.*completed" pipeline.log
  ```
- [ ] Pipeline completed successfully
  ```bash
  grep "Pipeline completed successfully" pipeline.log
  ```

## ✅ Results Analysis

### Findings Breakdown
- [ ] Count findings by category
  ```bash
  python3 -c "
  import json
  from collections import Counter
  data = json.load(open('findings.json'))
  categories = [f['category'] for f in data['findings']]
  for cat, count in Counter(categories).most_common():
      print(f'{cat}: {count}')
  "
  ```

### Expected Results
- [ ] Total findings: ~150-250 (varies by detection thresholds)
- [ ] EASY findings: ~30-50
- [ ] MEDIUM findings: ~50-80
- [ ] EVIL findings: ~70-120

### Quality Checks
- [ ] No duplicate finding IDs
- [ ] All categories are valid
- [ ] All page numbers are in range 1-1000
- [ ] All document_refs are non-empty

## ✅ Performance Metrics

### Timing
- [ ] Stage 1: ~15 seconds
- [ ] Stage 2: ~8 seconds
- [ ] Stage 3: ~10 minutes (cold) or ~30 seconds (warm)
- [ ] Stage 4: ~5 seconds
- [ ] Stage 5: <1 second
- [ ] Total: ~10-12 minutes (cold) or ~1 minute (warm)

### Cache Efficiency
- [ ] Check cache hit rate
  ```bash
  find .cache -name "ocr_*.json" | wc -l
  find .cache -name "extract_*.json" | wc -l
  ```
- [ ] Expected: ~1,000 OCR files + ~750 extract files

## ✅ Troubleshooting

### If Pipeline Fails

#### API Errors
- [ ] Check API credentials
- [ ] Test API connectivity
- [ ] Check API rate limits
- [ ] Review error messages in logs

#### Memory Errors
- [ ] Reduce `MAX_WORKERS` in `parser.py`
- [ ] Close other applications
- [ ] Check available RAM

#### Disk Space Errors
- [ ] Clear cache: `rm -rf .cache/`
- [ ] Free up disk space
- [ ] Check `/tmp` directory

#### Import Errors
- [ ] Reinstall dependencies
- [ ] Check Python version
- [ ] Verify virtual environment

### Common Issues

#### "Invalid API key"
```bash
# Verify environment variable
echo $HYPERAPI_KEY
# Should show your API key
```

#### "Connection refused"
```bash
# Check API URL
echo $HYPERAPI_URL
# Test connectivity
curl -I $HYPERAPI_URL
```

#### "PDF not found"
```bash
# Check file exists
ls -l gauntlet.pdf
# Check environment variable
echo $GAUNTLET_PDF
```

#### "Permission denied"
```bash
# Check write permissions
ls -ld . .cache
# Fix permissions if needed
chmod 755 .
```

## ✅ Final Checklist

Before submitting results:

- [ ] Pipeline completed successfully
- [ ] `findings.json` is valid JSON
- [ ] All findings have required fields
- [ ] No ERROR messages in logs
- [ ] Findings count is reasonable (~150-250)
- [ ] Team ID is correct in output
- [ ] Ready to submit!

## Quick Reference Commands

```bash
# 1. Validate setup
./validate_setup.sh

# 2. Test API
python test_api.py

# 3. Run pipeline
python -m logic.pipeline

# 4. Check output
cat findings.json | jq '.findings | length'

# 5. View findings by category
cat findings.json | jq '.findings | group_by(.category) | map({category: .[0].category, count: length})'

# 6. Check logs
tail -50 pipeline.log

# 7. Clear cache (if needed)
rm -rf .cache/

# 8. Re-run pipeline
python -m logic.pipeline
```

## Success Criteria

✅ All checks passed
✅ Pipeline runs without errors
✅ Output file generated
✅ Findings are valid
✅ Ready for production use

---

**Note:** This checklist should be completed before each pipeline run to ensure optimal results.
