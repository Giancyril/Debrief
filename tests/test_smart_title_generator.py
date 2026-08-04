import pytest
from unittest.mock import MagicMock
from src.pipeline.smart_title_generator import generate_meeting_title, _clean_filename_title


def _mock_gemini(response: str) -> MagicMock:
    g = MagicMock()
    g.generate_text.return_value = response
    return g


def test_title_generated_from_discussion_points():
    gemini = _mock_gemini("Q3 Budget Review and Hiring Plan")
    title = generate_meeting_title(
        gemini,
        key_discussion_points=["Q3 budget allocation", "New headcount requests"],
        filename="budget_meeting.mp3",
    )
    assert title == "Q3 Budget Review and Hiring Plan"


def test_title_strips_quotes():
    gemini = _mock_gemini('"Sprint 5 Planning and Backlog Grooming"')
    title = generate_meeting_title(gemini, ["Sprint planning", "backlog"], filename="sprint.mp3")
    assert title == "Sprint 5 Planning and Backlog Grooming"


def test_fallback_to_cleaned_filename_on_empty_discussion_points():
    gemini = _mock_gemini("some title")
    title = generate_meeting_title(gemini, key_discussion_points=[], filename="sprint_review_q3.mp3")
    assert title == "Sprint Review Q3"


def test_fallback_on_gemini_exception():
    gemini = MagicMock()
    gemini.generate_text.side_effect = Exception("API error")
    title = generate_meeting_title(gemini, ["budget review"], filename="monthly_review.wav")
    assert title == "Monthly Review"


def test_clean_filename_title_strips_extension():
    assert _clean_filename_title("sprint_planning.mp3") == "Sprint Planning"


def test_clean_filename_title_handles_dashes():
    assert _clean_filename_title("all-hands-q4-2026.wav") == "All Hands Q4 2026"


def test_clean_filename_title_handles_no_extension():
    assert _clean_filename_title("standup") == "Standup"


def test_title_rejected_if_too_long():
    # Response with >12 words should fall back to filename
    gemini = _mock_gemini("This is a very long title that exceeds the maximum acceptable word limit for a title")
    title = generate_meeting_title(gemini, ["budget"], filename="budget.mp3")
    assert title == "Budget"
