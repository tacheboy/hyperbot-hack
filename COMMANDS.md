# Terminal Commands - Quick Reference

## 🚀 Run the Pipeline (Choose One)

### Method 1: Using the Run Script (Recommended)
```bash
./run_pipeline.sh
```

### Method 2: One-Line Command
```bash
export HYPERAPI_KEY="hk_live_5b28c9ca40ef10c54d99af9edf6347fa" && export HYPERAPI_URL="https://api.hyperapi.dev" && export TEAM_ID="hyperbot_team" && python3 -m logic.pipeline
```

### Method 3: Step-by-Step
```bash
# Set environment variables
export HYPERAPI_KEY="hk_live_5b28c9ca40ef10c54d99af9edf6347fa"
export HYPERAPI_URL="https://api.hyperapi.dev"
export TEAM_ID="hyperbot_team"

# Run pipeline
python3 -m logic.pipeline
```

## 🧪 Test API Connection (Optional)
```bash
python3 test_api.py
```

## 📊 View Results

### Count Findings
```bash
cat findings.json | python3 -c "import json,sys; print(f'Total findings: {len(json.load(sys.stdin)[\"findings\"])}')"
```

### View First Finding
```bash
cat findings.json | python3 -c "import json,sys; data=json.load(sys.stdin); print(json.dumps(data['findings'][0], indent=2)) if data['findings'] else print('No findings')"
```

### View All Findings (Pretty Print)
```bash
cat findings.json | python3 -m json.tool
```

### Count by Category
```bash
python3 << 'EOF'
import json
from collections import Counter
with open('findings.json') as f:
    data = json.load(f)
cats = [f['category'] for f in data['findings']]
print('\nFindings by category:')
for cat, count in Counter(cats).most_common():
    print(f'  {cat}: {count}')
EOF
```

## 📝 View Logs
```bash
# View last 50 lines
tail -50 pipeline.log

# View all logs
cat pipeline.log

# Search for errors
grep ERROR pipeline.log

# Follow logs in real-time
tail -f pipeline.log
```

## 🔄 Clear Cache and Re-run
```bash
# Clear cache
rm -rf .cache/

# Run pipeline
python3 -m logic.pipeline
```

Or use the script:
```bash
./run_pipeline.sh --clear-cache
```

## ✅ Validate Setup
```bash
./validate_setup.sh
```

## 📦 Installation Commands

### Install Dependencies
```bash
pip3 install -r requirements.txt
pip3 install hyperapi-sdk/
```

### Verify Installation
```bash
python3 -c "import pymupdf, httpx, hyperapi; print('✓ All packages installed')"
```

## 🔍 Check Files

### Check PDF
```bash
python3 -c "import fitz; doc=fitz.open('gauntlet.pdf'); print(f'Pages: {len(doc)}')"
```

### Check Cache
```bash
# Count cache files
find .cache -type f | wc -l

# Check cache size
du -sh .cache

# List cache files
ls -lh .cache/ | head -20
```

### Check Output
```bash
# Check if findings.json exists
ls -lh findings.json

# Validate JSON
python3 -c "import json; json.load(open('findings.json')); print('✓ Valid JSON')"
```

## 🛠️ Troubleshooting Commands

### Test API Connectivity
```bash
curl -I https://api.hyperapi.dev
```

### Check Environment Variables
```bash
echo "HYPERAPI_KEY: ${HYPERAPI_KEY:0:15}..."
echo "HYPERAPI_URL: $HYPERAPI_URL"
echo "TEAM_ID: $TEAM_ID"
```

### Test API with curl
```bash
# Test parse endpoint
curl -X POST https://api.hyperapi.dev/v1/parse \
  -H "X-API-Key: hk_live_5b28c9ca40ef10c54d99af9edf6347fa" \
  -F "file=@test.png"
```

### Check Python Version
```bash
python3 --version
```

### Check Installed Packages
```bash
pip3 list | grep -E "pymupdf|httpx|hyperapi"
```

## 📊 Analysis Commands

### Get Findings Summary
```bash
python3 << 'EOF'
import json
with open('findings.json') as f:
    data = json.load(f)
    
print(f"Team ID: {data['team_id']}")
print(f"Total Findings: {len(data['findings'])}")

if data['findings']:
    print(f"\nFirst Finding:")
    f = data['findings'][0]
    print(f"  ID: {f['finding_id']}")
    print(f"  Category: {f['category']}")
    print(f"  Pages: {f['pages']}")
    print(f"  Description: {f['description'][:100]}...")
EOF
```

### Export Findings to CSV
```bash
python3 << 'EOF'
import json
import csv

with open('findings.json') as f:
    data = json.load(f)

with open('findings.csv', 'w', newline='') as csvfile:
    fieldnames = ['finding_id', 'category', 'pages', 'document_refs', 
                  'description', 'reported_value', 'correct_value']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    
    writer.writeheader()
    for finding in data['findings']:
        row = finding.copy()
        row['pages'] = str(row['pages'])
        row['document_refs'] = str(row['document_refs'])
        writer.writerow(row)

print("✓ Exported to findings.csv")
EOF
```

### Get Statistics
```bash
python3 << 'EOF'
import json
from collections import Counter

with open('findings.json') as f:
    data = json.load(f)

findings = data['findings']
print(f"Total Findings: {len(findings)}")
print(f"\nBy Category:")

cats = Counter(f['category'] for f in findings)
for cat, count in cats.most_common():
    print(f"  {cat}: {count}")

print(f"\nBy Tier:")
easy = ['arithmetic_error', 'billing_typo', 'duplicate_line_item', 'invalid_date', 'wrong_tax_rate']
medium = ['po_invoice_mismatch', 'vendor_name_typo', 'double_payment', 'ifsc_mismatch', 'duplicate_expense', 'date_cascade', 'gstin_state_mismatch']
evil = ['quantity_accumulation', 'price_escalation', 'balance_drift', 'circular_reference', 'triple_expense_claim', 'employee_id_collision', 'fake_vendor', 'phantom_po_reference']

easy_count = sum(cats[c] for c in easy if c in cats)
medium_count = sum(cats[c] for c in medium if c in cats)
evil_count = sum(cats[c] for c in evil if c in cats)

print(f"  EASY: {easy_count}")
print(f"  MEDIUM: {medium_count}")
print(f"  EVIL: {evil_count}")
EOF
```

## 🎯 Quick Workflow

```bash
# 1. Validate setup
./validate_setup.sh

# 2. Test API (optional)
python3 test_api.py

# 3. Run pipeline
./run_pipeline.sh

# 4. View results
cat findings.json | python3 -m json.tool | less

# 5. Get summary
python3 << 'EOF'
import json
from collections import Counter
with open('findings.json') as f:
    data = json.load(f)
print(f"Total: {len(data['findings'])} findings")
cats = [f['category'] for f in data['findings']]
for cat, count in Counter(cats).most_common():
    print(f'  {cat}: {count}')
EOF
```

---

**Most Common Command:**
```bash
./run_pipeline.sh
```

That's it! 🚀
