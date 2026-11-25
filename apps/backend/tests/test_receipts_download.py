"""11.8.0: download a receipt, or receipts as a zip with receipts.csv."""

from __future__ import annotations

import csv
import io
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.life import receipts
from tests.test_hub import AUTH, ENV

DOCS = {
    1: {"id": 1, "added_at": "2026-11-03T09:10:00", "title": "Cordless drill", "sender": "Bunnings", "summary": "$199 drill",
        "kind": "receipt", "files": ["email.html", "invoice.pdf"], "receipt_file": "invoice.pdf"},
    2: {"id": 2, "added_at": "2026-10-20T18:00:00", "title": "Order #123: shoes", "sender": "The Iconic", "summary": "Shoes",
        "kind": "receipt", "files": ["email.html"], "receipt_file": "email.html"},
    3: {"id": 3, "added_at": "2026-09-01T08:00:00", "title": "Parking", "sender": "", "summary": "", "kind": "receipt", "files": [], "text": "Paid $12"},
}
FILES = {(1, "invoice.pdf"): b"%PDF-1.7 drill", (2, "email.html"): b"<script>alert(1)</script><p>Shoes</p>"}


@pytest.fixture
def client(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/siris/documents":
            q = request.url.params.get("q", "")
            return httpx.Response(200, json=[{k: v for k, v in d.items() if k not in ("files", "receipt_file", "text")}
                                             for d in DOCS.values() if q.lower() in d["title"].lower()])
        parts = path.split("/")
        if len(parts) == 4 and parts[2] == "documents":
            d = DOCS.get(int(parts[3]))
            return httpx.Response(200, json=d) if d else httpx.Response(404, json={"detail": "No such document"})
        if len(parts) == 6 and parts[4] == "files":
            data = FILES.get((int(parts[3]), parts[5]))
            return httpx.Response(200, content=data) if data else httpx.Response(404)
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    return TestClient(app)


def test_all_receipts_as_a_zip_named_by_date_and_shop(client):
    r = client.get("/api/v1/life/receipts/download", headers=AUTH)
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip" and r.headers["x-receipts"] == "3"
    assert 'filename="Receipts.zip"' in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = sorted(z.namelist())
    assert names == ["2026-09-01 Parking.txt", "2026-10-20 The Iconic - Order #123 shoes.html", "2026-11-03 Bunnings - Cordless drill.pdf", "receipts.csv"]
    assert z.read("2026-11-03 Bunnings - Cordless drill.pdf") == b"%PDF-1.7 drill"
    email = z.read("2026-10-20 The Iconic - Order #123 shoes.html").decode()
    assert email.index("Content-Security-Policy") < email.index("<script>")   # saved emails can't run anything
    rows = list(csv.reader(io.StringIO(z.read("receipts.csv").decode("utf-8-sig"))))
    assert rows[0] == ["Date", "From", "Receipt", "Summary", "File"] and ["2026-11-03", "Bunnings", "Cordless drill", "$199 drill", "2026-11-03 Bunnings - Cordless drill.pdf"] in rows


def test_a_search_a_date_range_or_chosen_ones(client):
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/v1/life/receipts/download?q=drill", headers=AUTH).content))
    assert len(z.namelist()) == 2
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/v1/life/receipts/download?start=2026-10-01&end=2026-10-31", headers=AUTH).content))
    assert [n for n in z.namelist() if n != "receipts.csv"] == ["2026-10-20 The Iconic - Order #123 shoes.html"]
    r = client.get("/api/v1/life/receipts/download?ids=1,3", headers=AUTH)
    assert r.headers["x-receipts"] == "2"
    assert client.get("/api/v1/life/receipts/download?q=nothing", headers=AUTH).status_code == 404
    assert client.get("/api/v1/life/receipts/download").status_code == 401


def test_one_receipt_to_save(client):
    r = client.get("/api/v1/life/documents/1/download", headers=AUTH)
    assert r.status_code == 200 and r.content == b"%PDF-1.7 drill" and r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"] and "2026-11-03%20Bunnings" in r.headers["content-disposition"]
    assert client.get("/api/v1/life/documents/9/download", headers=AUTH).status_code == 404


def test_names_are_safe_everywhere():
    assert receipts.safe_name('a/b\\c:d*?"<>|e\n') == "a b c d e"
    assert receipts.safe_name("...") == "Receipt"
