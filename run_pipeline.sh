#!/bin/bash
# Run the Financial Gauntlet Pipeline with Real HyperAPI

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                                                                  ║"
echo "║         Financial Gauntlet Pipeline - Production Run            ║"
echo "║                                                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Set environment variables
export HYPERAPI_KEY="hk_live_386637e57a69ca0335c57a9fccd103b9"
export HYPERAPI_URL="http://hyperapi-production-12097051.us-east-1.elb.amazonaws.com"
export TEAM_ID="hyperbot_team"

echo "Environment:"
echo "  HYPERAPI_URL: $HYPERAPI_URL"
echo "  HYPERAPI_KEY: ${HYPERAPI_KEY:0:15}..."
echo "  TEAM_ID: $TEAM_ID"
echo ""

# Clear cache for fresh run (optional)
if [ "$1" == "--clear-cache" ]; then
    echo "Clearing cache..."
    rm -rf .cache/
    echo ""
fi

# Run the pipeline
echo "Starting pipeline..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 -m logic.pipeline

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if findings.json was created
if [ -f "findings.json" ]; then
    echo "✅ Pipeline completed successfully!"
    echo ""
    echo "Output file: findings.json"
    
    # Count findings
    FINDINGS_COUNT=$(python3 -c "import json; data=json.load(open('findings.json')); print(len(data['findings']))")
    echo "Total findings: $FINDINGS_COUNT"
    echo ""
    
    # Show findings by category
    echo "Findings by category:"
    python3 << 'EOF'
import json
from collections import Counter
with open('findings.json') as f:
    data = json.load(f)
cats = [f['category'] for f in data['findings']]
for cat, count in Counter(cats).most_common():
    print(f'  {cat}: {count}')
EOF
    echo ""
    echo "To view the full output:"
    echo "  cat findings.json | python3 -m json.tool"
else
    echo "❌ Pipeline failed - findings.json not created"
    echo "Check pipeline.log for errors"
fi
