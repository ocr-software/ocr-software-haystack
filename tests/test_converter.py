import pytest

from haystack import Pipeline
from ocr_software_haystack import OcrSoftwareConverter


def make(fake, **kw):
    return OcrSoftwareConverter(pipeline="p@1", base_url=fake.url, **kw)


def test_one_document_per_file_with_source_in_meta(fake, docs):
    out = make(fake).run(sources=docs[:2])["documents"]
    assert [d.content for d in out] == ["text of j1", "text of j2"]
    assert out[0].meta == {"file_path": docs[0], "pipeline": "p@1"}


def test_files_go_one_after_the_other_never_two_jobs_open(fake, docs):
    make(fake).run(sources=docs)
    calls = [(m, p) for m, p, _, _ in fake.log]
    submits = [i for i, c in enumerate(calls) if c == ("POST", "/v1/jobs")]
    assert len(submits) == 3
    for n, (first, second) in enumerate(zip(submits, submits[1:]), 1):
        assert ("GET", "/v1/jobs/j%d/result" % n) in calls[first:second]


def test_busy_503_is_retried_with_one_idempotency_key(fake, docs):
    fake.state["fail_submits"] = 2
    out = make(fake).run(sources=docs[:1])["documents"]
    keys = {k for m, p, _, k in fake.log if m == "POST"}
    assert out[0].content == "text of j1" and len(keys) == 1 and None not in keys and fake.state["jobs"] == 1


def test_unread_page_is_flagged_not_hidden(fake, docs):
    fake.state["unread"] = True
    doc = make(fake).run(sources=docs[:1])["documents"][0]
    assert doc.content == "text of j1" and "1 page(s) failed" in doc.meta["incomplete"]


def test_key_is_not_in_the_serialized_component(fake):
    data = make(fake).to_dict()
    assert "ocr_testkey" not in str(data)
    again = OcrSoftwareConverter.from_dict(data)
    assert again.pipeline == "p@1" and again.format == "text"


def test_runs_inside_a_haystack_pipeline(fake, docs):
    pipe = Pipeline()
    pipe.add_component("ocr", make(fake))
    out = pipe.run({"ocr": {"sources": docs[:1]}})
    assert out["ocr"]["documents"][0].content == "text of j1"
    assert all(auth == "Bearer ocr_testkey" for _, _, auth, _ in fake.log)


def test_bad_format_and_missing_file_fail_clearly(fake, tmp_path):
    with pytest.raises(ValueError):
        make(fake, format="pdf")
    with pytest.raises(ValueError, match="pipeline is required"):
        OcrSoftwareConverter(pipeline="")
    assert fake.log == []


def test_one_bad_file_is_skipped_with_a_warning_the_others_are_read(fake, docs, tmp_path, caplog):
    """Review 13.11.2026: an unreadable file in the list stopped the run and dropped the files already read."""
    empty = tmp_path / "leer.pdf"
    empty.write_bytes(b"")
    with caplog.at_level("WARNING"):
        out = make(fake).run(sources=[docs[0], str(empty), str(tmp_path / "nope.pdf"), docs[1]])["documents"]
    assert [d.content for d in out] == ["text of j1", "text of j2"]
    assert "file is empty" in caplog.text and "not a file" in caplog.text
