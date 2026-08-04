import logging
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FileManager:
    """
    Manages temporary audio file storage and cleanup.

    Files are saved to `upload_dir` with a UUID prefix to avoid collisions.
    They should be deleted immediately after pipeline processing completes
    (or on failure) to avoid accumulating audio on disk.
    """

    def __init__(self, upload_dir: Path):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, original_filename: str) -> Path:
        """
        Save uploaded audio bytes to a unique temporary path.

        Returns the path to the saved file.
        """
        suffix = Path(original_filename).suffix.lower()
        unique_name = f"{uuid.uuid4().hex}{suffix}"
        dest = self.upload_dir / unique_name
        dest.write_bytes(data)
        logger.info(f"Saved uploaded audio to: {dest} ({len(data) / 1024:.1f} KB)")
        return dest

    def delete(self, path: Path) -> None:
        """
        Delete a temporary audio file.  Logs a warning if deletion fails
        rather than raising, so pipeline errors don't cascade.
        """
        try:
            if path.exists():
                path.unlink()
                logger.info(f"Deleted temporary audio file: {path}")
        except Exception as exc:
            logger.warning(f"Failed to delete temporary file {path}: {exc}")

    def cleanup_old_files(self, max_age_hours: int = 6) -> int:
        """
        Delete all files in upload_dir older than `max_age_hours`.
        Returns the number of files deleted.
        """
        cutoff = time.time() - (max_age_hours * 3600)
        deleted = 0
        for f in self.upload_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                self.delete(f)
                deleted += 1
        if deleted:
            logger.info(f"Cleaned up {deleted} stale upload(s) older than {max_age_hours}h.")
        return deleted
