import pytest
from src.models.schemas import MeetingSummary, Transcript, ActionItem
from src.pipeline.action_status_manager import update_action_status


def _make_summary():
    return MeetingSummary(
        id="meet_001",
        filename="standup.mp3",
        transcript=Transcript(segments=[], full_text=""),
        action_items=[
            ActionItem(id="A1", description="Write spec", status="open", source_excerpt="Alice: I will write the spec."),
            ActionItem(id="A2", description="Review design", status="open", source_excerpt="Bob: Review design next sprint."),
        ],
        email_draft="[DRAFT] Follow-up",
    )


def test_update_status_to_completed():
    summary = _make_summary()
    updated = update_action_status(summary, "A1", "completed")
    assert updated.action_items[0].status == "completed"


def test_update_status_to_in_progress():
    summary = _make_summary()
    updated = update_action_status(summary, "A2", "in_progress")
    assert updated.action_items[1].status == "in_progress"


def test_update_nonexistent_action_raises_key_error():
    summary = _make_summary()
    with pytest.raises(KeyError, match="not found"):
        update_action_status(summary, "A99", "completed")


def test_update_invalid_status_raises_value_error():
    summary = _make_summary()
    with pytest.raises(ValueError, match="Invalid status"):
        update_action_status(summary, "A1", "invalid_status")
