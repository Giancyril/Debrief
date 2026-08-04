import mimetypes
from pathlib import Path
from fastapi import HTTPException, UploadFile, status


# Supported MIME types keyed by extension
MIME_MAP: dict[str, str] = {
    ".mp3":  "audio/mpeg",
    ".wav":  "audio/wav",
    ".m4a":  "audio/mp4",
    ".aac":  "audio/aac",
    ".flac": "audio/flac",
    ".ogg":  "audio/ogg",
    ".webm": "audio/webm",
}


def get_audio_mime_type(filename: str) -> str:
    """Return the MIME type for an audio file based on its extension."""
    suffix = Path(filename).suffix.lower()
    return MIME_MAP.get(suffix, "audio/mpeg")


def validate_audio_file(
    file: UploadFile,
    allowed_extensions: set[str],
    max_size_bytes: int,
) -> None:
    """
    Validate an uploaded audio file.

    Raises HTTPException (400) for:
      - Missing filename
      - Unsupported file extension
      - Empty file (0 bytes)
      - File exceeds max_size_bytes

    Parameters
    ----------
    file : UploadFile
        The incoming multipart file.
    allowed_extensions : set[str]
        Allowed extensions (e.g. {'.mp3', '.wav', '.m4a'}).
    max_size_bytes : int
        Maximum allowed file size in bytes.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file has no filename.",
        )

    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported audio format '{suffix}'. "
                f"Allowed formats: {', '.join(sorted(allowed_extensions))}."
            ),
        )

    # Check file size if content_length is provided by the client
    if file.size is not None:
        if file.size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes). Please upload a valid audio file.",
            )
        if file.size > max_size_bytes:
            max_mb = max_size_bytes / (1024 * 1024)
            actual_mb = file.size / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Uploaded file is too large ({actual_mb:.1f} MB). "
                    f"Maximum allowed size is {max_mb:.0f} MB."
                ),
            )


def validate_audio_bytes(
    data: bytes,
    filename: str,
    allowed_extensions: set[str],
    max_size_bytes: int,
) -> None:
    """
    Validate audio after reading bytes to disk (catches zero-byte and oversized cases
    that may not have had file.size available at upload time).
    """
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes). Please upload a valid audio file.",
        )

    if len(data) > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        actual_mb = len(data) / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Uploaded file is too large ({actual_mb:.1f} MB). "
                f"Maximum allowed size is {max_mb:.0f} MB."
            ),
        )

    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported audio format '{suffix}'. "
                f"Allowed formats: {', '.join(sorted(allowed_extensions))}."
            ),
        )
