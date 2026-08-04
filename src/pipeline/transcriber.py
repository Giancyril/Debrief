"""
transcriber.py — Stage 3: Audio Transcription

Sends audio to Gemini via GeminiService (inline or Files API depending on size),
prompts for a timestamped, speaker-segmented JSON transcript, and parses the
response into Transcript / TranscriptSegment Pydantic objects.

Gemini audio limits (as of 2025):
  - Inline audio bytes: up to ~20 MB (controlled by INLINE_AUDIO_THRESHOLD_MB)
  - Files API: up to 2 GB / 1 hour of audio
  - The GeminiService.process_audio() handles routing automatically.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from src.models.schemas import Transcript, TranscriptSegment
from src.services.gemini_client import GeminiService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Transcription prompt
# ---------------------------------------------------------------------------

TRANSCRIPTION_SYSTEM_INSTRUCTION = """
You are a precise meeting transcription engine.
Your task is to transcribe spoken audio recordings into structured, machine-readable JSON.

RULES:
- Output ONLY valid JSON, no markdown fences, no preamble, no explanation.
- Produce an array of segment objects with these fields:
    speaker    (string or null) — label as "Speaker 1", "Speaker 2", etc. only if you
                                  can clearly distinguish different voices.
                                  If a participant states their name (e.g. "Hi, this is Sarah"),
                                  use that name as the speaker label.
                                  Use null if speaker cannot be determined.
    start_time (float or null)  — seconds from the start of the recording.
    end_time   (float or null)  — seconds from the start of the recording.
    text       (string)         — the verbatim transcribed text for this segment.
- If audio quality is poor or a section is inaudible, represent it as a segment
  with text "[inaudible]" and speaker null — do not guess the content.
- Do NOT add commentary, summaries, or any text outside the JSON array.

OUTPUT FORMAT (strict):
[
  {
    "speaker": "Speaker 1" | "Sarah" | null,
    "start_time": 0.0 | null,
    "end_time": 5.2 | null,
    "text": "Verbatim spoken text here."
  },
  ...
]
""".strip()

TRANSCRIPTION_USER_PROMPT = """
Transcribe the attached audio recording into the JSON segment array format specified.
Label distinct speakers if discernible. Mark unclear sections as [inaudible].
""".strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe_audio(
    gemini: GeminiService,
    audio_path: Path,
    mime_type: str = "audio/mp3",
) -> Transcript:
    """
    Transcribe an audio file using Gemini's native audio understanding.

    Returns a Transcript with populated segments and full_text.
    """
    logger.info(f"Starting transcription for: {audio_path.name}")

    raw_response = gemini.process_audio(
        audio_path=audio_path,
        prompt=TRANSCRIPTION_USER_PROMPT,
        mime_type=mime_type,
        system_instruction=TRANSCRIPTION_SYSTEM_INSTRUCTION,
        temperature=0.1,  # Low temperature for deterministic transcription
    )

    segments, confidence_issue = _parse_transcript_response(raw_response)
    full_text = _flatten_segments(segments)

    logger.info(
        f"Transcription complete: {len(segments)} segment(s), "
        f"{len(full_text.split())} words."
    )

    return Transcript(
        segments=segments,
        full_text=full_text,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_transcript_response(raw: str) -> tuple[list[TranscriptSegment], Optional[str]]:
    """
    Parse Gemini's JSON transcript response into TranscriptSegment objects.

    Returns (segments, confidence_note_or_None).
    Falls back gracefully if the response isn't clean JSON.
    """
    cleaned = _strip_markdown_fences(raw.strip())

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Attempt extraction from raw response if JSON is embedded in prose
        logger.warning("Gemini did not return clean JSON; attempting embedded JSON extraction.")
        data = _extract_json_array(cleaned)
        if data is None:
            # Last-resort fallback: treat the entire response as a single segment
            logger.warning("Falling back to single-segment transcript from raw Gemini response.")
            return [TranscriptSegment(speaker=None, start_time=None, end_time=None, text=cleaned)], \
                   "Transcript structure could not be parsed into segments; displayed as raw text."

    if not isinstance(data, list):
        logger.warning("Gemini JSON transcript was not a list; wrapping in single segment.")
        return [TranscriptSegment(text=str(data))], None

    segments = []
    for item in data:
        if not isinstance(item, dict):
            continue
        segments.append(TranscriptSegment(
            speaker=item.get("speaker") or None,
            start_time=_safe_float(item.get("start_time")),
            end_time=_safe_float(item.get("end_time")),
            text=str(item.get("text", "")).strip(),
        ))

    confidence_note = None
    if any("[inaudible]" in seg.text for seg in segments):
        confidence_note = "Audio contained inaudible sections; some content may be incomplete."

    return segments, confidence_note


def _flatten_segments(segments: list[TranscriptSegment]) -> str:
    """Produce a flat, readable full_text from a list of segments."""
    parts = []
    for seg in segments:
        if seg.speaker:
            parts.append(f"{seg.speaker}: {seg.text}")
        else:
            parts.append(seg.text)
    return "\n".join(parts)


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` fences that Gemini sometimes adds despite instructions."""
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()


def _extract_json_array(text: str) -> Optional[list]:
    """Try to extract the first JSON array found in a string."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _safe_float(value) -> Optional[float]:
    """Convert value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
