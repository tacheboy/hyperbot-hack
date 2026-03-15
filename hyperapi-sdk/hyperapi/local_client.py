"""
Local OCR Client - Fallback when HyperAPI is not accessible
Uses Tesseract OCR for text extraction
"""

import os
import json
from pathlib import Path
from typing import Union
from PIL import Image
import pytesseract

from .exceptions import ParseError, ExtractError, ClassifyError, SplitError


class LocalOCRClient:
    """
    Local OCR client using Tesseract.
    Drop-in replacement for HyperAPIClient when API is not accessible.
    """
    
    def __init__(self, api_key=None, base_url=None, timeout=120.0):
        """Initialize local OCR client (API key not used)."""
        self.api_key = api_key or "local"
        self.base_url = base_url or "local"
        self.timeout = timeout
        print("⚠️  Using LOCAL OCR (Tesseract) - API not accessible")
    
    def parse(self, image_path: Union[str, Path]) -> dict:
        """
        Extract text from image using Tesseract OCR.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        try:
            # Open image and run OCR
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            
            return {"ocr": text}
            
        except Exception as e:
            raise ParseError(f"Local OCR failed: {str(e)}")
    
    def classify(self, image_path: Union[str, Path]) -> dict:
        """
        Classify document type based on OCR text patterns.
        """
        try:
            # Get OCR text
            result = self.parse(image_path)
            text = result["ocr"].lower()
            
            # Simple classification based on keywords
            if "invoice" in text or "bill to" in text or "inv-" in text:
                return {"document_type": "invoice", "confidence": 0.85}
            elif "purchase order" in text or "po-" in text or "p.o." in text:
                return {"document_type": "purchase_order", "confidence": 0.80}
            elif "receipt" in text:
                return {"document_type": "receipt", "confidence": 0.75}
            elif "contract" in text or "agreement" in text:
                return {"document_type": "contract", "confidence": 0.70}
            else:
                return {"document_type": "unknown", "confidence": 0.50}
                
        except Exception as e:
            raise ClassifyError(f"Classification failed: {str(e)}")
    
    def split(self, pdf_path: Union[str, Path]) -> dict:
        """
        Simple split - assume each 2 pages is one document.
        """
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            doc.close()
            
            # Simple heuristic: 2 pages per document
            segments = []
            for i in range(0, total_pages, 2):
                segments.append({
                    "document_index": i // 2,
                    "start_page": i + 1,
                    "end_page": min(i + 2, total_pages),
                    "type": "invoice"
                })
            
            return {"segments": segments, "pages": []}
            
        except Exception as e:
            raise SplitError(f"Split failed: {str(e)}")
    
    def extract(self, file_path: Union[str, Path]) -> dict:
        """
        Extract structured fields from OCR text using pattern matching.
        """
        try:
            # Get OCR text
            result = self.parse(file_path)
            text = result["ocr"]
            
            # Extract common fields using regex
            import re
            
            entities = {}
            
            # Invoice number
            inv_match = re.search(r'(?:invoice|inv)[:\s#-]*([A-Z0-9-]+)', text, re.I)
            if inv_match:
                entities["invoice_number"] = inv_match.group(1)
            
            # PO number
            po_match = re.search(r'(?:purchase order|po|p\.o\.)[:\s#-]*([A-Z0-9-]+)', text, re.I)
            if po_match:
                entities["po_number"] = po_match.group(1)
            
            # Date
            date_match = re.search(r'(?:date|dated)[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text, re.I)
            if date_match:
                entities["date"] = date_match.group(1)
            
            # Vendor name (look for common patterns)
            vendor_match = re.search(r'(?:vendor|from|bill from)[:\s]*([A-Za-z\s&]+(?:Ltd|Pvt|Inc|Corp|LLC)?)', text, re.I)
            if vendor_match:
                entities["vendor_name"] = vendor_match.group(1).strip()
            
            # GSTIN
            gstin_match = re.search(r'\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1})\b', text)
            if gstin_match:
                entities["gstin"] = gstin_match.group(1)
            
            # Total amount
            total_match = re.search(r'(?:total|amount|grand total)[:\s]*(?:Rs\.?|INR|₹)?\s*([\d,]+\.?\d*)', text, re.I)
            if total_match:
                entities["total_amount"] = total_match.group(1)
            
            # Line items (simplified)
            line_items = []
            
            return {
                "data": entities,
                "validation_errors": []
            }
            
        except Exception as e:
            raise ExtractError(f"Extraction failed: {str(e)}")
    
    def process(self, file_path: Union[str, Path]) -> dict:
        """Parse and extract in one call."""
        parse_result = self.parse(file_path)
        extract_result = self.extract(file_path)
        
        return {
            "ocr": parse_result["ocr"],
            "data": extract_result["data"]
        }
    
    def close(self):
        """No-op for compatibility."""
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
