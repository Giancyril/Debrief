import pytest
from src.config import Config
from src.models.schemas import (
    TranscriptSegment,
    Transcript,
    ActionItem,
    Decision,
    MeetingSummary,
)


# ---------------------------------------------------------------------------
# Config tests (offline — no API key checks)
# ---------------------------------------------------------------------------

def test_config_loads_defaults():
    cfg = Config(check_keys=False)
    assert cfg.gemini_model in ("gemini-2.5-flash", "gemini-2.0-flash")
    assert cfg.max_upload_size_mb > 0
    assert cfg.inline_audio_threshold_mb > 0
    assert ".mp3" in cfg.allowed_audio_extensions
    assert ".wav" in cfg.allowed_audio_extensions
    assert ".m4a" in cfg.allowed_audio_extensions


def test_config_raises_on_missing_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import importlib
    import src.config as config_mod
    import os
    os.environ.pop("GEMINI_API_KEY", None)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        Config(check_keys=True)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_transcript_segment_defaults():
    seg = TranscriptSegment(text="Hello, everyone.")
    assert seg.speaker is None
    assert seg.start_time is None
    assert seg.end_time is None
    assert seg.text == "Hello, everyone."


def test_transcript_full_text():
    t = Transcript(
        segments=[TranscriptSegment(text="Good morning."), TranscriptSegment(text="Let's begin.")],
        full_text="Good morning. Let's begin.",
    )
    assert "Good morning" in t.full_text


def test_action_item_owner_and_due_date_default_none():
    ai = ActionItem(
        id="A1",
        description="Send the report.",
        source_excerpt="Alice said she would send the report.",
    )
    assert ai.owner is None
    assert ai.due_date is None


def test_action_item_with_explicit_owner():
    ai = ActionItem(
        id="A2",
        description="Schedule a follow-up.",
        owner="Bob",
        due_date="2026-08-15",
        source_excerpt="Bob agreed to schedule a follow-up by August 15th.",
    )
    assert ai.owner == "Bob"
    assert ai.due_date == "2026-08-15"


def test_decision_requires_source_excerpt():
    d = Decision(
        id="D1",
        description="Adopted the new pricing model.",
        source_excerpt="The team unanimously agreed to adopt the new pricing model.",
    )
    assert d.source_excerpt != ""


def test_meeting_summary_empty_lists():
    ms = MeetingSummary(
        id="meet_001",
        filename="standup.mp3",
        transcript=Transcript(segments=[], full_text=""),
        email_draft="[DRAFT] Follow-up email here.",
    )
    assert ms.action_items == []
    assert ms.decisions == []
    assert ms.open_questions == []
    assert ms.confidence_note is None


def test_meeting_summary_with_items():
    ms = MeetingSummary(
        id="meet_002",
        filename="planning.wav",
        transcript=Transcript(
            segments=[TranscriptSegment(speaker="Speaker 1", start_time=0.0, text="Let's finalize the roadmap.")],
            full_text="Let's finalize the roadmap.",
        ),
        key_discussion_points=["Roadmap review", "Q3 targets"],
        decisions=[Decision(id="D1", description="Freeze scope for Q3.", source_excerpt="Agreed to freeze scope.")],
        action_items=[ActionItem(id="A1", description="Write spec.", owner="Alice", source_excerpt="Alice to write spec.")],
        open_questions=["Who reviews the design?"],
        email_draft="[DRAFT] Here is the meeting follow-up.",
        confidence_note="Audio quality was poor in the last 5 minutes.",
    )
    assert len(ms.decisions) == 1
    assert len(ms.action_items) == 1
    assert ms.action_items[0].owner == "Alice"
    assert ms.confidence_note is not None
