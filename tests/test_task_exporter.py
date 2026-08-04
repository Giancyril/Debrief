import pytest
from src.models.schemas import ActionItem
from src.output.task_exporter import export_to_csv, export_to_ics, export_to_markdown_checklist

ITEMS = [
    ActionItem(id="A1", description="Write spec", owner="Alice", due_date="2026-08-15",
               status="open", source_excerpt="Alice will write the spec by Aug 15."),
    ActionItem(id="A2", description="Review design", owner=None, due_date=None,
               status="completed", source_excerpt="Team agreed to review design."),
]

def test_csv_has_header_and_rows():
    csv_str = export_to_csv(ITEMS)
    assert "id,description,owner" in csv_str
    assert "Write spec" in csv_str
    assert "Review design" in csv_str

def test_csv_empty_owner_shown_as_blank():
    csv_str = export_to_csv(ITEMS)
    lines = csv_str.strip().split("\n")
    # Row 2 has no owner
    assert lines[2].split(",")[2] == ""

def test_ics_contains_vtodo():
    ics = export_to_ics(ITEMS, "Sprint Sync")
    assert "BEGIN:VCALENDAR" in ics
    assert "BEGIN:VTODO" in ics
    assert "Write spec" in ics
    assert "END:VCALENDAR" in ics

def test_ics_has_due_date():
    ics = export_to_ics(ITEMS, "Sprint Sync")
    assert "DUE;VALUE=DATE:20260815" in ics

def test_markdown_contains_checkbox_items():
    md = export_to_markdown_checklist(ITEMS, "Sprint Sync")
    assert "- [ ] [A1] Write spec" in md
    assert "- [x] [A2] Review design" in md

def test_markdown_shows_unassigned():
    md = export_to_markdown_checklist(ITEMS)
    assert "*(unassigned)*" in md

def test_markdown_includes_source_quote():
    md = export_to_markdown_checklist(ITEMS)
    assert "Alice will write the spec" in md
