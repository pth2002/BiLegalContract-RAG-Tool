from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _make_minimal_docx_bytes(text: str = "Test contract text") -> bytes:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>"""

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document)
    return buffer.getvalue()


def _build_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DOCUMENT_STORE_PATH", str(tmp_path / "documents.json"))

    from src.config import get_config
    from src.services.document_store_service import reset_document_store_for_tests

    get_config.cache_clear()
    reset_document_store_for_tests(tmp_path / "documents.json")

    from src.main import app

    return TestClient(app)


def test_health_endpoint(tmp_path, monkeypatch):
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_upload_get_and_delete_document_persisted(tmp_path, monkeypatch):
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/documents/upload",
        params={"session_id": "sess_test"},
        files={
            "file": (
                "contract.docx",
                _make_minimal_docx_bytes("Payment terms"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    document_id = payload["document"]["id"]

    store_file = tmp_path / "documents.json"
    assert store_file.exists()
    assert document_id in store_file.read_text(encoding="utf-8")

    list_response = client.get("/api/documents", params={"session_id": "sess_test"})
    assert list_response.status_code == 200
    assert list_response.json()["documents"][0]["id"] == document_id

    get_response = client.get(f"/api/documents/{document_id}")
    assert get_response.status_code == 200
    assert get_response.json()["document"]["session_id"] == "sess_test"

    delete_response = client.delete(f"/api/documents/{document_id}")
    assert delete_response.status_code == 200
    assert client.get(f"/api/documents/{document_id}").status_code == 404


def test_analyze_stream_returns_404_for_unknown_document(tmp_path, monkeypatch):
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/analyze/stream",
        json={"document_id": "550e8400-e29b-41d4-a716-446655440000", "perspective": "party_a"},
    )

    assert response.status_code == 404
