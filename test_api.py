#!/usr/bin/env python3
"""
Test script for HyperAPI endpoints
"""

import os
import sys
from pathlib import Path

# Add hyperapi-sdk to path
sys.path.insert(0, str(Path(__file__).parent / "hyperapi-sdk"))

from hyperapi import HyperAPIClient
from hyperapi.exceptions import HyperAPIError


def test_parse():
    """Test the /api/v1/parse endpoint"""
    print("\n" + "="*60)
    print("Testing /api/v1/parse endpoint")
    print("="*60)
    
    client = HyperAPIClient()
    
    # Test with a sample page from gauntlet.pdf
    # First, we need to extract a page as PNG
    import fitz
    
    pdf_path = Path("gauntlet.pdf")
    if not pdf_path.exists():
        print("❌ gauntlet.pdf not found")
        return False
    
    # Render page 5 (first document page)
    doc = fitz.open(str(pdf_path))
    page = doc[4]  # 0-indexed, so page 5
    mat = fitz.Matrix(200/72, 200/72)
    pix = page.get_pixmap(matrix=mat)
    test_img = Path("/tmp/test_page_5.png")
    pix.save(str(test_img))
    doc.close()
    
    print(f"✓ Rendered test page to {test_img}")
    
    try:
        result = client.parse(str(test_img))
        print(f"✓ Parse successful")
        print(f"  OCR text length: {len(result.get('ocr', ''))} characters")
        print(f"  First 200 chars: {result.get('ocr', '')[:200]}...")
        return True
    except HyperAPIError as e:
        print(f"❌ Parse failed: {e.message} (status: {e.status_code})")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_extract():
    """Test the /api/v1/extract endpoint"""
    print("\n" + "="*60)
    print("Testing /api/v1/extract endpoint")
    print("="*60)
    
    client = HyperAPIClient()
    
    # Sample OCR text from an invoice
    sample_ocr = """
    TAX INVOICE
    
    Invoice No: INV-2025-0001
    Date: 15/01/2025
    
    Vendor: Acme Supplies Pvt Ltd
    GSTIN: 29AABCA1234F1Z5
    
    Bill To:
    ABC Corporation
    
    Description          Qty    Rate    Amount
    Office Supplies      10     100.00  1000.00
    Stationery Items     5      50.00   250.00
    
    Subtotal:                           1250.00
    CGST @ 9%:                          112.50
    SGST @ 9%:                          112.50
    Total:                              1475.00
    """
    
    try:
        result = client.extract(sample_ocr)
        print(f"✓ Extract successful")
        print(f"  Extracted data keys: {list(result.get('data', {}).keys())}")
        
        data = result.get('data', {})
        if 'invoice_number' in data:
            print(f"  Invoice Number: {data['invoice_number']}")
        if 'vendor_name' in data:
            print(f"  Vendor Name: {data['vendor_name']}")
        if 'total' in data:
            print(f"  Total: {data['total']}")
        if 'line_items' in data:
            print(f"  Line Items: {len(data['line_items'])} items")
        
        validation_errors = result.get('validation_errors', [])
        if validation_errors:
            print(f"  Validation Errors: {len(validation_errors)}")
            for err in validation_errors[:3]:
                print(f"    - {err}")
        
        return True
    except HyperAPIError as e:
        print(f"❌ Extract failed: {e.message} (status: {e.status_code})")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_classify():
    """Test the /api/v1/classify endpoint"""
    print("\n" + "="*60)
    print("Testing /api/v1/classify endpoint")
    print("="*60)
    
    client = HyperAPIClient()
    
    test_img = Path("/tmp/test_page_5.png")
    if not test_img.exists():
        print("❌ Test image not found (run test_parse first)")
        return False
    
    try:
        result = client.classify(str(test_img))
        print(f"✓ Classify successful")
        print(f"  Document Type: {result.get('document_type')}")
        print(f"  Confidence: {result.get('confidence', 0):.2%}")
        return True
    except HyperAPIError as e:
        print(f"❌ Classify failed: {e.message} (status: {e.status_code})")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_split():
    """Test the /api/v1/split endpoint"""
    print("\n" + "="*60)
    print("Testing /api/v1/split endpoint")
    print("="*60)
    
    client = HyperAPIClient()
    
    # Create a small test PDF with 3 pages
    import fitz
    
    pdf_path = Path("gauntlet.pdf")
    if not pdf_path.exists():
        print("❌ gauntlet.pdf not found")
        return False
    
    # Extract first 3 pages to a test PDF
    doc = fitz.open(str(pdf_path))
    test_pdf = fitz.open()
    for i in range(min(3, len(doc))):
        test_pdf.insert_pdf(doc, from_page=i, to_page=i)
    
    test_pdf_path = Path("/tmp/test_3pages.pdf")
    test_pdf.save(str(test_pdf_path))
    test_pdf.close()
    doc.close()
    
    print(f"✓ Created test PDF with 3 pages: {test_pdf_path}")
    
    try:
        result = client.split(str(test_pdf_path))
        print(f"✓ Split successful")
        print(f"  Pages: {len(result.get('pages', []))}")
        print(f"  Sections: {len(result.get('sections', []))}")
        return True
    except HyperAPIError as e:
        print(f"❌ Split failed: {e.message} (status: {e.status_code})")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("HyperAPI Endpoint Tests")
    print("="*60)
    
    # Check environment variables
    if not os.environ.get("HYPERAPI_KEY"):
        print("❌ HYPERAPI_KEY environment variable not set")
        print("   Please set it with: export HYPERAPI_KEY='your-key'")
        return 1
    
    if not os.environ.get("HYPERAPI_URL"):
        print("❌ HYPERAPI_URL environment variable not set")
        print("   Please set it with: export HYPERAPI_URL='https://your-api-url'")
        return 1
    
    print(f"✓ HYPERAPI_KEY: {os.environ['HYPERAPI_KEY'][:10]}...")
    print(f"✓ HYPERAPI_URL: {os.environ['HYPERAPI_URL']}")
    
    # Run tests
    results = {
        "parse": test_parse(),
        "extract": test_extract(),
        "classify": test_classify(),
        "split": test_split(),
    }
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
