import tempfile
import json
from pathlib import Path
import pytest
from src.models.schemas import MeetingSummary, Transcript, ActionItem, Decision
from src.output.meeting_diff import compare_meetings
from src.output.boardroom_brief import generate_boardroom_brief
from src.output.agenda_generator import generate_next_agenda
from src.storage.meeting_search import search_past_meetings


def _make_summary(id="m1", filename="sync.mp3", actions=None, decisions=None, questions=None):
    return MeetingSummary(
        id=id,
        filename=filename,
        transcript=Transcript(segments=[], full_text="Sarah discussed database migration strategy."),
        action_items=actions or [ActionItem(id="A1", description="Migrate DB", owner="Dave", source_excerpt="Dave to migrate.")],
        decisions=decisions or [Decision(id="D1", description="Adopt Postgres", source_excerpt="Agreed Postgres.")],
        open_questions=questions or ["Who tests staging?"],
        key_discussion_points=["Database planning"],
        email_draft="[DRAFT] Follow up email",
    )


def test_boardroom_brief_formatting():
    s = _make_summary()
    brief = generate_boardroom_brief(s)
    assert "EXECUTIVE BOARDROOM MEMORANDUM" in brief
    assert "sync.mp3" in brief
    assert "[DECISION D1] Adopt Postgres" in brief


def test_agenda_generator_formatting():
    s = _make_summary()
    agenda = generate_next_agenda(s)
    assert "# Next Meeting Agenda" in agenda
    assert "Who tests staging?" in agenda


def test_meeting_diff_comparison():
    s1 = _make_summary(id="m1", actions=[ActionItem(id="A1", description="Task 1", source_excerpt="Quote 1")])
    s2 = _make_summary(id="m2", actions=[
        ActionItem(id="A1", description="Task 1", source_excerpt="Quote 1"),
        ActionItem(id="A2", description="Task 2", source_excerpt="Quote 2"),
    ])
    diff = compare_meetings(s2, s1)
    assert len(diff["newly_added_action_items"]) == 1
    assert diff["newly_added_action_items"][0].id == "A2"


def test_meeting_search_finds_query():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        summary = _make_summary(id="search_001", filename="postgres_migration.mp3")
        json_file = tmp_path / "search_001.json"
        json_file.write_text(summary.model_dump_json(), encoding="utf-8")

        results = search_past_meetings(tmp_path, "postgres")
        assert len(results) == 1
        assert results[0]["id"] == "search_001"
