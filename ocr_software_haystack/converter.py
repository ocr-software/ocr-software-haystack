"""Haystack converter: PDF, PNG, JPEG or TIFF files in, one Document per page out, read by the ocr-software.com API.

One file after the other, so at most one job is open at the API (rules: doku integrationen-regeln.md). Retries, size
limits and the document check live in the ocr-software package. Without a pipeline the default is used: the fastest
and cheapest available one (ocr_software.advice.default_pipeline), named in the log.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from haystack import Document, component, default_from_dict, default_to_dict
from haystack.utils import Secret, deserialize_secrets_inplace
from ocr_software import Client, OcrError, PagesUnread, split_pages

logger = logging.getLogger(__name__)


@component
class OcrSoftwareConverter:
    """Usage: OcrSoftwareConverter().run(sources=["scan.pdf"]). pipeline: "name@version" (ocr-software --list-pipelines),
    default the fastest and cheapest. Each Document is one page, meta["page"] counts from 1; split_pages=False gives one
    Document per file (pages separated by a form feed in "text", by "## Page N" headings in "md"). format "md" works
    with every pipeline; real headings and lists need scan-vlm-ctc@2. on_error "skip" (default) skips a file that is
    missing, empty or not a PDF/PNG/JPEG/TIFF with a log warning, "raise" raises instead."""

    def __init__(self, pipeline: Optional[str] = None, api_key: Secret = Secret.from_env_var("OCR_SOFTWARE_API_KEY"),
                 base_url: Optional[str] = None, format: str = "text", timeout: int = 3600, split_pages: bool = True,
                 on_error: str = "skip"):
        if format not in ("text", "md"):
            raise ValueError("format must be 'text' or 'md'")
        if on_error not in ("skip", "raise"):
            raise ValueError("on_error must be 'skip' or 'raise'")
        self.pipeline, self.api_key, self.base_url, self.format, self.timeout = pipeline, api_key, base_url, format, timeout
        self.split_pages, self.on_error = split_pages, on_error

    def to_dict(self) -> Dict[str, Any]:
        return default_to_dict(self, pipeline=self.pipeline, api_key=self.api_key.to_dict(), base_url=self.base_url,
                               format=self.format, timeout=self.timeout, split_pages=self.split_pages, on_error=self.on_error)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OcrSoftwareConverter":
        deserialize_secrets_inplace(data["init_parameters"], keys=["api_key"])
        return default_from_dict(cls, data)

    @component.output_types(documents=List[Document])
    def run(self, sources: List[Union[str, Path]]) -> Dict[str, List[Document]]:
        """A page that failed does not stop the run: the Documents of that file carry meta["incomplete"] with the reason.
        Other errors (key, address, service) are raised. If not one file could be read, that is an error, never []."""
        client = Client(api_key=self.api_key.resolve_value() or "", base_url=self.base_url)
        pipeline = self.pipeline or client.default_pipeline()
        if not self.pipeline:
            logger.info("no pipeline given, using %s (the fastest and cheapest available)", pipeline)
        documents, skipped = [], []
        for source in sources:
            meta = {"file_path": str(source), "pipeline": pipeline}
            try:
                data = client.ocr(str(source), pipeline, self.format, timeout=self.timeout)
            except PagesUnread as e:
                data, meta["incomplete"] = e.data, str(e)
            except OcrError as e:
                if e.code != "bad_input" or self.on_error == "raise":  # key, address, service errors: the whole run is wrong, say so
                    raise
                logger.warning("skipped %s: %s", source, e)  # one unreadable file must not stop the other files
                skipped.append(str(e))
                continue
            text = data.decode("utf-8")
            pages = split_pages(text, self.format) if self.split_pages else [(None, text)]
            for number, content in pages:
                documents.append(Document(content=content, meta=dict(meta, page=number) if number else dict(meta)))
        if skipped and not documents:
            raise OcrError("none of the %d files could be read, first problem: %s" % (len(skipped), skipped[0]), "bad_input")
        return {"documents": documents}
