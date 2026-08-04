import pytest
from src.models.schemas import TranscriptSegment
from src.pipeline.audio_player_utils import (
    compute_playback_markers,
    format_timestamp,
    estimate_duration,
)

SEGMENTS = [
    TranscriptSegment(speaker="Alice", start_time=0.0, end_time=5.5, text="Hello."),
    TranscriptSegment(speaker="Bob", start_time=5.6, end_time=12.0, text="Hi there."),
    TranscriptSegment(speaker=None, start_time=None, end_time=None, text="[inaudible]"),
]

def test_compute_playback_markers_only_timestamped():
    markers = compute_playback_markers(SEGMENTS)
    assert len(markers) == 2
    assert markers[0]["speaker"] == "Alice"
    assert markers[1]["start_time"] == 5.6

def test_compute_playback_markers_excludes_no_timestamp():
    markers = compute_playback_markers(SEGMENTS)
    texts = [m["text"] for m in markers]
    assert "[inaudible]" not in texts

def test_format_timestamp_basic():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(65) == "01:05"
    assert format_timestamp(3661) == "61:01"

def test_format_timestamp_negative_clamps_to_zero():
    assert format_timestamp(-5) == "00:00"

def test_estimate_duration_returns_last_end_time():
    duration = estimate_duration(SEGMENTS)
    assert duration == 12.0

def test_estimate_duration_all_none():
    no_time_segs = [TranscriptSegment(text="no timestamps")]
    assert estimate_duration(no_time_segs) is None
