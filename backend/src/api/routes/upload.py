"""File upload API endpoints."""

import os
import re
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, UploadFile, HTTPException

router = APIRouter(tags=["upload"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
    "text/plain",
}
ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".txt"}

UPLOAD_DIR = Path(os.path.expanduser("~/.investment_report_agent/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_uploads: dict = {}


def _safe_filename(filename: str | None) -> str:
    raw = (filename or "upload").replace("\\", "/").split("/")[-1].strip()
    stem = Path(raw).stem
    suffix = Path(raw).suffix.lower()
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    if not safe_stem:
        safe_stem = "upload"
    return f"{safe_stem}{suffix}"


def _validate_file(filename: str, content_type: str, size: int):
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")
    if size > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large: {size} bytes. Max: {MAX_FILE_SIZE}")
    if content_type not in ALLOWED_MIMES and not filename.endswith(".csv"):
        raise HTTPException(400, f"Unsupported MIME type: {content_type}")


async def _read_limited_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large: > {MAX_FILE_SIZE} bytes")
    return content


@router.post("/upload", status_code=201)
async def upload_file(file: UploadFile):
    content = await _read_limited_upload(file)
    filename = _safe_filename(file.filename)
    _validate_file(filename, file.content_type or "", len(content))

    fid = str(uuid4())
    file_path = UPLOAD_DIR / f"{fid}_{filename}"
    file_path.write_bytes(content)

    _uploads[fid] = {
        "file_id": fid,
        "filename": filename,
        "size_bytes": len(content),
        "content_type": file.content_type,
        "file_path": str(file_path),
        "status": "ready",
    }
    return {"file_id": fid, "filename": file.filename, "status": "ready"}


@router.get("/upload/{file_id}/status")
async def upload_status(file_id: str):
    f = _uploads.get(file_id)
    if not f:
        raise HTTPException(404, "File not found")
    return {"file_id": file_id, "status": f["status"], "filename": f["filename"]}
