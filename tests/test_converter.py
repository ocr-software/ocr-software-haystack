import pytest

from haystack import Pipeline
from ocr_software_haystack import OcrError, OcrSoftwareConverter


def make(fake, **kw):
    return OcrSoftwareConverter(pipeline="p@1", base_url=fake.url, **kw)


def test_one_document_per_file_with_source_and_page_in_meta(fake, docs):
    out = make(fake).run(sources=docs[:2])["documents"]
    assert [d.content for d in out] == ["text of j1", "text of j2"]
    assert out[0].meta == {"file_path": docs[0], "pipeline": "p@1", "page": 1}


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
    with pytest.raises(ValueError, match="on_error"):
        make(fake, on_error="ignore")
    assert fake.log == []


def test_one_bad_file_is_skipped_with_a_warning_the_others_are_read(fake, docs, tmp_path, caplog):
    """Review 13.11.2026: an unreadable file in the list stopped the run and dropped the files already read."""
    empty = tmp_path / "leer.pdf"
    empty.write_bytes(b"")
    with caplog.at_level("WARNING"):
        out = make(fake).run(sources=[docs[0], str(empty), str(tmp_path / "nope.pdf"), docs[1]])["documents"]
    assert [d.content for d in out] == ["text of j1", "text of j2"]
    assert "file is empty" in caplog.text and "not a file" in caplog.text


THREE_PAGES = b"one\n\ftwo\n\fthree\n"


def test_one_document_per_page_with_page_number_from_1(fake, docs):
    """Kundentest 13.11.2026 (Fund 2): a RAG citation 'page 4' needs meta["page"]."""
    fake.state["result"] = THREE_PAGES
    out = make(fake).run(sources=docs[:1])["documents"]
    assert [(d.content, d.meta["page"], d.meta["file_path"]) for d in out] == [("one\n", 1, docs[0]), ("two\n", 2, docs[0]), ("three\n", 3, docs[0])]


def test_markdown_pages_and_the_switch_for_one_document_per_file(fake, docs):
    fake.state["result"] = b"## Page 1\n\nalpha\n\n## Page 2\n\nbeta\n"
    out = make(fake, format="md").run(sources=docs[:1])["documents"]
    assert [(d.content, d.meta["page"]) for d in out] == [("alpha\n", 1), ("beta\n", 2)]
    whole = make(fake, format="md", split_pages=False).run(sources=docs[:1])["documents"]
    assert len(whole) == 1 and "page" not in whole[0].meta and whole[0].content.startswith("## Page 1")


def test_an_unread_page_marks_every_page_document_of_the_file(fake, docs):
    fake.state["result"], fake.state["unread"] = THREE_PAGES, True
    out = make(fake).run(sources=docs[:1])["documents"]
    assert len(out) == 3 and all("1 page(s) failed" in d.meta["incomplete"] for d in out)


def test_no_pipeline_uses_the_cheapest_and_says_so(fake, docs, caplog):
    """Kundentest 13.11.2026 (Fund 4): pipeline optional, default as in the Python client; the choice is in meta and log."""
    with caplog.at_level("INFO"):
        out = OcrSoftwareConverter(base_url=fake.url).run(sources=docs[:2])["documents"]
    assert {d.meta["pipeline"] for d in out} == {"cheap@1"} and "using cheap@1" in caplog.text
    assert all("pipeline=cheap@1" in q for q in fake.queries if "dry_run" not in q and q.startswith("pipeline"))
    assert OcrSoftwareConverter.from_dict(OcrSoftwareConverter().to_dict()).pipeline is None


def test_on_error_raise_stops_at_the_first_bad_file(fake, docs, tmp_path):
    with pytest.raises(OcrError, match="not a file"):
        make(fake, on_error="raise").run(sources=[docs[0], str(tmp_path / "nope.pdf"), docs[1]])
    assert fake.state["jobs"] == 1


def test_only_bad_files_is_an_error_not_an_empty_list(fake, tmp_path):
    """Kundentest 13.11.2026 (Fund 3): a typo in the only path gave [] and no error."""
    with pytest.raises(OcrError, match="none of the 2 files could be read.*nope.pdf") as e:
        make(fake).run(sources=[str(tmp_path / "nope.pdf"), str(tmp_path / "x.pdf")])
    assert e.value.code == "bad_input"
    assert make(fake).run(sources=[])["documents"] == []


def test_ocr_error_can_be_imported_from_the_package():
    import ocr_software
    import ocr_software_haystack
    assert ocr_software_haystack.OcrError is ocr_software.OcrError
