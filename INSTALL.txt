# ocr-software-haystack: read PDFs and scans in a Haystack pipeline

A Haystack component that sends PDF, PNG, JPEG or TIFF files to the [ocr-software.com OCR API](https://ocr-software.com/) and returns one `Document` per file. The files leave your machine for the API (Helsinki, EU), or for your own server if you set `base_url`.

```
pip install ocr-software-haystack
export OCR_SOFTWARE_API_KEY=ocr_...        # get a key at https://ocr-software.com/order/
```

```python
from ocr_software_haystack import OcrSoftwareConverter

converter = OcrSoftwareConverter(pipeline="NAME@VERSION")   # you pick the pipeline: ocr-software --list-pipelines
documents = converter.run(sources=["scan.pdf"])["documents"]
print(documents[0].content, documents[0].meta)
```

- `pipeline`: required, `name@version`. The list: `ocr-software --list-pipelines` (the `ocr-software` package is installed with this one).
- `format`: `"text"` (default) or `"md"`; Markdown needs a pipeline that offers it (`scan-vlm-ctc@2`).
- `base_url`: default `https://api.ocr-software.com`; for your own server e.g. `http://127.0.0.1:8080`.
- Files are read one after the other, so at most one job is open at the API. A page that failed does not stop the run; the `Document` then has `meta["incomplete"]` with the reason. A file that is missing, empty or not a PDF, PNG, JPEG or TIFF is skipped with a log warning; a wrong key or address stops the run.
- The component works in a `Pipeline`; `to_dict` and `from_dict` keep the key out of the file, it is read from the environment. Haystack 3 loads only trusted modules from YAML: `Pipeline.loads(text, allowed_modules=["ocr_software_haystack"])`.

Tests (fake local service, no network, no key): `pip install -e ".[test]"` and `python -m pytest -p no:cacheprovider .`

MIT, see `LICENSE`. Operated by Helm & Nagel GmbH. [Terms](https://ocr-software.com/legal/saas-terms/) · [Privacy](https://ocr-software.com/legal/privacy/) · [Imprint](https://ocr-software.com/legal/imprint/) · [Security](https://ocr-software.com/legal/security/)
