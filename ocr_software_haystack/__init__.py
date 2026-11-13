"""Haystack component for the ocr-software.com OCR API."""
from ocr_software import OcrError

from .converter import OcrSoftwareConverter

__version__ = "0.1.0"
__all__ = ["OcrSoftwareConverter", "OcrError", "__version__"]
