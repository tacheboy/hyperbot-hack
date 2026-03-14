"""
HyperAPI Client
"""

import os
from pathlib import Path
from typing import Union, Optional

import httpx

from .exceptions import AuthenticationError, ParseError, ExtractError, ClassifyError, SplitError


class HyperAPIClient:
    """
    Client for interacting with HyperAPI.

    Usage:
        from hyperapi import HyperAPIClient

        client = HyperAPIClient(api_key="your-api-key")

        # Parse a document
        result = client.parse("invoice.png")
        print(result["ocr"])

        # Extract structured fields
        fields = client.extract(result["ocr"])
        print(fields["data"])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 120.0
    ):
        """
        Initialize HyperAPI client.

        Args:
            api_key: API key for authentication. If not provided, reads from
                     HYPERAPI_KEY environment variable.
            base_url: Base URL for the API. If not provided, reads from
                      HYPERAPI_URL environment variable or uses default.
            timeout: Request timeout in seconds (default: 120s).
        """
        self.api_key = api_key or os.environ.get("HYPERAPI_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "API key required. Pass api_key or set HYPERAPI_KEY environment variable."
            )

        self.base_url = (
            base_url
            or os.environ.get("HYPERAPI_URL")
            or "https://apis.hyperbots.com"
        )
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def _get_headers(self) -> dict:
        """Get request headers with API key."""
        return {"X-API-Key": self.api_key}

    def parse(self, image_path: Union[str, Path]) -> dict:
        """
        Parse a document image using OCR.
        
        POST /api/v1/parse - Extract text from documents including PDFs and images.
        Optimized for financial documents, invoices, and forms.

        Args:
            image_path: Path to the image file (PNG, JPG, PDF, etc.)

        Returns:
            dict with keys:
                - ocr: Extracted text string

        Raises:
            FileNotFoundError: If image file doesn't exist
            AuthenticationError: If API key is invalid
            ParseError: If parsing fails
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Determine content type
        suffix = image_path.suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".pdf": "application/pdf",
        }
        content_type = content_types.get(suffix, "application/octet-stream")

        try:
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, content_type)}
                response = self._client.post(
                    f"{self.base_url}/api/v1/parse",
                    files=files,
                    headers=self._get_headers()
                )

            if response.status_code == 401:
                raise AuthenticationError("Invalid API key", status_code=401)

            if response.status_code != 200:
                raise ParseError(
                    f"Parse failed (status {response.status_code}): {response.text}",
                    status_code=response.status_code
                )

            data = response.json()
            
            # Handle various response formats
            # Format 1: {"ocr": "text"}
            if "ocr" in data:
                return {"ocr": data["ocr"]}
            # Format 2: {"result": {"ocr": "text"}}
            elif "result" in data and isinstance(data["result"], dict):
                if "ocr" in data["result"]:
                    return {"ocr": data["result"]["ocr"]}
                elif "text" in data["result"]:
                    return {"ocr": data["result"]["text"]}
            # Format 3: {"text": "text"}
            elif "text" in data:
                return {"ocr": data["text"]}
            # Format 4: {"data": {"ocr": "text"}}
            elif "data" in data and isinstance(data["data"], dict):
                if "ocr" in data["data"]:
                    return {"ocr": data["data"]["ocr"]}
                elif "text" in data["data"]:
                    return {"ocr": data["data"]["text"]}
            
            # If we can't find OCR text, raise error
            raise ParseError(f"Unexpected response format: {data}")

        except httpx.TimeoutException:
            raise ParseError("Request timed out", status_code=504)
        except httpx.RequestError as e:
            raise ParseError(f"Request failed: {str(e)}")

    def classify(self, image_path: Union[str, Path]) -> dict:
        """
        Classify document type automatically.
        
        POST /api/v1/classify - Categorize document types automatically — 
        invoices, contracts, receipts, IDs, and more.

        Args:
            image_path: Path to the document file

        Returns:
            dict with keys:
                - document_type: Detected type (invoice, po, receipt, etc.)
                - confidence: Confidence score (0-1)

        Raises:
            FileNotFoundError: If image file doesn't exist
            AuthenticationError: If API key is invalid
            ClassifyError: If classification fails
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        suffix = image_path.suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".pdf": "application/pdf",
        }
        content_type = content_types.get(suffix, "application/octet-stream")

        try:
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, content_type)}
                response = self._client.post(
                    f"{self.base_url}/api/v1/classify",
                    files=files,
                    headers=self._get_headers()
                )

            if response.status_code == 401:
                raise AuthenticationError("Invalid API key", status_code=401)

            if response.status_code != 200:
                raise ClassifyError(
                    f"Classify failed (status {response.status_code}): {response.text}",
                    status_code=response.status_code
                )

            data = response.json()
            
            # Handle various response formats
            if "document_type" in data:
                return {
                    "document_type": data["document_type"],
                    "confidence": data.get("confidence", 1.0)
                }
            elif "result" in data and isinstance(data["result"], dict):
                return {
                    "document_type": data["result"].get("document_type", "unknown"),
                    "confidence": data["result"].get("confidence", 1.0)
                }
            elif "type" in data:
                return {
                    "document_type": data["type"],
                    "confidence": data.get("confidence", 1.0)
                }
            
            raise ClassifyError(f"Unexpected response format: {data}")

        except httpx.TimeoutException:
            raise ClassifyError("Request timed out", status_code=504)
        except httpx.RequestError as e:
            raise ClassifyError(f"Request failed: {str(e)}")

    def split(self, pdf_path: Union[str, Path]) -> dict:
        """
        Split multi-page documents into individual pages or logical sections.
        
        POST /api/v1/split - Split multi-page documents into individual pages 
        or logical sections for downstream processing.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            dict with keys:
                - pages: List of page information
                - sections: List of logical document sections

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            AuthenticationError: If API key is invalid
            SplitError: If splitting fails
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            with open(pdf_path, "rb") as f:
                files = {"file": (pdf_path.name, f, "application/pdf")}
                response = self._client.post(
                    f"{self.base_url}/api/v1/split",
                    files=files,
                    headers=self._get_headers(),
                    timeout=300.0  # Splitting can take time for large PDFs
                )

            if response.status_code == 401:
                raise AuthenticationError("Invalid API key", status_code=401)

            if response.status_code != 200:
                raise SplitError(
                    f"Split failed (status {response.status_code}): {response.text}",
                    status_code=response.status_code
                )

            data = response.json()
            
            # Handle various response formats
            if "pages" in data or "sections" in data:
                return {
                    "pages": data.get("pages", []),
                    "sections": data.get("sections", [])
                }
            elif "result" in data and isinstance(data["result"], dict):
                return {
                    "pages": data["result"].get("pages", []),
                    "sections": data["result"].get("sections", [])
                }
            
            raise SplitError(f"Unexpected response format: {data}")

        except httpx.TimeoutException:
            raise SplitError("Request timed out", status_code=504)
        except httpx.RequestError as e:
            raise SplitError(f"Request failed: {str(e)}")

    def process(self, image_path: Union[str, Path], doc_type: Optional[str] = None) -> dict:
        """
        Parse and extract in one call.

        Args:
            image_path: Path to the document file
            doc_type: Optional document type hint for better extraction

        Returns:
            dict with keys:
                - ocr: Raw OCR text
                - data: Extracted structured fields
                - validation_errors: List of validation errors
        """
        parse_result = self.parse(image_path)
        extract_result = self.extract(parse_result["ocr"], doc_type=doc_type)

        return {
            "ocr": parse_result["ocr"],
            "data": extract_result["data"],
            "validation_errors": extract_result.get("validation_errors", [])
        }

    def extract(self, ocr_text: str, doc_type: Optional[str] = None) -> dict:
        """
        Extract structured fields from OCR text.
        
        POST /api/v1/extract - Extract structured data fields from documents 
        using vision-language models for high accuracy.

        Args:
            ocr_text: OCR text from parsed document (from parse() result)
            doc_type: Optional document type hint (invoice, po, bank_statement, etc.)

        Returns:
            dict with keys:
                - data: Extracted fields (invoice_number, date, line_items, etc.)
                - validation_errors: List of validation errors (if any)

        Raises:
            AuthenticationError: If API key is invalid
            ExtractError: If extraction fails
        """
        try:
            payload = {"text": ocr_text}
            if doc_type:
                payload["document_type"] = doc_type
            
            response = self._client.post(
                f"{self.base_url}/api/v1/extract",
                json=payload,
                headers=self._get_headers(),
                timeout=600.0  # LLM calls can take longer
            )

            if response.status_code == 401:
                raise AuthenticationError("Invalid API key", status_code=401)

            if response.status_code != 200:
                raise ExtractError(
                    f"Extract failed (status {response.status_code}): {response.text}",
                    status_code=response.status_code
                )

            data = response.json()
            
            # Handle various response formats
            # Format 1: {"data": {...}, "validation_errors": [...]}
            if "data" in data:
                return {
                    "data": data["data"],
                    "validation_errors": data.get("validation_errors", [])
                }
            # Format 2: {"result": {...}}
            elif "result" in data:
                result = data["result"]
                if isinstance(result, dict):
                    return {
                        "data": result,
                        "validation_errors": data.get("validation_errors", [])
                    }
            # Format 3: Direct fields
            elif any(key in data for key in ["invoice_number", "vendor_name", "total", "line_items"]):
                return {
                    "data": data,
                    "validation_errors": []
                }
            
            # If we can't find structured data, raise error
            raise ExtractError(f"Unexpected response format: {data}")

        except httpx.TimeoutException:
            raise ExtractError("Request timed out", status_code=504)
        except httpx.RequestError as e:
            raise ExtractError(f"Request failed: {str(e)}")

    def process(self, image_path: Union[str, Path]) -> dict:
        """
        Parse and extract in one call.

        Args:
            image_path: Path to the document file

        Returns:
            dict with keys:
                - ocr: Raw OCR text
                - data: Extracted structured fields
        """
        parse_result = self.parse(image_path)
        extract_result = self.extract(parse_result["ocr"])

        return {
            "ocr": parse_result["ocr"],
            "data": extract_result["data"]
        }

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
