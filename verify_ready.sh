#!/bin/bash
# Verify that the pipeline is ready to run

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                                                                  ║"
echo "║         Financial Gauntlet Pipeline - Readiness Check           ║"
echo "║                                                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

READY=true

# Check Python
echo "Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "  ✅ $PYTHON_VERSION"
else
    echo "  ❌ Python 3 not found"
    READY=false
fi

# Check dependencies
echo ""
echo "Checking Python dependencies..."
if python3 -c "import httpx" 2>/dev/null; then
    echo "  ✅ httpx installed"
else
    echo "  ❌ httpx not installed (run: pip3 install httpx)"
    READY=false
fi

if python3 -c "import fitz" 2>/dev/null; then
    echo "  ✅ PyMuPDF installed"
else
    echo "  ❌ PyMuPDF not installed (run: pip3 install pymupdf)"
    READY=false
fi

# Check HyperAPI SDK
echo ""
echo "Checking HyperAPI SDK..."
if python3 -c "from hyperapi import HyperAPIClient" 2>/dev/null; then
    echo "  ✅ HyperAPI SDK installed"
else
    echo "  ❌ HyperAPI SDK not installed (run: cd hyperapi-sdk && pip3 install -e .)"
    READY=false
fi

# Check gauntlet.pdf
echo ""
echo "Checking input file..."
if [ -f "gauntlet.pdf" ]; then
    SIZE=$(du -h gauntlet.pdf | cut -f1)
    echo "  ✅ gauntlet.pdf found ($SIZE)"
else
    echo "  ❌ gauntlet.pdf not found"
    READY=false
fi

# Check environment variables
echo ""
echo "Checking environment variables..."
if [ -n "$HYPERAPI_KEY" ]; then
    echo "  ✅ HYPERAPI_KEY set (${HYPERAPI_KEY:0:15}...)"
else
    echo "  ⚠️  HYPERAPI_KEY not set (will be set by run_pipeline.sh)"
fi

if [ -n "$HYPERAPI_URL" ]; then
    echo "  ✅ HYPERAPI_URL set ($HYPERAPI_URL)"
else
    echo "  ⚠️  HYPERAPI_URL not set (will be set by run_pipeline.sh)"
fi

# Check run script
echo ""
echo "Checking run script..."
if [ -f "run_pipeline.sh" ]; then
    if [ -x "run_pipeline.sh" ]; then
        echo "  ✅ run_pipeline.sh is executable"
    else
        echo "  ⚠️  run_pipeline.sh not executable (run: chmod +x run_pipeline.sh)"
    fi
else
    echo "  ❌ run_pipeline.sh not found"
    READY=false
fi

# Check logic modules
echo ""
echo "Checking pipeline modules..."
MODULES=("logic/__init__.py" "logic/pipeline.py" "logic/parser.py" "logic/vendor_master.py" "logic/detectors.py" "logic/splitter.py" "logic/output.py")
for module in "${MODULES[@]}"; do
    if [ -f "$module" ]; then
        echo "  ✅ $module"
    else
        echo "  ❌ $module not found"
        READY=false
    fi
done

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$READY" = true ]; then
    echo "✅ All checks passed! Pipeline is ready to run."
    echo ""
    echo "To run the pipeline:"
    echo "  ./run_pipeline.sh"
    echo ""
    echo "To test API connectivity first:"
    echo "  export HYPERAPI_KEY='hk_live_5b28c9ca40ef10c54d99af9edf6347fa'"
    echo "  export HYPERAPI_URL='https://api.hyperapi.dev'"
    echo "  python3 test_api.py"
    exit 0
else
    echo "❌ Some checks failed. Please fix the issues above."
    exit 1
fi
