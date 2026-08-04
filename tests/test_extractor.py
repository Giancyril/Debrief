import json
from unittest.mock import MagicMock

import pytest

from src.models.schemas import Transcript, TranscriptSegment, ActionItem, Decision
from src.pipeline.extractor import (
    extract_meeting_data,
    _parse_extraction_response,
    _parse_action_items,
    _parse_decisions,
    _empty_extraction,
    _strip_markdown_fences,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_gemini(response: str) -> MagicMock:
    mock = MagicMock()
    mock.generate_text.return_value = response
    return mock


def _make_transcript(text: str) -> Transcript:
    return Transcript(
        segments=[TranscriptSegment(text=text)],
        full_text=text,
    )


# ---------------------------------------------------------------------------
# Sample Gemini extraction responses
# ---------------------------------------------------------------------------

FULL_EXTRACTION = json.dumps({
    "action_items": [
        {
            "description": "Send the updated project spec to the team.",
            "owner": "Alice",
            "due_date": "2026-08-10",
            "source_excerpt": "Alice said she would send the updated spec by next Monday."
        },
        {
            "description": "Schedule a follow-up sync meeting.",
            "owner": None,
            "due_date": None,
            "source_excerpt": "The team agreed to schedule a follow-up sync next week."
        }
    ],
    "decisions": [
        {
            "description": "Approved the new design mockups.",
            "source_excerpt": "Everyone agreed to move forward with the new design mockups."
        }
    ],
    "key_discussion_points": [
        "Q3 roadmap review",
        "Design approval for new product page",
        "Staffing concerns"
    ],
    "open_questions": [
        "Who will own the mobile version of the design?",
        "Budget approval status unclear."
    ],
    "confidence_note": None
})

NO_ITEMS_EXTRACTION = json.dumps({
    "action_items": [],
    "decisions": [],
    "key_discussion_points": ["General team check-in", "Holiday schedule"],
    "open_questions": [],
    "confidence_note": None
})


# ---------------------------------------------------------------------------
# extract_meeting_data tests
# ---------------------------------------------------------------------------

def test_extract_returns_action_items_and_decisions():
    gemini = _mock_gemini(FULL_EXTRACTION)
    transcript = _make_transcript("Alice said she would send the updated spec by next Monday.")
    result = extract_meeting_data(gemini, transcript)

    assert len(result["action_items"]) == 2
    assert len(result["decisions"]) == 1
    assert result["action_items"][0].owner == "Alice"
    assert result["action_items"][0].due_date == "2026-08-10"


def test_extract_source_excerpts_are_populated():
    """Core grounding test: every action item and decision must have a source_excerpt."""
    gemini = _mock_gemini(FULL_EXTRACTION)
    transcript = _make_transcript("Meeting content here.")
    result = extract_meeting_data(gemini, transcript)

    for ai in result["action_items"]:
        assert ai.source_excerpt, f"ActionItem '{ai.id}' is missing source_excerpt!"
    for d in result["decisions"]:
        assert d.source_excerpt, f"Decision '{d.id}' is missing source_excerpt!"


def test_extract_no_action_items_returns_empty_list():
    """
    Grounding rule: a casual meeting with no clear action items must produce
    an empty list, never fabricated items.
    """
    gemini = _mock_gemini(NO_ITEMS_EXTRACTION)
    transcript = _make_transcript("We just had a general check-in. No decisions were made.")
    result = extract_meeting_data(gemini, transcript)

    assert result["action_items"] == []
    assert result["decisions"] == []
    assert len(result["key_discussion_points"]) == 2


def test_extract_empty_transcript_returns_empty():
    """Empty transcript must return empty extraction without calling Gemini."""
    gemini = _mock_gemini("")
    transcript = _make_transcript("")
    result = extract_meeting_data(gemini, transcript)

    assert result["action_items"] == []
    assert result["decisions"] == []
    gemini.generate_text.assert_not_called()


def test_extract_unowned_action_item_owner_is_none():
    """Action item without explicit owner must have owner=None."""
    gemini = _mock_gemini(FULL_EXTRACTION)
    transcript = _make_transcript("Meeting content here.")
    result = extract_meeting_data(gemini, transcript)

    # Second action item has no explicit owner in mock data
    assert result["action_items"][1].owner is None
    assert result["action_items"][1].due_date is None


def test_extract_handles_fenced_json():
    fenced = f"```json\n{FULL_EXTRACTION}\n```"
    gemini = _mock_gemini(fenced)
    transcript = _make_transcript("Meeting.")
    result = extract_meeting_data(gemini, transcript)
    assert len(result["action_items"]) == 2


def test_extract_bad_json_returns_empty_with_note():
    gemini = _mock_gemini("Sorry, I could not process this transcript.")
    transcript = _make_transcript("Some text.")
    result = extract_meeting_data(gemini, transcript)
    assert result["action_items"] == []
    assert result["confidence_note"] is not None


# ---------------------------------------------------------------------------
# _parse_action_items unit tests
# ---------------------------------------------------------------------------

def test_parse_action_items_skips_missing_source_excerpt():
    raw = [
        {"description": "Task without excerpt", "owner": None, "due_date": None, "source_excerpt": ""},
        {"description": "Valid task", "owner": "Bob", "due_date": None, "source_excerpt": "Bob will do it."},
    ]
    result = _parse_action_items(raw)
    assert len(result) == 1
    assert result[0].owner == "Bob"


def test_parse_action_items_ids_sequential():
    raw = [
        {"description": f"Task {i}", "source_excerpt": f"Source {i}"} for i in range(3)
    ]
    result = _parse_action_items(raw)
    ids = [ai.id for ai in result]
    assert ids == ["A1", "A2", "A3"]


# ---------------------------------------------------------------------------
# _parse_decisions unit tests
# ---------------------------------------------------------------------------

def test_parse_decisions_skips_missing_source_excerpt():
    raw = [
        {"description": "Decision with no source", "source_excerpt": ""},
        {"description": "Valid decision", "source_excerpt": "Agreed in the meeting."},
    ]
    result = _parse_decisions(raw)
    assert len(result) == 1
    assert result[0].description == "Valid decision"


# ---------------------------------------------------------------------------
# _strip_markdown_fences
# ---------------------------------------------------------------------------

def test_strip_fences_removes_json_code_block():
    assert _strip_markdown_fences("```json\n{}\n```") == "{}"


def test_strip_fences_noop_on_clean():
    assert _strip_markdown_fences("{}") == "{}"
