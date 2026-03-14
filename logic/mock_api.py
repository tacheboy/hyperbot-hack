"""
Mock HyperAPI implementation for testing without API access
"""
import json
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
        """
        image_path = Path(image_path)
        
        # For PNG images, we can't extract text directly
        # Return a placeholder
        return {
            "type": "layout",
            "ocr": f"[Mock OCR text from {image_path.name}]"
        }
    
    def extract(self, ocr_text: str) -> dict:
        """
        Mock extract - returns basic structure.
        """
        return {
            "type": "extract",
            "data": {
                "invoice_number": "MOCK-001",
                "date": "2025-01-01",
                "vendor_name": "Mock Vendor",
                "total_amount": "1000.00",
                "line_items": [
                    {
                        "description": "Mock Item",
                        "quantity": 1,
                        "unit_price": "1000.00",
                        "total": "1000.00"
                    }
                ]
            }
        }
    
    def process(self, image_path: Union[str, Path]) -> dict:
        """
        Mock process - combines parse and extract.
        """
        parse_result = self.parse(image_path)
        extract_result = self.extract(parse_result["ocr"])
        
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
