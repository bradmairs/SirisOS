from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.engineering_standards_ocr import extract_standard_pages
from app.services.engineering_standards_search import rank_pages

router = APIRouter(prefix="/api/v1/engineering/standards", tags=["engineering"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
LIBRARY_ROOT = Path(os.getenv("SIRISOS_STANDARDS_PATH", "/app/data/standards"))
MAX_UPLOAD_BYTES = int(os.getenv("SIRISOS_STANDARDS_MAX_UPLOAD_MB", "100")) * 1024 * 1024


class StandardDocumentResponse(BaseModel):
    id: str
    title: str
    authority: str
    reference: str | None = None
    edition: str | None = None
    filename: str
    uploaded_at: str
    pages: int
    indexed: bool
    extraction_method: str = "native"
    ocr_attempted: bool = False
    ocr_error: str | None = None
    active: bool = True
    archived_at: str | None = None
    supersedes_id: str | None = None
    superseded_by_id: str | None = None
    revision: int = 1


class StandardSearchHit(BaseModel):
    document: StandardDocumentResponse
    page: int | None = None
    snippet: str | None = None
    score: int | None = None
    citation: str | None = None


class StandardSearchResponse(BaseModel):
    query: str
    hits: list[StandardSearchHit]


class StandardPageResponse(BaseModel):
    document: StandardDocumentResponse
    page: int
    text: str
    citation: str


def _authenticate(authorization: Annotated[str | None, Header()] = None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            JWT_SECRET,
            algorithms=["HS256"],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc
    if payload.get("sub") != AUTH_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid session user.")


def _paths(document_id: str) -> tuple[Path, Path, Path]:
    directory = LIBRARY_ROOT / document_id
    return directory, directory / "metadata.json", directory / "index.json"


def _load_metadata(document_id: str) -> dict:
    _, metadata_path, _ = _paths(document_id)
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Standard document not found.")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _write_metadata(metadata: dict) -> None:
    _, metadata_path, _ = _paths(str(metadata["id"]))
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _load_pages(document_id: str) -> list[dict]:
    _, _, index_path = _paths(document_id)
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="This standard has no searchable text index.")
    try:
        value = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="The standards text index is unreadable.") from exc
    return value if isinstance(value, list) else []


def _normalise_metadata(metadata: dict) -> dict:
    value = dict(metadata)
    value.setdefault("extraction_method", "native" if value.get("indexed") else "none")
    value.setdefault("ocr_attempted", False)
    value.setdefault("ocr_error", None)
    value.setdefault("active", True)
    value.setdefault("archived_at", None)
    value.setdefault("supersedes_id", None)
    value.setdefault("superseded_by_id", None)
    value.setdefault("revision", 1)
    return value


def _response(metadata: dict) -> StandardDocumentResponse:
    return StandardDocumentResponse(**_normalise_metadata(metadata))


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip(" .")
    return cleaned[:180] or "standard.pdf"


def _snippet(text: str, query: str, radius: int = 150) -> str | None:
    lowered = text.lower()
    position = lowered.find(query.lower())
    if position < 0:
        terms = re.findall(r"[a-z0-9]+", query.lower())
        positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
        position = min(positions) if positions else -1
    if position < 0:
        return None
    start = max(0, position - radius)
    end = min(len(text), position + max(len(query), 1) + radius)
    excerpt = " ".join(text[start:end].split())
    return ("…" if start else "") + excerpt + ("…" if end < len(text) else "")


def _citation(metadata: dict, page: int) -> str:
    identity = str(metadata.get("reference") or metadata.get("title") or "Standard")
    edition = str(metadata.get("edition") or "").strip()
    authority = str(metadata.get("authority") or "").strip()
    revision = int(metadata.get("revision") or 1)
    parts = [identity]
    if edition:
        parts.append(edition)
    if revision > 1:
        parts.append(f"library rev. {revision}")
    if authority:
        parts.append(authority)
    return f"{' · '.join(parts)} · p. {page}"


async def _read_pdf(file: UploadFile) -> tuple[str, bytes]:
    filename = _safe_filename(file.filename or "standard.pdf")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF standards are supported in this release.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded standard exceeds the configured size limit.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF.")
    return filename, data


def _store_document(
    *,
    filename: str,
    data: bytes,
    title: str,
    authority: str,
    reference: str | None,
    edition: str | None,
    revision: int = 1,
    supersedes_id: str | None = None,
) -> dict:
    document_id = uuid.uuid4().hex
    directory, metadata_path, index_path = _paths(document_id)
    directory.mkdir(parents=True, exist_ok=False)
    pdf_path = directory / filename
    pdf_path.write_bytes(data)
    extraction = extract_standard_pages(pdf_path)
    index_path.write_text(json.dumps(extraction.pages, ensure_ascii=False), encoding="utf-8")
    metadata = {
        "id": document_id,
        "title": title.strip(),
        "authority": authority.strip(),
        "reference": reference.strip() if reference else None,
        "edition": edition.strip() if edition else None,
        "filename": filename,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "pages": len(extraction.pages),
        "indexed": extraction.indexed,
        "extraction_method": extraction.extraction_method,
        "ocr_attempted": extraction.ocr_attempted,
        "ocr_error": extraction.ocr_error,
        "active": True,
        "archived_at": None,
        "supersedes_id": supersedes_id,
        "superseded_by_id": None,
        "revision": revision,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


@router.get("", response_model=StandardSearchResponse)
async def search_standards(
    authorization: Annotated[str | None, Header()] = None,
    query: Annotated[str, Query(max_length=200)] = "",
    authority: Annotated[str | None, Query(max_length=120)] = None,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> StandardSearchResponse:
    _authenticate(authorization)
    LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    hits: list[StandardSearchHit] = []
    query_value = query.strip()
    authority_value = authority.strip().lower() if authority else None

    for metadata_path in sorted(LIBRARY_ROOT.glob("*/metadata.json")):
        try:
            metadata = _normalise_metadata(json.loads(metadata_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
        if not include_archived and not metadata["active"]:
            continue
        if authority_value and authority_value not in str(metadata.get("authority", "")).lower():
            continue
        document = _response(metadata)
        searchable_metadata = " ".join(str(metadata.get(key) or "") for key in ("title", "authority", "reference", "edition", "filename"))
        if not query_value:
            hits.append(StandardSearchHit(document=document))
        else:
            if query_value.lower() in searchable_metadata.lower():
                hits.append(StandardSearchHit(document=document, score=100))
            _, _, index_path = _paths(document.id)
            if index_path.exists():
                try:
                    pages = json.loads(index_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    pages = []
                remaining = max(0, min(5, limit - len(hits)))
                for ranked in rank_pages(pages, query_value, limit=remaining):
                    hits.append(StandardSearchHit(document=document, page=ranked.page or None, snippet=_snippet(ranked.text, query_value), score=ranked.score, citation=_citation(metadata, ranked.page)))
                    if len(hits) >= limit:
                        break
        if len(hits) >= limit:
            break
    hits.sort(key=lambda hit: -(hit.score or 0))
    return StandardSearchResponse(query=query_value, hits=hits[:limit])


@router.post("", response_model=StandardDocumentResponse, status_code=201)
async def upload_standard(
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=200)],
    authority: Annotated[str, Form(min_length=1, max_length=120)],
    reference: Annotated[str | None, Form(max_length=120)] = None,
    edition: Annotated[str | None, Form(max_length=120)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> StandardDocumentResponse:
    _authenticate(authorization)
    filename, data = await _read_pdf(file)
    return _response(_store_document(filename=filename, data=data, title=title, authority=authority, reference=reference, edition=edition))


@router.post("/{document_id}/replace", response_model=StandardDocumentResponse, status_code=201)
async def replace_standard(
    document_id: str,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=200)] = None,
    authority: Annotated[str | None, Form(max_length=120)] = None,
    reference: Annotated[str | None, Form(max_length=120)] = None,
    edition: Annotated[str | None, Form(max_length=120)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> StandardDocumentResponse:
    _authenticate(authorization)
    old = _normalise_metadata(_load_metadata(document_id))
    if not old["active"]:
        raise HTTPException(status_code=409, detail="Only the active revision can be replaced.")
    filename, data = await _read_pdf(file)
    new = _store_document(
        filename=filename,
        data=data,
        title=(title or old["title"]),
        authority=(authority or old["authority"]),
        reference=reference if reference is not None else old.get("reference"),
        edition=edition if edition is not None else old.get("edition"),
        revision=int(old.get("revision") or 1) + 1,
        supersedes_id=document_id,
    )
    old["active"] = False
    old["archived_at"] = datetime.now(timezone.utc).isoformat()
    old["superseded_by_id"] = new["id"]
    _write_metadata(old)
    return _response(new)


@router.delete("/{document_id}", response_model=StandardDocumentResponse)
async def archive_standard(document_id: str, authorization: Annotated[str | None, Header()] = None) -> StandardDocumentResponse:
    _authenticate(authorization)
    metadata = _normalise_metadata(_load_metadata(document_id))
    if metadata["active"]:
        metadata["active"] = False
        metadata["archived_at"] = datetime.now(timezone.utc).isoformat()
        _write_metadata(metadata)
    return _response(metadata)


@router.post("/{document_id}/restore", response_model=StandardDocumentResponse)
async def restore_standard(document_id: str, authorization: Annotated[str | None, Header()] = None) -> StandardDocumentResponse:
    _authenticate(authorization)
    metadata = _normalise_metadata(_load_metadata(document_id))
    if metadata.get("superseded_by_id"):
        raise HTTPException(status_code=409, detail="A superseded revision cannot be restored while a newer revision exists.")
    metadata["active"] = True
    metadata["archived_at"] = None
    _write_metadata(metadata)
    return _response(metadata)


@router.get("/{document_id}/pages/{page}", response_model=StandardPageResponse)
async def standard_page(document_id: str, page: int, authorization: Annotated[str | None, Header()] = None) -> StandardPageResponse:
    _authenticate(authorization)
    metadata = _normalise_metadata(_load_metadata(document_id))
    if page < 1 or page > int(metadata.get("pages") or 0):
        raise HTTPException(status_code=404, detail="Standard page not found.")
    pages = _load_pages(document_id)
    item = next((value for value in pages if int(value.get("page") or 0) == page), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Standard page text not found.")
    return StandardPageResponse(document=_response(metadata), page=page, text=str(item.get("text") or ""), citation=_citation(metadata, page))


@router.get("/{document_id}/file")
async def download_standard(document_id: str, authorization: Annotated[str | None, Header()] = None) -> FileResponse:
    _authenticate(authorization)
    metadata = _load_metadata(document_id)
    directory, _, _ = _paths(document_id)
    pdf_path = directory / metadata["filename"]
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Standard file not found.")
    return FileResponse(pdf_path, media_type="application/pdf", filename=metadata["filename"])
