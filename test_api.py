"""
Quick test script to verify HyperAPI connection
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, 'hyperapi-sdk')

from hyperapi import HyperAPIClient
import fitz

# Set environment variables
os.environ['HYPERAPI_KEY'] = 'hk_live_9343899f616b122756268dee94e6ead8'
os.environ['HYPERAPI_URL'] = 'https://apis.hyperbots.com'

def test_api():
    print("=== Testing HyperAPI Connection ===")
    
    # Initialize client
    client = HyperAPIClient()
    print(f"✓ Client initialized")
    print(f"  Base URL: {client.base_url}")
    print(f"  API Key: {client.api_key[:20]}...")
    
    # Check if gauntlet.pdf exists
    pdf_path = Path("gauntlet.pdf")
    if not pdf_path.exists():
        print(f"✗ PDF not found: {pdf_path}")
        return
    
    print(f"✓ PDF found: {pdf_path}")
    
    # Render page 3 (vendor master page)
    print("\nRendering page 3...")
    pdf_doc = fitz.open(str(pdf_path))
    page = pdf_doc[2]  # 0-indexed
    mat = fitz.Matrix(200 / 72, 200 / 72)
    pix = page.get_pixmap(matrix=mat)
    
    test_img = Path("/tmp/test_page_3.png")
    pix.save(str(test_img))
    print(f"✓ Rendered to {test_img}")
    
    # Test parse endpoint
    print("\nTesting /api/v1/parse endpoint...")
    try:
        result = client.parse(str(test_img))
        print(f"✓ Parse successful!")
        print(f"  OCR text length: {len(result.get('ocr', ''))} chars")
        print(f"  First 200 chars: {result.get('ocr', '')[:200]}...")
    except Exception as e:
        print(f"✗ Parse failed: {e}")
        return
    
    # Test extract endpoint
    print("\nTesting /api/v1/extract endpoint...")
    try:
        extract_result = client.extract(result.get('ocr', ''))
        print(f"✓ Extract successful!")
        print(f"  Data keys: {list(extract_result.get('data', {}).keys())}")
        if 'line_items' in extract_result.get('data', {}):
            print(f"  Line items: {len(extract_result['data']['line_items'])} items")
    except Exception as e:
        print(f"✗ Extract failed: {e}")
        return
    
    print("\n=== All tests passed! ===")
    client.close()

if __name__ == "__main__":
    test_api()
