import pytest
from src.models.schemas import MeetingSummary, Transcript, TranscriptSegment, ActionItem
from src.pipeline.speaker_manager import rename_speakers


def _make_summary():
    return MeetingSummary(
        id="test_001",
        filename="meeting.mp3",
        transcript=Transcript(
            segments=[
                TranscriptSegment(speaker="Speaker 1", text="Hello team."),
                TranscriptSegment(speaker="Speaker 2", text="Hi everyone."),
            ],
            full_text="Speaker 1: Hello team.\nSpeaker 2: Hi everyone.",
        ),
        action_items=[
            ActionItem(id="A1", description="Draft spec", owner="Speaker 1", source_excerpt="Speaker 1: Hello team.")
        ],
        email_draft="[DRAFT] Follow up email",
    )


def test_rename_speakers_updates_transcript_and_action_item():
    summary = _make_summary()
    updated = rename_speakers(summary, {"Speaker 1": "Sarah Connor"})

    assert updated.transcript.segments[0].speaker == "Sarah Connor"
    assert "Sarah Connor: Hello team." in updated.transcript.full_text
    assert updated.action_items[0].owner == "Sarah Connor"
    assert updated.speaker_map.mapping["Speaker 1"] == "Sarah Connor"


def test_rename_speakers_empty_map_returns_unchanged():
    summary = _make_summary()
    updated = rename_speakers(summary, {})
    assert updated.transcript.segments[0].speaker == "Speaker 1"
