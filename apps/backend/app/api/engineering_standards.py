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
from pypdf import PdfReader

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


def _load_pages(document_id: str) -> list[dict]:
    _, _, index_path = _paths(document_id)
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="This standard has no searchable text index.")
    try:
        value = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="The standards text index is unreadable.") from exc
    return value if isinstance(value, list) else []


def _response(metadata: dict) -> StandardDocumentResponse:
    return StandardDocumentResponse(**metadata)


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
    parts = [identity]
    if edition:
        parts.append(edition)
    if authority:
        parts.append(authority)
    return f"{' · '.join(parts)} · p. {page}"


@router.get("", response_model=StandardSearchResponse)
async def search_standards(
    authorization: Annotated[str | None, Header()] = None,
    query: Annotated[str, Query(max_length=200)] = "",
    authority: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> StandardSearchResponse:
    _authenticate(authorization)
    LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    hits: list[StandardSearchHit] = []
    query_value = query.strip()
    authority_value = authority.strip().lower() if authority else None

    for metadata_path in sorted(LIBRARY_ROOT.glob("*/metadata.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if authority_value and authority_value not in str(metadata.get("authority", "")).lower():
            continue
        document = _response(metadata)
        searchable_metadata = " ".join(
            str(metadata.get(key) or "")
            for key in ("title", "authority", "reference", "edition", "filename")
        )
        if not query_value:
            hits.append(StandardSearchHit(document=document))
        else:
            metadata_match = query_value.lower() in searchable_metadata.lower()
            if metadata_match:
                hits.append(StandardSearchHit(document=document, score=100))
            _, _, index_path = _paths(document.id)
            if index_path.exists():
                try:
                    pages = json.loads(index_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    pages = []
                remaining = max(0, min(5, limit - len(hits)))
                for ranked in rank_pages(pages, query_value, limit=remaining):
                    hits.append(
                        StandardSearchHit(
                            document=document,
                            page=ranked.page or None,
                            snippet=_snippet(ranked.text, query_value),
                            score=ranked.score,
                            citation=_citation(metadata, ranked.page),
                        )
                    )
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
    filename = _safe_filename(file.filename or "standard.pdf")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF standards are supported in this release.")

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded standard exceeds the configured size limit.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF.")

    document_id = uuid.uuid4().hex
    directory, metadata_path, index_path = _paths(document_id)
    directory.mkdir(parents=True, exist_ok=False)
    pdf_path = directory / filename
    pdf_path.write_bytes(data)

    pages: list[dict[str, object]] = []
    indexed = False
    try:
        reader = PdfReader(str(pdf_path))
        for number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"page": number, "text": text})
        index_path.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
        indexed = any(str(item["text"]).strip() for item in pages)
    except Exception:
        pages = []
        indexed = False

    metadata = {
        "id": document_id,
        "title": title.strip(),
        "authority": authority.strip(),
        "reference": reference.strip() if reference else None,
        "edition": edition.strip() if edition else None,
        "filename": filename,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "pages": len(pages),
        "indexed": indexed,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return _response(metadata)


@router.get("/{document_id}/pages/{page}", response_model=StandardPageResponse)
async def standard_page(
    document_id: str,
    page: int,
    authorization: Annotated[str | None, Header()] = None,
) -> StandardPageResponse:
    _authenticate(authorization)
    metadata = _load_metadata(document_id)
    if page < 1 or page > int(metadata.get("pages") or 0):
        raise HTTPException(status_code=404, detail="Standard page not found.")
    pages = _load_pages(document_id)
    item = next((value for value in pages if int(value.get("page") or 0) == page), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Standard page text not found.")
    return StandardPageResponse(
        document=_response(metadata),
        page=page,
        text=str(item.get("text") or ""),
        citation=_citation(metadata, page),
    )


@router.get("/{document_id}/file")
async def download_standard(
    document_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> FileResponse:
    _authenticate(authorization)
    metadata = _load_metadata(document_id)
    directory, _, _ = _paths(document_id)
    pdf_path = directory / metadata["filename"]
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Standard file not found.")
    return FileResponse(pdf_path, media_type="application/pdf", filename=metadata["filename"])
