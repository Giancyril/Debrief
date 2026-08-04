import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from fastapi import HTTPException

from src.pipeline.audio_validator import (
    validate_audio_file,
    validate_audio_bytes,
    get_audio_mime_type,
    MIME_MAP,
)
from src.storage.file_manager import FileManager


ALLOWED = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".webm"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB for tests


# ---------------------------------------------------------------------------
# audio_validator tests
# ---------------------------------------------------------------------------

def _make_upload(filename: str, size: int = 1024) -> MagicMock:
    """Create a mock UploadFile."""
    mock = MagicMock()
    mock.filename = filename
    mock.size = size
    return mock


def test_valid_mp3_passes():
    validate_audio_file(_make_upload("meeting.mp3"), ALLOWED, MAX_SIZE)


def test_valid_wav_passes():
    validate_audio_file(_make_upload("standup.wav", size=2 * 1024 * 1024), ALLOWED, MAX_SIZE)


def test_unsupported_extension_raises():
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_file(_make_upload("video.mp4"), ALLOWED, MAX_SIZE)
    assert exc_info.value.status_code == 400
    assert "mp4" in exc_info.value.detail.lower() or "unsupported" in exc_info.value.detail.lower()


def test_missing_filename_raises():
    mock = MagicMock()
    mock.filename = None
    mock.size = 1024
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_file(mock, ALLOWED, MAX_SIZE)
    assert exc_info.value.status_code == 400


def test_empty_file_raises():
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_file(_make_upload("empty.mp3", size=0), ALLOWED, MAX_SIZE)
    assert exc_info.value.status_code == 400
    assert "empty" in exc_info.value.detail.lower()


def test_oversized_file_raises():
    oversized = MAX_SIZE + 1
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_file(_make_upload("huge.mp3", size=oversized), ALLOWED, MAX_SIZE)
    assert exc_info.value.status_code == 400
    assert "large" in exc_info.value.detail.lower() or "size" in exc_info.value.detail.lower()


def test_validate_bytes_empty_raises():
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_bytes(b"", "file.mp3", ALLOWED, MAX_SIZE)
    assert exc_info.value.status_code == 400


def test_validate_bytes_bad_extension_raises():
    with pytest.raises(HTTPException) as exc_info:
        validate_audio_bytes(b"data", "file.exe", ALLOWED, MAX_SIZE)
    assert exc_info.value.status_code == 400


def test_get_audio_mime_type_mp3():
    assert get_audio_mime_type("meeting.mp3") == "audio/mpeg"


def test_get_audio_mime_type_wav():
    assert get_audio_mime_type("recording.wav") == "audio/wav"


def test_get_audio_mime_type_unknown_defaults():
    mime = get_audio_mime_type("file.xyz")
    assert mime == "audio/mpeg"  # fallback


# ---------------------------------------------------------------------------
# FileManager tests
# ---------------------------------------------------------------------------

def test_file_manager_save_and_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        fm = FileManager(Path(tmpdir))
        audio_bytes = b"FAKE_AUDIO_BYTES"
        saved_path = fm.save(audio_bytes, "test_meeting.mp3")

        assert saved_path.exists()
        assert saved_path.read_bytes() == audio_bytes
        assert saved_path.suffix == ".mp3"

        fm.delete(saved_path)
        assert not saved_path.exists()


def test_file_manager_delete_nonexistent_does_not_raise():
    with tempfile.TemporaryDirectory() as tmpdir:
        fm = FileManager(Path(tmpdir))
        fm.delete(Path(tmpdir) / "nonexistent.mp3")  # Should not raise


def test_file_manager_unique_names():
    with tempfile.TemporaryDirectory() as tmpdir:
        fm = FileManager(Path(tmpdir))
        path1 = fm.save(b"audio1", "meeting.mp3")
        path2 = fm.save(b"audio2", "meeting.mp3")
        assert path1 != path2
        fm.delete(path1)
        fm.delete(path2)
