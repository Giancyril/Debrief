"""
audio_player_utils.py — Audio Segment Timestamp Calculator

Produces a list of playback markers from transcript segments so the frontend
audio player can highlight the currently-playing segment in real time.
"""
from typing import List, Optional
from dataclasses import dataclass
from src.models.schemas import TranscriptSegment


@dataclass
class PlaybackMarker:
    segment_index: int
    start_time: float
    end_time: float
    speaker: Optional[str]
    text: str


def compute_playback_markers(segments: List[TranscriptSegment]) -> List[dict]:
    """
    Generate a list of playback marker dicts for the frontend audio player.
    Only includes segments that have both start_time and end_time defined.
    """
    markers = []
    for i, seg in enumerate(segments):
        if seg.start_time is not None and seg.end_time is not None:
            markers.append({
                "segment_index": i,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "speaker": seg.speaker,
                "text": seg.text,
            })
    return markers


def format_timestamp(seconds: float) -> str:
    """Format seconds to MM:SS string."""
    total_seconds = max(0, int(seconds))
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def estimate_duration(segments: List[TranscriptSegment]) -> Optional[float]:
    """Estimate total audio duration from the last segment's end_time."""
    for seg in reversed(segments):
        if seg.end_time is not None:
            return seg.end_time
    return None
