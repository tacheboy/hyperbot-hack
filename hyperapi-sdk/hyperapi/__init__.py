"""
HyperAPI Python SDK
Financial document processing APIs that scale well.
"""

from .client import HyperAPIClient
from .local_client import LocalOCRClient
from .exceptions import (
    HyperAPIError, 
    AuthenticationError, 
    ParseError, 
    ExtractError,
    ClassifyError,
    SplitError
)

__version__ = "0.1.0"
__all__ = [
    "HyperAPIClient",
    "LocalOCRClient",
    "HyperAPIError", 
    "AuthenticationError", 
    "ParseError", 
    "ExtractError",
    "ClassifyError",
    "SplitError"
]
