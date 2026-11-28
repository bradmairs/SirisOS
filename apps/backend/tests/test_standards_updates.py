"""11.21: the weekly check for new versions of the standards in the library."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.api import engineering_standards as es
from app.engineering import standards_updates as su

RealClient = httpx.Client
seen_heads: list[str] = []
downloads: list[str] = []


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setattr(es, "LIBRARY_ROOT", tmp_path / "standards")
    monkeypatch.setenv("SIRISOS_STANDARDS_UPDATES_PATH", str(tmp_path / "standards-updates.json"))
    # The "text" of a fake PDF is everything after its header, ignoring a regenerated timestamp.
    fake = lambda path: SimpleNamespace(pages=[{"page": 1, "text": path.read_bytes()[8:].split(b"|ts")[0].decode()}],  # noqa: E731
                                        indexed=True, extraction_method="native", ocr_attempted=False, ocr_error=None)
    monkeypatch.setattr(es, "extract_standard_pages", fake)
    monkeypatch.setattr("app.services.engineering_standards_ocr.extract_standard_pages", fake)
    return tmp_path


def _client(files: dict[str, bytes], page: str = "") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://pub.example/downloads":
            return httpx.Response(200, text=page, headers={"content-type": "text/html"})
        if url not in files:
            return httpx.Response(404)
        headers = {"etag": f'"{hash(files[url])}"'}
        if request.method == "HEAD":
            seen_heads.append(url)
            return httpx.Response(200, headers=headers)
        downloads.append(url)
        return httpx.Response(200, content=files[url], headers=headers)
    return RealClient(transport=httpx.MockTransport(handler))


def _store(data: bytes, source: dict) -> dict:
    return es._store_document(filename="IDM.pdf", data=data, title="Infrastructure Design Manual", authority="LGIDA",
                              reference="IDM", edition="v5.6", category="Land development", source=source)


def test_a_newer_version_at_a_new_address_becomes_a_new_revision(lib) -> None:
    old = _store(b"%PDF-1.4 IDM five six", {"url": "https://pub.example/IDM_Version_5.6.pdf",
                                             "page": "https://pub.example/downloads", "pattern": r"IDM_Version_([\d.]+)\.pdf"})
    page = '<a href="/IDM_Version_5.6.pdf">IDM 5.6</a> <a href="/IDM_Version_5.10.pdf">IDM 5.10</a> <a href="/IDM_Version_5.9.pdf">5.9</a>'
    files = {"https://pub.example/IDM_Version_5.10.pdf": b"%PDF-1.4 IDM five ten"}
    with _client(files, page) as c:
        out = su.check_one(c, es._normalise_metadata(old))
    assert out["status"] == "updated" and out["new_url"].endswith("5.10.pdf")      # 5.10 beats 5.9: versions, not text
    new = es._normalise_metadata(es._load_metadata(out["new_id"]))
    assert new["revision"] == 2 and new["category"] == "Land development" and new["source"]["url"].endswith("5.10.pdf")
    assert new["filename"] == "IDM_Version_5.10.pdf"
    was = es._normalise_metadata(es._load_metadata(old["id"]))
    assert was["active"] is False and was["superseded_by_id"] == new["id"]


def test_the_same_file_or_the_same_text_regenerated_is_not_an_update(lib) -> None:
    data = b"%PDF-1.4 MUSIC guidelines|ts1"
    doc = _store(data, {"url": "https://pub.example/music"})
    with _client({"https://pub.example/music": data}) as c:
        assert su.check_one(c, es._normalise_metadata(doc))["status"] == "current"
    doc = es._normalise_metadata(es._load_metadata(doc["id"]))
    assert doc["source"]["sha256"]                                                  # remembered for next week
    with _client({"https://pub.example/music": b"%PDF-1.4 MUSIC guidelines|ts2"}) as c:   # regenerated, same words
        out = su.check_one(c, doc)
    assert out["status"] == "current" and "same text" in out["note"]
    with _client({"https://pub.example/music": b"%PDF-1.4 MUSIC guidelines 2027"}) as c:  # same address, new words
        assert su.check_one(c, es._normalise_metadata(es._load_metadata(doc["id"])))["status"] == "updated"


def test_not_a_pdf_is_refused_and_the_run_logs_and_notifies(lib, monkeypatch) -> None:
    good = _store(b"%PDF-1.4 old", {"url": "https://pub.example/a.pdf"})
    _store(b"%PDF-1.4 other", {"url": "https://pub.example/b.pdf"})
    files = {"https://pub.example/a.pdf": b"%PDF-1.4 new", "https://pub.example/b.pdf": b"<html>moved</html>"}
    monkeypatch.setattr(su.httpx, "Client", lambda **kw: _client(files))
    out = su.run(datetime(2026, 11, 29, 4, tzinfo=timezone.utc))
    statuses = sorted(r["status"] for r in out["results"])
    assert statuses == ["error", "updated"]
    doc = su.state()
    assert doc["last"]["updated"] == 1 and "isn't a PDF" in doc["last"]["errors"][0]["why"]
    [msg] = su.push_messages(datetime(2026, 11, 30, tzinfo=timezone.utc))
    assert msg["title"] == "New version of Infrastructure Design Manual" and msg["key"].startswith("standard-updated:")
    assert su.push_messages(datetime(2026, 12, 20, tzinfo=timezone.utc)) == []      # a fortnight on, no longer sent
    assert not es._normalise_metadata(es._load_metadata(good["id"]))["active"]


def test_weekly_on_sunday_from_the_hour(lib) -> None:
    sunday_5am_melb = datetime(2026, 11, 28, 18, tzinfo=timezone.utc)   # Sun 29 Nov 5am AEDT
    assert su.due(sunday_5am_melb)
    assert not su.due(sunday_5am_melb - timedelta(days=1))
    su._save({"events": [], "last_run": sunday_5am_melb.isoformat()})
    assert not su.due(sunday_5am_melb + timedelta(hours=2))


def test_source_can_be_set_and_a_bad_pattern_is_refused(lib) -> None:
    from fastapi.testclient import TestClient

    from app.entrypoint import app
    from tests.test_hub import AUTH

    doc = _store(b"%PDF-1.4 x", {})
    c = TestClient(app, headers=AUTH)
    r = c.patch(f"/api/v1/engineering/standards/{doc['id']}", json={"source_url": "https://pub.example/x.pdf", "source_pattern": r"x_([\d.]+)"})
    assert r.status_code == 200 and r.json()["source"] == {"url": "https://pub.example/x.pdf", "pattern": r"x_([\d.]+)"}
    assert c.patch(f"/api/v1/engineering/standards/{doc['id']}", json={"source_pattern": "x(["}).status_code == 422
    assert c.patch(f"/api/v1/engineering/standards/{doc['id']}", json={"source_url": "ftp://nope"}).status_code == 422
    assert c.patch(f"/api/v1/engineering/standards/{doc['id']}", json={"source_url": ""}).json()["source"] is None
    status = c.get("/api/v1/engineering/standards/updates").json()
    assert status["weekly_hour"] == 4 and status["events"] == []


def test_an_unchanged_file_isnt_downloaded_again(lib) -> None:
    data = b"%PDF-1.4 MRWA survey manual"
    doc = _store(data, {"url": "https://pub.example/survey"})
    with _client({"https://pub.example/survey": data}) as c:
        su.check_one(c, es._normalise_metadata(doc))                 # first time: downloaded, its fingerprint kept
    downloads.clear()
    with _client({"https://pub.example/survey": data}) as c:
        assert su.check_one(c, es._normalise_metadata(es._load_metadata(doc["id"])))["status"] == "current"
    assert downloads == [] and seen_heads[-1] == "https://pub.example/survey"   # asked, not downloaded
    with _client({"https://pub.example/survey": b"%PDF-1.4 MRWA survey manual v2"}) as c:   # a new file: new ETag
        assert su.check_one(c, es._normalise_metadata(es._load_metadata(doc["id"])))["status"] == "updated"
