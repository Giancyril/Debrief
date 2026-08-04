"""
boardroom_brief.py — Executive 1-Page Boardroom Brief Generator

Formats meeting summary into a condensed 1-page boardroom memo suitable for
C-level executive distribution and printing.
"""
from src.models.schemas import MeetingSummary


def generate_boardroom_brief(summary: MeetingSummary) -> str:
    """Generate a clean, 1-page executive boardroom memo from a MeetingSummary."""
    lines = [
        "================================================================================",
        "                       EXECUTIVE BOARDROOM MEMORANDUM                          ",
        "================================================================================",
        f"DATE:       {summary.created_at}",
        f"MEETING:    {summary.filename}",
        f"SUMMARY ID: {summary.id}",
        "--------------------------------------------------------------------------------",
        "",
        "EXECUTIVE SUMMARY & KEY TOPICS",
    ]

    for pt in summary.key_discussion_points:
        lines.append(f"  • {pt}")
    if not summary.key_discussion_points:
        lines.append("  (No key discussion points recorded)")

    lines += ["", "DECISIONS CONFIRMED"]
    for d in summary.decisions:
        lines.append(f"  [DECISION {d.id}] {d.description}")
        lines.append(f"    Source Quote: \"{d.source_excerpt}\"")
    if not summary.decisions:
        lines.append("  (No explicit decisions confirmed in this session)")

    lines += ["", "ACTION ITEMS & TASK ASSIGNMENTS"]
    for ai in summary.action_items:
        owner = ai.owner or "Unassigned"
        due = f" | Due: {ai.due_date}" if ai.due_date else ""
        lines.append(f"  [TASK {ai.id}] {ai.description} (Assignee: {owner}{due})")
    if not summary.action_items:
        lines.append("  (No action items assigned)")

    if summary.open_questions:
        lines += ["", "UNRESOLVED OPEN ISSUES"]
        for q in summary.open_questions:
            lines.append(f"  ? {q}")

    lines += [
        "",
        "================================================================================",
        "             CONFIDENTIAL — FOR INTERNAL EXECUTIVE REVIEW ONLY                ",
        "================================================================================",
    ]

    return "\n".join(lines)
