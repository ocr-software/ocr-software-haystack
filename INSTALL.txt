# ocr-software-haystack: read PDFs and scans in a Haystack pipeline

A Haystack component that sends PDF, PNG, JPEG or TIFF files to the [ocr-software.com OCR API](https://ocr-software.com/) and returns one `Document` per page. The files leave your machine for the API (Helsinki, EU), or for your own server if you set `base_url`.

```
pip install git+https://github.com/ocr-software/ocr-software-haystack
# not on PyPI yet; after the first release: pip install ocr-software-haystack
# the client ocr-software comes from PyPI by itself
export OCR_SOFTWARE_API_KEY=ocr_...        # get a key at https://ocr-software.com/order/
```

```python
from ocr_software_haystack import OcrSoftwareConverter

converter = OcrSoftwareConverter()          # no pipeline given: the cheapest available one, named in the log and in meta
documents = converter.run(sources=["scan.pdf"])["documents"]
print(documents[0].content, documents[0].meta)   # meta: file_path, pipeline, page (1-based)
```

- `pipeline`: optional, `name@version`. Without it the cheapest available pipeline is used and logged (same rule as the `ocr-software` command). The list: `ocr-software --list-pipelines`.
- `format`: `"text"` (default) or `"md"`; Markdown works with `scan-ctc@2` too (only `## Page N` headings) and with `scan-vlm-ctc@2` (headings, tables, more layout).
- `split_pages`: `True` (default) gives one `Document` per page with `meta["page"]`, counted from 1, so a RAG answer can cite "page 4". `False` gives one `Document` per file. The text result separates pages with a form feed (`\f`), the Markdown result starts each page with `## Page N`; the component splits at exactly these marks.
- `base_url`: default `https://api.ocr-software.com`; for your own server e.g. `http://127.0.0.1:8080`.
- Files are read one after the other, so at most one job is open at the API. A page that failed does not stop the run; the `Document` then has `meta["incomplete"]` with the reason. A file that is missing, empty or not a PDF, PNG, JPEG or TIFF is skipped with a log warning, unless `on_error="raise"` is set, which stops at the first such file with an `OcrError`. If every file was skipped, the run raises `OcrError` instead of returning an empty list. A wrong key or address always stops the run; import `OcrError` from `ocr_software_haystack`.
- Wrong API keys: after several wrong keys from one address the service answers `429 locked_out` with `Retry-After` for wrong keys from that address (a correct key still works, also from the same office network). Do not retry in a loop; fix the key.
- The component works in a `Pipeline`; `to_dict` and `from_dict` keep the key out of the file, it is read from the environment. Haystack 3 loads only trusted modules from YAML: `Pipeline.loads(text, allowed_modules=["ocr_software_haystack"])`.

Tests (fake local service, no network, no key): `pip install -e ".[test]"` and `python -m pytest -p no:cacheprovider .`

MIT, see `LICENSE`. Operated by Helm & Nagel GmbH. [Terms](https://ocr-software.com/legal/saas-terms/) · [Privacy](https://ocr-software.com/legal/privacy/) · [Imprint](https://ocr-software.com/legal/imprint/) · [Security](https://ocr-software.com/legal/security/)
