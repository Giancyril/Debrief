import pytest
from src.models.schemas import MeetingSummary, Transcript, ActionItem
from src.output.risk_detector import analyze_meeting_risk


def _make_summary(actions=None, open_questions=None):
    return MeetingSummary(
        id="m_risk",
        filename="sprint.mp3",
        transcript=Transcript(segments=[], full_text=""),
        action_items=actions or [],
        open_questions=open_questions or [],
        email_draft="Draft email",
    )


def test_clean_meeting_has_low_risk():
    actions = [
        ActionItem(id="A1", description="Deploy app", owner="Alice", due_date="2026-08-10", source_excerpt="Quote 1"),
        ActionItem(id="A2", description="Write docs", owner="Bob", due_date="2026-08-12", source_excerpt="Quote 2"),
    ]
    s = _make_summary(actions=actions)
    report = analyze_meeting_risk(s)
    assert report.overall_risk_level == "LOW"
    assert report.unassigned_count == 0
    assert report.no_due_date_count == 0


def test_unassigned_and_no_due_date_triggers_flags():
    actions = [
        ActionItem(id="A1", description="Unassigned item", owner=None, due_date=None, source_excerpt="Quote"),
    ]
    s = _make_summary(actions=actions)
    report = analyze_meeting_risk(s)
    assert report.unassigned_count == 1
    assert report.no_due_date_count == 1
    assert len(report.flags) == 2


def test_single_owner_overload_triggers_high_severity():
    actions = [
        ActionItem(id="A1", description="Task 1", owner="Alice", due_date="2026-08-10", source_excerpt="Q1"),
        ActionItem(id="A2", description="Task 2", owner="Alice", due_date="2026-08-10", source_excerpt="Q2"),
        ActionItem(id="A3", description="Task 3", owner="Alice", due_date="2026-08-10", source_excerpt="Q3"),
        ActionItem(id="A4", description="Task 4", owner="Bob", due_date="2026-08-10", source_excerpt="Q4"),
    ]
    s = _make_summary(actions=actions)
    report = analyze_meeting_risk(s)
    overload_flags = [f for f in report.flags if f.flag_type == "SINGLE_OWNER_OVERLOAD"]
    assert len(overload_flags) == 1
    assert overload_flags[0].severity == "HIGH"


def test_open_questions_risk():
    s = _make_summary(open_questions=["Q1?", "Q2?", "Q3?"])
    report = analyze_meeting_risk(s)
    q_flags = [f for f in report.flags if f.flag_type == "HIGH_OPEN_QUESTIONS"]
    assert len(q_flags) == 1
