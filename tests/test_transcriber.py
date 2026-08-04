import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.schemas import Transcript, TranscriptSegment
from src.pipeline.transcriber import (
    transcribe_audio,
    _parse_transcript_response,
    _flatten_segments,
    _strip_markdown_fences,
    _extract_json_array,
    _safe_float,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_TRANSCRIPT_JSON = json.dumps([
    {"speaker": "Speaker 1", "start_time": 0.0, "end_time": 5.2, "text": "Good morning, everyone."},
    {"speaker": "Speaker 2", "start_time": 5.3, "end_time": 10.1, "text": "Thanks for joining the call."},
    {"speaker": "Speaker 1", "start_time": 10.2, "end_time": 18.5, "text": "Let's start with the Q3 roadmap."},
])

SAMPLE_WITH_INAUDIBLE = json.dumps([
    {"speaker": "Speaker 1", "start_time": 0.0, "end_time": 3.0, "text": "Let me share my screen."},
    {"speaker": None, "start_time": 3.1, "end_time": 7.0, "text": "[inaudible]"},
    {"speaker": "Speaker 2", "start_time": 7.1, "end_time": 12.0, "text": "Can you hear me now?"},
])


def _mock_gemini(response: str) -> MagicMock:
    """Return a mock GeminiService whose process_audio returns the given string."""
    mock = MagicMock()
    mock.process_audio.return_value = response
    return mock


# ---------------------------------------------------------------------------
# transcribe_audio tests (with mocked GeminiService)
# ---------------------------------------------------------------------------

def test_transcribe_audio_returns_transcript():
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(b"FAKE_AUDIO")
        audio_path = Path(f.name)

    try:
        gemini = _mock_gemini(SAMPLE_TRANSCRIPT_JSON)
        result = transcribe_audio(gemini, audio_path, "audio/mpeg")

        assert isinstance(result, Transcript)
        assert len(result.segments) == 3
        assert result.segments[0].speaker == "Speaker 1"
        assert result.segments[0].start_time == 0.0
        assert "Good morning" in result.full_text
    finally:
        audio_path.unlink(missing_ok=True)


def test_transcribe_audio_marks_inaudible():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"FAKE_AUDIO")
        audio_path = Path(f.name)

    try:
        gemini = _mock_gemini(SAMPLE_WITH_INAUDIBLE)
        result = transcribe_audio(gemini, audio_path, "audio/wav")
        texts = [seg.text for seg in result.segments]
        assert "[inaudible]" in texts
    finally:
        audio_path.unlink(missing_ok=True)


def test_transcribe_audio_null_speaker_segment():
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(b"FAKE_AUDIO")
        audio_path = Path(f.name)

    data = json.dumps([{"speaker": None, "start_time": None, "end_time": None, "text": "No one spoke."}])
    try:
        gemini = _mock_gemini(data)
        result = transcribe_audio(gemini, audio_path, "audio/mpeg")
        assert result.segments[0].speaker is None
    finally:
        audio_path.unlink(missing_ok=True)


def test_transcribe_audio_fallback_on_bad_json():
    """When Gemini returns prose instead of JSON, should still produce a Transcript."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(b"FAKE_AUDIO")
        audio_path = Path(f.name)

    try:
        gemini = _mock_gemini("Speaker 1 said: Hello. Speaker 2 replied: Hi there.")
        result = transcribe_audio(gemini, audio_path, "audio/mpeg")
        assert isinstance(result, Transcript)
        assert result.full_text != ""
    finally:
        audio_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# _parse_transcript_response unit tests
# ---------------------------------------------------------------------------

def test_parse_valid_json():
    segments, note = _parse_transcript_response(SAMPLE_TRANSCRIPT_JSON)
    assert len(segments) == 3
    assert segments[1].text == "Thanks for joining the call."
    assert note is None


def test_parse_strips_markdown_fences():
    fenced = f"```json\n{SAMPLE_TRANSCRIPT_JSON}\n```"
    segments, _ = _parse_transcript_response(fenced)
    assert len(segments) == 3


def test_parse_inaudible_returns_confidence_note():
    segments, note = _parse_transcript_response(SAMPLE_WITH_INAUDIBLE)
    assert note is not None
    assert "inaudible" in note.lower()


def test_parse_prose_fallback():
    segments, note = _parse_transcript_response("This is just a plain text transcript.")
    assert len(segments) == 1
    assert segments[0].speaker is None


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------

def test_flatten_segments_with_speakers():
    segs = [
        TranscriptSegment(speaker="Alice", text="Hello."),
        TranscriptSegment(speaker="Bob", text="Good morning."),
    ]
    result = _flatten_segments(segs)
    assert "Alice: Hello." in result
    assert "Bob: Good morning." in result


def test_flatten_segments_without_speakers():
    segs = [
        TranscriptSegment(speaker=None, text="Welcome."),
        TranscriptSegment(speaker=None, text="Let's begin."),
    ]
    result = _flatten_segments(segs)
    assert "Welcome." in result


def test_strip_markdown_fences():
    assert _strip_markdown_fences("```json\n[]\n```") == "[]"
    assert _strip_markdown_fences("```\n[]\n```") == "[]"
    assert _strip_markdown_fences("[]") == "[]"


def test_extract_json_array_embedded():
    text = 'Here is the result: [{"speaker": null, "text": "hi"}] end.'
    result = _extract_json_array(text)
    assert result is not None
    assert result[0]["text"] == "hi"


def test_extract_json_array_none_on_failure():
    assert _extract_json_array("no json here") is None


def test_safe_float_valid():
    assert _safe_float(5.3) == 5.3
    assert _safe_float("3.14") == 3.14


def test_safe_float_none():
    assert _safe_float(None) is None
    assert _safe_float("not-a-float") is None
