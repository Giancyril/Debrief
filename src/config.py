import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self, check_keys: bool = True):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        self.max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
        self.inline_audio_threshold_mb = int(os.getenv("INLINE_AUDIO_THRESHOLD_MB", "20"))

        self.allowed_audio_extensions = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".webm"}
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", "uploads"))
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "output"))

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if check_keys and not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is missing or empty. "
                "Please set it in your .env file or environment."
            )
