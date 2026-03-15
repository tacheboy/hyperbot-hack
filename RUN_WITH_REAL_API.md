# Running with Real HyperAPI

This guide shows you how to run the pipeline with the actual HyperAPI (no mock data).

## ✅ Prerequisites

1. **API Credentials:**
   - API Key: `hk_live_5b28c9ca40ef10c54d99af9edf6347fa`
   - API URL: `https://api.hyperapi.dev`

2. **Dependencies Installed:**
   ```bash
   pip3 install -r requirements.txt
   pip3 install hyperapi-sdk/
   ```

3. **Files Present:**
   - `gauntlet.pdf` (1,000-page document)
   - All `logic/` modules
   - HyperAPI SDK

## 🚀 Quick Start (One Command)

### Option 1: Using the Run Script
```bash
./run_pipeline.sh
```

### Option 2: Direct Python Command
```bash
export HYPERAPI_KEY="hk_live_5b28c9ca40ef10c54d99af9edf6347fa" && \
export HYPERAPI_URL="https://api.hyperapi.dev" && \
export TEAM_ID="hyperbot_team" && \
python3 -m logic.pipeline
```

## 📋 Step-by-Step Instructions

### Step 1: Set Environment Variables
```bash
export HYPERAPI_KEY="hk_live_5b28c9ca40ef10c54d99af9edf6347fa"
export HYPERAPI_URL="https://api.hyperapi.dev"
export TEAM_ID="hyperbot_team"
```

### Step 2: (Optional) Test API Connection
```bash
python3 test_api.py
```

This will test all 4 endpoints:
- `/v1/parse` - OCR extraction
- `/v1/extract` - Structured data extraction
- `/v1/classify` - Document classification
- `/v1/split` - Document splitting

### Step 3: Run the Pipeline
```bash
python3 -m logic.pipeline
```

### Step 4: Check the Output
```bash
# View findings count
cat findings.json | python3 -c "import json,sys; print(f'Total: {len(json.load(sys.stdin)[\"findings\"])}')"

# View full output
cat findings.json | python3 -m json.tool

# View by category
python3 << 'EOF'
import json
from collections import Counter
with open('findings.json') as f:
    data = json.load(f)
cats = [f['category'] for f in data['findings']]
for cat, count in Counter(cats).most_common():
    print(f'{cat}: {count}')
EOF
```

## 📊 Expected Results

### With Real API

**Processing Time:**
- First run (cold cache): ~10-12 minutes
- Subsequent runs (warm cache): ~30-60 seconds

**Output:**
- Vendors extracted: ~35
- Documents found: ~750
- Findings detected: 150-250 across all categories

**Findings by Category:**
```
EASY (5 types, ~40 points):
  arithmetic_error: 8-12
  billing_typo: 5-8
  duplicate_line_item: 6-10
  invalid_date: 4-6
  wrong_tax_rate: 10-15

MEDIUM (7 types, ~180 points):
  po_invoice_mismatch: 15-25
  vendor_name_typo: 10-15
  double_payment: 5-10
  ifsc_mismatch: 8-12
  duplicate_expense: 6-10
  date_cascade: 10-15
  gstin_state_mismatch: 12-18

EVIL (8 types, ~700 points):
  quantity_accumulation: 20-30
  price_escalation: 15-25
  balance_drift: 10-15
  circular_reference: 5-10
  triple_expense_claim: 8-12
  employee_id_collision: 6-10
  fake_vendor: 15-25
  phantom_po_reference: 20-30
```

## 🔧 Advanced Options

### Clear Cache Before Running
```bash
rm -rf .cache/
python3 -m logic.pipeline
```

Or use the script:
```bash
./run_pipeline.sh --clear-cache
```

### Monitor Progress
```bash
# In another terminal
tail -f pipeline.log
```

### Adjust Worker Count
Edit `logic/parser.py`:
```python
_API_SEMAPHORE = threading.Semaphore(8)  # Change 8 to your desired count
```

## 📁 Output Files

After running, you'll have:

1. **findings.json** - Main output file
   ```json
   {
     "team_id": "hyperbot_team",
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

2. **pipeline.log** - Execution log with detailed progress

3. **.cache/** - Cached OCR and extraction results
   - `ocr_NNNN.json` - Per-page OCR cache
   - `extract_*.json` - Per-document extraction cache

## 🐛 Troubleshooting

### API Connection Errors

**Error:** `Request failed: [Errno 8] nodename nor servname provided`

**Solution:** Check your internet connection and API URL
```bash
# Test connectivity
curl -I https://api.hyperapi.dev

# Verify environment variables
echo $HYPERAPI_URL
echo $HYPERAPI_KEY
```

### Authentication Errors

**Error:** `Invalid API key (status: 401)`

**Solution:** Verify your API key
```bash
# Check the key
echo $HYPERAPI_KEY

# Should start with: hk_live_
```

### Rate Limit Errors

**Error:** `Too Many Requests (status: 429)`

**Solution:** The pipeline has built-in rate limiting with 8 concurrent workers. If you still hit limits:
1. Reduce workers in `logic/parser.py`
2. Add delays between requests
3. Contact HyperAPI support for higher limits

### Timeout Errors

**Error:** `Request timed out (status: 504)`

**Solution:** Increase timeout in `logic/pipeline.py`:
```python
client = HyperAPIClient(
    api_key=os.environ["HYPERAPI_KEY"],
    base_url=os.environ["HYPERAPI_URL"],
    timeout=300.0,  # Increase from 180 to 300 seconds
)
```

## 📊 Performance Tips

1. **Use Cache:** Don't delete `.cache/` between runs unless necessary
2. **Parallel Processing:** Default 8 workers is optimal for most systems
3. **Monitor API Usage:** Check your HyperAPI dashboard for usage stats
4. **Batch Processing:** Process documents in batches if you have many PDFs

## 🔍 Validation

### Verify Output Format
```bash
# Check JSON is valid
python3 -c "import json; json.load(open('findings.json'))"

# Check required fields
python3 << 'EOF'
import json
with open('findings.json') as f:
    data = json.load(f)
    
required_fields = ['finding_id', 'category', 'pages', 'document_refs', 
                   'description', 'reported_value', 'correct_value']

for i, finding in enumerate(data['findings'][:5]):
    missing = [f for f in required_fields if f not in finding]
    if missing:
        print(f"Finding {i}: Missing fields: {missing}")
    else:
        print(f"Finding {i}: ✓ All fields present")
EOF
```

### Check Logs for Errors
```bash
# Look for errors
grep ERROR pipeline.log

# Check completion
grep "Pipeline completed successfully" pipeline.log
```

## 📞 Support

If you encounter issues:

1. Check `pipeline.log` for detailed error messages
2. Run `./validate_setup.sh` to verify setup
3. Run `python3 test_api.py` to test API connectivity
4. Review the troubleshooting section above

## 🎯 Success Criteria

✅ Pipeline completes without errors  
✅ `findings.json` is created  
✅ Findings count is reasonable (150-250)  
✅ All required fields present in findings  
✅ No ERROR messages in `pipeline.log`  

---

**Ready to run?**
```bash
./run_pipeline.sh
```

Good luck! 🚀
