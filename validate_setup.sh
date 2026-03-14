#!/bin/bash
# Validation script to check if everything is set up correctly

echo "=========================================="
echo "Financial Gauntlet - Setup Validation"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "1. Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
    echo -e "   ${GREEN}✓${NC} Python $PYTHON_VERSION (>= 3.8 required)"
else
    echo -e "   ${RED}✗${NC} Python $PYTHON_VERSION (>= 3.8 required)"
    exit 1
fi

# Check required files
echo ""
echo "2. Checking required files..."

FILES=("gauntlet.pdf" "requirements.txt" "test_api.py" "logic/pipeline.py")
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "   ${GREEN}✓${NC} $file"
    else
        echo -e "   ${RED}✗${NC} $file (missing)"
        exit 1
    fi
done

# Check environment variables
echo ""
echo "3. Checking environment variables..."

if [ -z "$HYPERAPI_KEY" ]; then
    echo -e "   ${RED}✗${NC} HYPERAPI_KEY not set"
    echo "      Set it with: export HYPERAPI_KEY='your-key'"
    exit 1
else
    echo -e "   ${GREEN}✓${NC} HYPERAPI_KEY (${HYPERAPI_KEY:0:10}...)"
fi

if [ -z "$HYPERAPI_URL" ]; then
    echo -e "   ${RED}✗${NC} HYPERAPI_URL not set"
    echo "      Set it with: export HYPERAPI_URL='https://your-api-url'"
    exit 1
else
    echo -e "   ${GREEN}✓${NC} HYPERAPI_URL ($HYPERAPI_URL)"
fi

if [ -z "$TEAM_ID" ]; then
    echo -e "   ${YELLOW}⚠${NC} TEAM_ID not set (optional but recommended)"
    echo "      Set it with: export TEAM_ID='your_team_name'"
else
    echo -e "   ${GREEN}✓${NC} TEAM_ID ($TEAM_ID)"
fi

# Check Python packages
echo ""
echo "4. Checking Python packages..."

PACKAGES=("pymupdf" "httpx")
for package in "${PACKAGES[@]}"; do
    if python3 -c "import $package" 2>/dev/null; then
        VERSION=$(python3 -c "import $package; print($package.__version__)" 2>/dev/null)
        echo -e "   ${GREEN}✓${NC} $package ($VERSION)"
    else
        echo -e "   ${RED}✗${NC} $package (not installed)"
        echo "      Install with: pip install -r requirements.txt"
        exit 1
    fi
done

# Check HyperAPI SDK
if python3 -c "import hyperapi" 2>/dev/null; then
    VERSION=$(python3 -c "import hyperapi; print(hyperapi.__version__)" 2>/dev/null)
    echo -e "   ${GREEN}✓${NC} hyperapi SDK ($VERSION)"
else
    echo -e "   ${RED}✗${NC} hyperapi SDK (not installed)"
    echo "      Install with: pip install -e hyperapi-sdk/"
    exit 1
fi

# Check PDF file size
echo ""
echo "5. Checking gauntlet.pdf..."
PDF_SIZE=$(du -h gauntlet.pdf | cut -f1)
PDF_PAGES=$(python3 -c "import fitz; print(len(fitz.open('gauntlet.pdf')))" 2>/dev/null)

if [ "$PDF_PAGES" -eq 1000 ]; then
    echo -e "   ${GREEN}✓${NC} gauntlet.pdf ($PDF_SIZE, $PDF_PAGES pages)"
else
    echo -e "   ${YELLOW}⚠${NC} gauntlet.pdf ($PDF_SIZE, $PDF_PAGES pages)"
    echo "      Expected 1,000 pages, found $PDF_PAGES"
fi

# Check cache directory
echo ""
echo "6. Checking cache directory..."
if [ -d ".cache" ]; then
    CACHE_SIZE=$(du -sh .cache 2>/dev/null | cut -f1)
    CACHE_FILES=$(find .cache -type f 2>/dev/null | wc -l)
    echo -e "   ${GREEN}✓${NC} .cache exists ($CACHE_SIZE, $CACHE_FILES files)"
    echo "      To clear cache: rm -rf .cache/"
else
    echo -e "   ${YELLOW}⚠${NC} .cache does not exist (will be created on first run)"
fi

# Summary
echo ""
echo "=========================================="
echo "Setup Validation Complete"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Test API connection:"
echo "     python test_api.py"
echo ""
echo "  2. Run the pipeline:"
echo "     python -m logic.pipeline"
echo ""
echo "  3. Check the output:"
echo "     cat findings.json | jq '.findings | length'"
echo ""
