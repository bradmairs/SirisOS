from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.engineering_standards_ocr import extract_standard_pages
from app.services.engineering_standards_search import rank_pages
from app.services.json_cache import load_json
from app.secrets_config import jwt_secret

router = APIRouter(prefix="/api/v1/engineering/standards", tags=["engineering"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")

LIBRARY_ROOT = Path(os.getenv("SIRISOS_STANDARDS_PATH", "/app/data/standards"))
MAX_UPLOAD_BYTES = int(os.getenv("SIRISOS_STANDARDS_MAX_UPLOAD_MB", "100")) * 1024 * 1024


class StandardDocumentResponse(BaseModel):
    id: str
    title: str
    authority: str
    reference: str | None = None
    edition: str | None = None
    # 11.20: the topic it's filed under on the Standards screen (Hydrology and flooding, Drinking water, ...)
    category: str | None = None
    # 11.21: where it downloads from, for the weekly check for new versions (standards_updates.py)
    source: dict | None = None
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
            jwt_secret(),
            algorithms=["HS256"],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc
    if payload.get("sub") != AUTH_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid session user.")


_DOCUMENT_ID = re.compile(r"[0-9a-f]{32}")


def _paths(document_id: str) -> tuple[Path, Path, Path]:
    # 11.20: an id is the uuid4().hex it was stored under, nothing that could step outside the library.
    if not _DOCUMENT_ID.fullmatch(document_id or ""):
        raise HTTPException(status_code=404, detail="Standard document not found.")
    root = os.path.normpath(str(LIBRARY_ROOT))
    candidate = os.path.normpath(os.path.join(root, document_id))
    if not candidate.startswith(root + os.sep):
        raise HTTPException(status_code=404, detail="Standard document not found.")
    directory = Path(candidate)
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
        value = load_json(index_path)
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
    value.setdefault("category", None)
    value.setdefault("source", None)
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
    category: str | None = None,
    source: dict | None = None,
) -> dict:
    document_id = uuid.uuid4().hex
    directory, metadata_path, index_path = _paths(document_id)
    directory.mkdir(parents=True, exist_ok=False)
    try:
        pdf_path = directory / filename
        pdf_path.write_bytes(data)
        extraction = extract_standard_pages(pdf_path)
        # 11.20.1: some PDFs (maths in Australian Rainfall and Runoff) give text with broken characters (lone surrogates);
        # they become "?" rather than failing the upload.
        text = json.dumps(extraction.pages, ensure_ascii=False).encode("utf-8", "replace").decode("utf-8")
        index_path.write_text(text, encoding="utf-8")
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)  # never leave a half-stored standard behind
        raise
    metadata = {
        "id": document_id,
        "title": title.strip(),
        "authority": authority.strip(),
        "reference": reference.strip() if reference else None,
        "edition": edition.strip() if edition else None,
        "category": category.strip() if category and category.strip() else None,
        "source": source or None,
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
    # Disk reads and scoring run off the event loop so a search never stalls
    # hub tiles or a streaming chat reply.
    return await asyncio.to_thread(_search, query, authority, include_archived, limit)


def _search(query: str, authority: str | None, include_archived: bool, limit: int) -> StandardSearchResponse:
    LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    hits: list[StandardSearchHit] = []
    query_value = query.strip()
    authority_value = authority.strip().lower() if authority else None

    for metadata_path in sorted(LIBRARY_ROOT.glob("*/metadata.json")):
        try:
            metadata = _normalise_metadata(load_json(metadata_path))
        except (OSError, json.JSONDecodeError):
            continue
        if not include_archived and not metadata["active"]:
            continue
        if authority_value and authority_value not in str(metadata.get("authority", "")).lower():
            continue
        document = _response(metadata)
        searchable_metadata = " ".join(str(metadata.get(key) or "") for key in ("title", "authority", "reference", "edition", "category", "filename"))
        if not query_value:
            hits.append(StandardSearchHit(document=document))
        else:
            if query_value.lower() in searchable_metadata.lower():
                hits.append(StandardSearchHit(document=document, score=100))
            _, _, index_path = _paths(document.id)
            if index_path.exists():
                try:
                    pages = load_json(index_path)
                except (OSError, json.JSONDecodeError):
                    pages = []
                # 11.20.2: every standard is scored before the best are picked; stopping at `limit` hits ranked whichever
                # folders came first, so with 28 standards ARR could lose to a wetland manual on "critical storm duration".
                for ranked in rank_pages(pages, query_value, limit=min(5, limit)):
                    hits.append(StandardSearchHit(document=document, page=ranked.page or None, snippet=_snippet(ranked.text, query_value), score=ranked.score, citation=_citation(metadata, ranked.page)))
        if not query_value and len(hits) >= limit:  # a plain listing can stop; a search looks at everything
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
    category: Annotated[str | None, Form(max_length=80)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> StandardDocumentResponse:
    _authenticate(authorization)
    filename, data = await _read_pdf(file)
    # Text extraction (and OCR for scanned PDFs, up to minutes) runs in a
    # worker thread so the rest of SirisOS stays responsive meanwhile.
    stored = await asyncio.to_thread(
        _store_document, filename=filename, data=data, title=title, authority=authority, reference=reference, edition=edition, category=category
    )
    return _response(stored)


class StandardChange(BaseModel):
    """11.20: correct a standard's details or its topic without uploading it again."""
    title: str | None = Field(default=None, min_length=1, max_length=200)
    authority: str | None = Field(default=None, min_length=1, max_length=120)
    reference: str | None = Field(default=None, max_length=120)
    edition: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=80)
    # 11.21: where to check for new versions (see standards_updates.py); an empty url stops checking
    source_url: str | None = Field(default=None, max_length=500, pattern=r"^(https?://\S+)?$")
    source_page: str | None = Field(default=None, max_length=500, pattern=r"^(https?://\S+)?$")
    source_pattern: str | None = Field(default=None, max_length=200)


@router.get("/updates")
async def update_status(authorization: Annotated[str | None, Header()] = None) -> dict:
    """11.21: when the library was last checked for new versions, what changed, and what couldn't be checked."""
    _authenticate(authorization)
    from app.engineering import standards_updates

    doc = standards_updates.state()
    return {"last_run": doc.get("last_run"), "last": doc.get("last"), "events": doc["events"][:30],
            "running": standards_updates._running.locked(), "weekly_hour": standards_updates.check_hour()}


@router.post("/updates/check")
async def check_updates(authorization: Annotated[str | None, Header()] = None) -> dict:
    _authenticate(authorization)
    from app.engineering import standards_updates

    return {"started": standards_updates.start()}


@router.patch("/{document_id}", response_model=StandardDocumentResponse)
async def change_standard(document_id: str, body: StandardChange, authorization: Annotated[str | None, Header()] = None) -> StandardDocumentResponse:
    _authenticate(authorization)
    metadata = _normalise_metadata(_load_metadata(document_id))
    changes = body.model_dump(exclude_unset=True)
    source_changes = {k.removeprefix("source_"): changes.pop(k) for k in list(changes) if k.startswith("source_")}
    for key, value in changes.items():
        metadata[key] = (value.strip() or None) if isinstance(value, str) else value
    if source_changes:
        if "pattern" in source_changes and source_changes["pattern"]:
            try:
                re.compile(source_changes["pattern"])
            except re.error as exc:
                raise HTTPException(status_code=422, detail=f"That pattern isn't a valid regex: {exc}") from None
        source = dict(metadata.get("source") or {})
        if source_changes.get("url") is not None and source_changes["url"] != source.get("url"):
            source.pop("sha256", None)  # a different file to compare against
        source.update({k: (v.strip() or None) if isinstance(v, str) else v for k, v in source_changes.items()})
        metadata["source"] = source if source.get("url") else None
    _write_metadata(metadata)
    return _response(metadata)


@router.post("/{document_id}/replace", response_model=StandardDocumentResponse, status_code=201)
async def replace_standard(
    document_id: str,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=200)] = None,
    authority: Annotated[str | None, Form(max_length=120)] = None,
    reference: Annotated[str | None, Form(max_length=120)] = None,
    edition: Annotated[str | None, Form(max_length=120)] = None,
    category: Annotated[str | None, Form(max_length=80)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> StandardDocumentResponse:
    _authenticate(authorization)
    filename, data = await _read_pdf(file)
    new = await asyncio.to_thread(replace_document, document_id, filename=filename, data=data, title=title, authority=authority,
                                  reference=reference, edition=edition, category=category)
    return _response(new)


def replace_document(document_id: str, *, filename: str, data: bytes, title: str | None = None, authority: str | None = None,
                     reference: str | None = None, edition: str | None = None, category: str | None = None,
                     source: dict | None = None) -> dict:
    """A new revision of a standard (an upload, or a new version found by the weekly check, 11.21): the old one is
    kept, marked superseded, and the new one takes its details unless given others."""
    old = _normalise_metadata(_load_metadata(document_id))
    if not old["active"]:
        raise HTTPException(status_code=409, detail="Only the active revision can be replaced.")
    new = _store_document(
        filename=filename,
        data=data,
        title=(title or old["title"]),
        authority=(authority or old["authority"]),
        reference=reference if reference is not None else old.get("reference"),
        edition=edition if edition is not None else old.get("edition"),
        category=category if category is not None else old.get("category"),
        source=source if source is not None else old.get("source"),
        revision=int(old.get("revision") or 1) + 1,
        supersedes_id=document_id,
    )
    old["active"] = False
    old["archived_at"] = datetime.now(timezone.utc).isoformat()
    old["superseded_by_id"] = new["id"]
    _write_metadata(old)
    return new


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
