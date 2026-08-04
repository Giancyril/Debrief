import os
import time
import logging
from pathlib import Path
from typing import Optional, Union, List, Dict, Any
from google import genai
from google.genai import types
from google.genai.errors import APIError

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", inline_threshold_mb: int = 20):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required to initialize GeminiService.")
        self.api_key = api_key
        self.model_name = model_name
        self.inline_threshold_bytes = inline_threshold_mb * 1024 * 1024
        self.client = genai.Client(api_key=self.api_key)

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_retries: int = 3,
        temperature: float = 0.2,
    ) -> str:
        """
        Generates text using Gemini model with retry mechanism.
        """
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction,
        )

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                if response.text:
                    return response.text
                raise ValueError("Gemini API returned an empty text response.")
            except APIError as err:
                logger.warning(f"Gemini API error (attempt {attempt}/{max_retries}): {err}")
                if attempt == max_retries:
                    raise err
                time.sleep(2 ** attempt)
            except Exception as exc:
                logger.error(f"Unexpected error in GeminiService (attempt {attempt}/{max_retries}): {exc}")
                if attempt == max_retries:
                    raise exc
                time.sleep(2 ** attempt)

        raise RuntimeError("Failed to generate content after max retries.")

    def process_audio(
        self,
        audio_path: Union[str, Path],
        prompt: str,
        mime_type: str = "audio/mp3",
        system_instruction: Optional[str] = None,
        max_retries: int = 3,
        temperature: float = 0.2,
    ) -> str:
        """
        Processes audio input using Gemini native audio understanding.
        Routes to inline bytes for files < inline_threshold_bytes,
        or Gemini Files API (client.files.upload) for larger files.
        Ensures remote file cleanup after processing.
        """
        file_path = Path(audio_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        file_size = file_path.stat().st_size
        logger.info(f"Processing audio '{file_path.name}' ({file_size / (1024*1024):.2f} MB)...")

        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction,
        )

        if file_size <= self.inline_threshold_bytes:
            # Inline audio upload
            logger.info(f"Audio size <= {self.inline_threshold_bytes // (1024*1024)}MB. Using inline bytes upload.")
            audio_bytes = file_path.read_bytes()
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            contents = [audio_part, prompt]

            for attempt in range(1, max_retries + 1):
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                        config=config,
                    )
                    if response.text:
                        return response.text
                    raise ValueError("Gemini API returned an empty text response for inline audio.")
                except APIError as err:
                    logger.warning(f"Gemini inline audio API error (attempt {attempt}/{max_retries}): {err}")
                    if attempt == max_retries:
                        raise err
                    time.sleep(2 ** attempt)
                except Exception as exc:
                    logger.error(f"Unexpected error processing inline audio (attempt {attempt}/{max_retries}): {exc}")
                    if attempt == max_retries:
                        raise exc
                    time.sleep(2 ** attempt)

            raise RuntimeError("Inline audio processing failed after max retries.")

        else:
            # Files API upload
            logger.info(f"Audio size > {self.inline_threshold_bytes // (1024*1024)}MB. Using Gemini Files API.")
            uploaded_file = None
            try:
                uploaded_file = self.client.files.upload(
                    file=file_path,
                    config=types.UploadFileConfig(mime_type=mime_type, display_name=file_path.name),
                )
                logger.info(f"Uploaded audio to Gemini Files API: {uploaded_file.name}")

                # Wait if file state is ACTIVE
                while uploaded_file.state and uploaded_file.state.name == "PROCESSING":
                    logger.info("Waiting for uploaded audio processing on Gemini Files API...")
                    time.sleep(3)
                    uploaded_file = self.client.files.get(name=uploaded_file.name)

                if uploaded_file.state and uploaded_file.state.name == "FAILED":
                    raise RuntimeError(f"Gemini Files API failed to process file '{file_path.name}'.")

                contents = [uploaded_file, prompt]

                for attempt in range(1, max_retries + 1):
                    try:
                        response = self.client.models.generate_content(
                            model=self.model_name,
                            contents=contents,
                            config=config,
                        )
                        if response.text:
                            return response.text
                        raise ValueError("Gemini API returned empty text response for Files API audio.")
                    except APIError as err:
                        logger.warning(f"Gemini Files API audio error (attempt {attempt}/{max_retries}): {err}")
                        if attempt == max_retries:
                            raise err
                        time.sleep(2 ** attempt)
                    except Exception as exc:
                        logger.error(f"Unexpected error in Files API audio (attempt {attempt}/{max_retries}): {exc}")
                        if attempt == max_retries:
                            raise exc
                        time.sleep(2 ** attempt)

                raise RuntimeError("Files API audio processing failed after max retries.")

            finally:
                if uploaded_file:
                    try:
                        self.client.files.delete(name=uploaded_file.name)
                        logger.info(f"Deleted remote Gemini Files API asset: {uploaded_file.name}")
                    except Exception as del_err:
                        logger.warning(f"Failed to delete remote Gemini file {uploaded_file.name}: {del_err}")
