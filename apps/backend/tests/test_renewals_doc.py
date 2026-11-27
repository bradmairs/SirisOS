"""11.19: a renewal keeps its document (a policy schedule, a scan of the licence)."""

from fastapi.testclient import TestClient

from app.entrypoint import app
from tests.test_hub import AUTH


def test_a_renewal_links_and_unlinks_its_document(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_RENEWALS_PATH", str(tmp_path / "renewals.json"))
    c = TestClient(app, headers=AUTH)
    [r] = c.post("/api/v1/renewals", json={"name": "Home and contents", "kind": "insurance", "expires": "2027-03-01"}).json()["renewals"]
    [r] = c.patch(f"/api/v1/renewals/{r['id']}", json={"doc_id": 42}).json()["renewals"]
    assert r["doc_id"] == 42
    [r] = c.patch(f"/api/v1/renewals/{r['id']}", json={"expires": "2028-03-01"}).json()["renewals"]
    assert r["doc_id"] == 42 and r["expires"] == "2028-03-01"   # kept through a renewal
    [r] = c.patch(f"/api/v1/renewals/{r['id']}", json={"doc_id": 0}).json()["renewals"]
    assert "doc_id" not in r
