"""File upload API endpoints."""

from uuid import uuid4
from fastapi import APIRouter, UploadFile, HTTPException

router = APIRouter(tags=["upload"])

_uploads: dict = {}


@router.post("/upload", status_code=201)
async def upload_file(file: UploadFile):
    fid = str(uuid4())
    content = await file.read()
    _uploads[fid] = {
        "file_id": fid,
        "filename": file.filename,
        "size_bytes": len(content),
        "content_type": file.content_type,
        "status": "uploaded",
    }
    return {"file_id": fid, "filename": file.filename, "status": "uploaded"}


@router.get("/upload/{file_id}/status")
async def upload_status(file_id: str):
    f = _uploads.get(file_id)
    if not f:
        raise HTTPException(404, "File not found")
    return {"file_id": file_id, "status": f["status"], "filename": f["filename"]}
