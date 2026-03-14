"""
Mock HyperAPI implementation for testing without API access
"""
import json
import re
from pathlib import Path
from typing import Union
import fitz


class MockHyperAPIClient:
    """
    Mock client that simulates HyperAPI responses for testing.
    Uses PyMuPDF for basic OCR simulation.
    """
    
    def __init__(self, api_key=None, base_url=None, timeout=120.0):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
    
    def parse(self, image_path: Union[str, Path]) -> dict:
        """
        Mock parse - extracts text from image using PyMuPDF.
        For PNG images rendered from PDF, we return placeholder text.
        """
        image_path = Path(image_path)
        
        # Extract page number from filename if possible
        page_match = re.search(r'page_(\d+)', str(image_path))
        if page_match:
            page_num = int(page_match.group(1))
            return {
                "ocr": f"[Mock OCR text from page {page_num}]\n\nSample document content for page {page_num}."
            }
        
        return {
            "ocr": f"[Mock OCR text from {image_path.name}]\n\nSample document content."
        }
    
    def extract(self, file_path: Union[str, Path]) -> dict:
        """
        Mock extract - returns basic structure based on file content.
        """
        file_path = Path(file_path)
        
        # Try to read some text if it's an image from a PDF page
        page_match = re.search(r'page_(\d+)', str(file_path))
        page_num = int(page_match.group(1)) if page_match else 0
        
        # Generate mock data based on page number
        data = {
            "invoice_number": f"MOCK-INV-{page_num:04d}",
            "date": "2025-01-15",
            "vendor_name": "Mock Vendor Ltd",
            "total_amount": "1000.00",
            "subtotal": 850.00,
            "tax_amount": 150.00,
            "line_items": [
                {
                    "description": "Mock Item 1",
                    "quantity": 10,
                    "rate": 85.00,
                    "amount": 850.00
                }
            ]
        }
        
        return {
            "data": data,
            "validation_errors": []
        }
    
    def classify(self, image_path: Union[str, Path]) -> dict:
        """
        Mock classify - returns document type based on filename or content.
        """
        image_path = Path(image_path)
        
        # Simple classification based on filename
        name_lower = image_path.name.lower()
        if "invoice" in name_lower:
            return {"document_type": "invoice", "confidence": 0.95}
        elif "po" in name_lower or "purchase" in name_lower:
            return {"document_type": "po", "confidence": 0.90}
        elif "bank" in name_lower or "statement" in name_lower:
            return {"document_type": "bank_statement", "confidence": 0.88}
        elif "expense" in name_lower:
            return {"document_type": "expense_report", "confidence": 0.92}
        else:
            return {"document_type": "unknown", "confidence": 0.50}
    
    def split(self, pdf_path: Union[str, Path]) -> dict:
        """
        Mock split - returns page information.
        """
        pdf_path = Path(pdf_path)
        
        try:
            doc = fitz.open(str(pdf_path))
            pages = []
            for i in range(len(doc)):
                pages.append({
                    "page_number": i + 1,
                    "has_text": True
                })
            doc.close()
            
            return {
                "pages": pages,
                "sections": []
            }
        except Exception:
            return {
                "pages": [],
                "sections": []
            }
    
    def process(self, file_path: Union[str, Path]) -> dict:
        """
        Mock process - combines parse and extract.
        """
        parse_result = self.parse(file_path)
        extract_result = self.extract(file_path)
        
        return {
            "ocr": parse_result["ocr"],
            "data": extract_result["data"]
        }
    
    def close(self):
        """Mock close."""
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
