from unittest.mock import MagicMock

import pytest

from src.models.schemas import ActionItem, Decision
from src.pipeline.email_drafter import draft_follow_up_email, _build_email_prompt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_gemini(response: str) -> MagicMock:
    mock = MagicMock()
    mock.generate_text.return_value = response
    return mock


def _sample_extraction(
    action_items=None, decisions=None, key_points=None, open_questions=None
):
    return {
        "action_items": action_items or [],
        "decisions": decisions or [],
        "key_discussion_points": key_points or [],
        "open_questions": open_questions or [],
        "confidence_note": None,
    }


SAMPLE_AI = ActionItem(
    id="A1",
    description="Finalize the Q3 roadmap document.",
    owner="Alice",
    due_date="2026-08-15",
    source_excerpt="Alice agreed to finalize the roadmap by August 15th.",
)

SAMPLE_DECISION = Decision(
    id="D1",
    description="Approved the new pricing strategy.",
    source_excerpt="The team unanimously agreed to approve the new pricing strategy.",
)


# ---------------------------------------------------------------------------
# draft_follow_up_email tests
# ---------------------------------------------------------------------------

def test_draft_returns_string():
    gemini = _mock_gemini("[DRAFT — PLEASE REVIEW BEFORE SENDING]\n\nDear Team,\nThank you.")
    extraction = _sample_extraction(action_items=[SAMPLE_AI], decisions=[SAMPLE_DECISION])
    result = draft_follow_up_email(gemini, extraction)
    assert isinstance(result, str)
    assert len(result) > 0


def test_draft_contains_draft_label():
    gemini = _mock_gemini("Thank you for attending.")  # Gemini omits DRAFT label
    extraction = _sample_extraction(action_items=[SAMPLE_AI])
    result = draft_follow_up_email(gemini, extraction)
    assert "[DRAFT" in result.upper()


def test_draft_label_not_duplicated():
    """Gemini includes the label; we should not add it a second time."""
    full_draft = "[DRAFT — PLEASE REVIEW BEFORE SENDING]\n\nDear All,\nSee summary below."
    gemini = _mock_gemini(full_draft)
    extraction = _sample_extraction(action_items=[SAMPLE_AI])
    result = draft_follow_up_email(gemini, extraction)
    assert result.upper().count("[DRAFT") == 1


def test_draft_empty_extraction_returns_minimal_email():
    """Empty meeting data should produce a minimal draft without calling Gemini."""
    gemini = _mock_gemini("Should not be called.")
    extraction = _sample_extraction()  # All empty
    result = draft_follow_up_email(gemini, extraction)
    assert "[DRAFT" in result.upper()
    assert "no specific action items" in result.lower()
    gemini.generate_text.assert_not_called()


def test_draft_with_only_key_points_calls_gemini():
    gemini = _mock_gemini("[DRAFT — PLEASE REVIEW BEFORE SENDING]\n\nSummary email.")
    extraction = _sample_extraction(key_points=["Q3 planning", "Budget review"])
    result = draft_follow_up_email(gemini, extraction)
    gemini.generate_text.assert_called_once()


# ---------------------------------------------------------------------------
# _build_email_prompt unit tests
# ---------------------------------------------------------------------------

def test_build_prompt_includes_action_items():
    extraction = _sample_extraction(action_items=[SAMPLE_AI], key_points=["Planning"])
    prompt = _build_email_prompt(extraction)
    assert "Finalize the Q3 roadmap" in prompt
    assert "Alice" in prompt
    assert "2026-08-15" in prompt


def test_build_prompt_includes_decisions():
    extraction = _sample_extraction(decisions=[SAMPLE_DECISION])
    prompt = _build_email_prompt(extraction)
    assert "Approved the new pricing strategy" in prompt


def test_build_prompt_no_action_items_says_none():
    extraction = _sample_extraction(key_points=["General review"])
    prompt = _build_email_prompt(extraction)
    assert "None identified" in prompt


def test_build_prompt_includes_open_questions():
    extraction = _sample_extraction(
        key_points=["Budget"],
        open_questions=["Who approves the final budget?"]
    )
    prompt = _build_email_prompt(extraction)
    assert "Who approves the final budget?" in prompt


def test_build_prompt_action_item_no_owner_shows_tbd():
    ai_no_owner = ActionItem(
        id="A2",
        description="Review design mockups.",
        owner=None,
        due_date=None,
        source_excerpt="Team agreed to review mockups.",
    )
    extraction = _sample_extraction(action_items=[ai_no_owner])
    prompt = _build_email_prompt(extraction)
    assert "TBD" in prompt
