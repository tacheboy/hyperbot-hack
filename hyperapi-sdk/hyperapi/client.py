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
            or "https://api.hyperapi.dev"
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
                    f"{self.base_url}/v1/parse",
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
            
            # API returns: {"status": "success", "result": {"ocr": "..."}}
            if data.get("status") == "success" and "result" in data:
                result = data["result"]
                if "ocr" in result:
                    return {"ocr": result["ocr"]}
            
            # Fallback for other formats
            if "result" in data and "ocr" in data["result"]:
                return {"ocr": data["result"]["ocr"]}
            elif "ocr" in data:
                return {"ocr": data["ocr"]}
            
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
                    f"{self.base_url}/v1/classify",
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
            
            # API returns: {"status": "success", "result": {"label": "invoice", "confidence": 0.98}}
            if data.get("status") == "success" and "result" in data:
                result = data["result"]
                return {
                    "document_type": result.get("label", "unknown"),
                    "confidence": result.get("confidence", 1.0)
                }
            
            # Fallback
            if "result" in data and "label" in data["result"]:
                return {
                    "document_type": data["result"]["label"],
                    "confidence": data["result"].get("confidence", 1.0)
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
                    f"{self.base_url}/v1/split",
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
            
            # API returns: {"status": "success", "result": {"segments": [...]}}
            if data.get("status") == "success" and "result" in data:
                result = data["result"]
                return {
                    "segments": result.get("segments", []),
                    "pages": result.get("pages", [])
                }
            
            # Fallback
            if "result" in data and "segments" in data["result"]:
                return {
                    "segments": data["result"]["segments"],
                    "pages": data["result"].get("pages", [])
                }
            
            raise SplitError(f"Unexpected response format: {data}")

        except httpx.TimeoutException:
            raise SplitError("Request timed out", status_code=504)
        except httpx.RequestError as e:
            raise SplitError(f"Request failed: {str(e)}")

    def process(self, file_path: Union[str, Path]) -> dict:
        """
        Parse and extract in one call.

        Args:
            file_path: Path to the document file

        Returns:
            dict with keys:
                - ocr: Raw OCR text
                - data: Extracted structured fields
        """
        parse_result = self.parse(file_path)
        extract_result = self.extract(file_path)

        return {
            "ocr": parse_result["ocr"],
            "data": extract_result["data"]
        }

    def extract(self, file_path: Union[str, Path]) -> dict:
        """
        Extract structured fields from document file.
        
        POST /v1/extract - Extract structured data fields from documents 
        using vision-language models for high accuracy.

        Args:
            file_path: Path to the document file (PDF, PNG, JPG)

        Returns:
            dict with keys:
                - entities: Extracted fields (invoice_number, date, vendor_name, etc.)
                - line_items: List of line items with description, quantity, price, etc.

        Raises:
            FileNotFoundError: If file doesn't exist
            AuthenticationError: If API key is invalid
            ExtractError: If extraction fails
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".pdf": "application/pdf",
        }
        content_type = content_types.get(suffix, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, content_type)}
                response = self._client.post(
                    f"{self.base_url}/v1/extract",
                    files=files,
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
            
            # API returns: {"status": "success", "result": {"entities": {...}, "line_items": [...]}}
            if data.get("status") == "success" and "result" in data:
                result = data["result"]
                # Flatten entities and line_items into a single dict
                extracted_data = {}
                if "entities" in result:
                    extracted_data.update(result["entities"])
                if "line_items" in result:
                    extracted_data["line_items"] = result["line_items"]
                return {
                    "data": extracted_data,
                    "validation_errors": []
                }
            
            # Fallback
            if "result" in data:
                return {"data": data["result"], "validation_errors": []}
            
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
