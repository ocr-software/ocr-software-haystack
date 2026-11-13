"""Haystack converter: PDF, PNG, JPEG or TIFF files in, one Document per file out, read by the ocr-software.com API.

One file after the other, so at most one job is open at the API (rules: doku integrationen-regeln.md). Retries, size
limits and the document check live in the ocr-software package. The pipeline has no default: the user names it.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from haystack import Document, component, default_from_dict, default_to_dict
from haystack.utils import Secret, deserialize_secrets_inplace
from ocr_software import Client, OcrError, PagesUnread

logger = logging.getLogger(__name__)


@component
class OcrSoftwareConverter:
    """Usage: OcrSoftwareConverter(pipeline="NAME@VERSION").run(sources=["scan.pdf"]). format "md" needs a pipeline that
    offers Markdown (scan-vlm-ctc@2); the default "text" works everywhere."""

    def __init__(self, pipeline: str, api_key: Secret = Secret.from_env_var("OCR_SOFTWARE_API_KEY"),
                 base_url: Optional[str] = None, format: str = "text", timeout: int = 3600):
        if not pipeline:
            raise ValueError("pipeline is required: name@version (ocr-software --list-pipelines)")
        if format not in ("text", "md"):
            raise ValueError("format must be 'text' or 'md'")
        self.pipeline, self.api_key, self.base_url, self.format, self.timeout = pipeline, api_key, base_url, format, timeout

    def to_dict(self) -> Dict[str, Any]:
        return default_to_dict(self, pipeline=self.pipeline, api_key=self.api_key.to_dict(), base_url=self.base_url,
                               format=self.format, timeout=self.timeout)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OcrSoftwareConverter":
        deserialize_secrets_inplace(data["init_parameters"], keys=["api_key"])
        return default_from_dict(cls, data)

    @component.output_types(documents=List[Document])
    def run(self, sources: List[Union[str, Path]]) -> Dict[str, List[Document]]:
        """A page that failed does not stop the run: the Document is returned with meta["incomplete"] set to the reason.
        A file that is missing, empty or not a PDF/PNG/JPEG/TIFF is skipped with a warning; other errors are raised."""
        client = Client(api_key=self.api_key.resolve_value() or "", base_url=self.base_url)
        documents = []
        for source in sources:
            meta = {"file_path": str(source), "pipeline": self.pipeline}
            try:
                data = client.ocr(str(source), self.pipeline, self.format, timeout=self.timeout)
            except PagesUnread as e:
                data, meta["incomplete"] = e.data, str(e)
            except OcrError as e:
                if e.code != "bad_input":  # key, address, service errors: the whole run is wrong, say so
                    raise
                logger.warning("skipped %s: %s", source, e)  # one unreadable file must not stop the other files
                continue
            documents.append(Document(content=data.decode("utf-8"), meta=meta))
        return {"documents": documents}
