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


class StandardSearchResponse(BaseModel):
    query: str
    hits: list[StandardSearchHit]


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


def _response(metadata: dict) -> StandardDocumentResponse:
    return StandardDocumentResponse(**metadata)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip(" .")
    return cleaned[:180] or "standard.pdf"


def _snippet(text: str, query: str, radius: int = 150) -> str | None:
    lowered = text.lower()
    position = lowered.find(query.lower())
    if position < 0:
        return None
    start = max(0, position - radius)
    end = min(len(text), position + len(query) + radius)
    excerpt = " ".join(text[start:end].split())
    return ("…" if start else "") + excerpt + ("…" if end < len(text) else "")


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
        elif query_value.lower() in searchable_metadata.lower():
            hits.append(StandardSearchHit(document=document))
        else:
            _, _, index_path = _paths(document.id)
            if index_path.exists():
                try:
                    pages = json.loads(index_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    pages = []
                for item in pages:
                    text = str(item.get("text") or "")
                    excerpt = _snippet(text, query_value)
                    if excerpt:
                        hits.append(
                            StandardSearchHit(
                                document=document,
                                page=int(item.get("page") or 0) or None,
                                snippet=excerpt,
                            )
                        )
                        break
        if len(hits) >= limit:
            break
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
