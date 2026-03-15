#!/bin/bash
# Check pipeline progress

echo "=== Pipeline Progress ==="
echo ""

if [ -f "pipeline_run.log" ]; then
    echo "Latest log entries:"
    tail -10 pipeline_run.log
    echo ""
fi

if [ -d ".cache" ]; then
    OCR_COUNT=$(ls -1 .cache/ocr_*.json 2>/dev/null | wc -l)
    EXTRACT_COUNT=$(ls -1 .cache/extract_*.json 2>/dev/null | wc -l)
    echo "Cached OCR results: $OCR_COUNT"
    echo "Cached extractions: $EXTRACT_COUNT"
    echo ""
fi

if [ -f "findings.json" ]; then
    FINDINGS=$(python3 -c "import json; print(len(json.load(open('findings.json'))['findings']))" 2>/dev/null || echo "0")
    echo "✅ findings.json created with $FINDINGS findings"
else
    echo "⏳ findings.json not yet created (pipeline still running)"
fi
