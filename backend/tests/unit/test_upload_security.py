import pytest
from fastapi import HTTPException

from api.routes.upload import MAX_FILE_SIZE, _read_limited_upload, _safe_filename, _validate_file


class FakeUpload:
    def __init__(self, content: bytes):
        self.content = content
        self.requested_size: int | None = None

    async def read(self, size: int = -1) -> bytes:
        self.requested_size = size
        if size == -1:
            return self.content
        return self.content[:size]


def test_safe_filename_strips_path_segments():
    assert _safe_filename("../../secret.csv") == "secret.csv"
    assert _safe_filename("..\\..\\secret.csv") == "secret.csv"


def test_safe_filename_replaces_unsafe_characters():
    assert _safe_filename("财报 2026?.csv") == "2026.csv"
    assert _safe_filename("###.txt") == "upload.txt"


def test_validate_file_rejects_disallowed_extension_after_sanitizing():
    filename = _safe_filename("../../shell.exe")

    with pytest.raises(HTTPException) as exc:
        _validate_file(filename, "application/octet-stream", 10)

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_read_limited_upload_caps_read_size():
    upload = FakeUpload(b"hello")

    content = await _read_limited_upload(upload)

    assert content == b"hello"
    assert upload.requested_size == MAX_FILE_SIZE + 1


@pytest.mark.asyncio
async def test_read_limited_upload_rejects_oversized_file():
    upload = FakeUpload(b"x" * (MAX_FILE_SIZE + 1))

    with pytest.raises(HTTPException) as exc:
        await _read_limited_upload(upload)

    assert exc.value.status_code == 400
