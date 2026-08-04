"""
agenda_generator.py — Next Meeting Agenda Generator

Generates a structured agenda for the next meeting based on unresolved open questions
and pending action items from the current summary.
"""
from src.models.schemas import MeetingSummary


def generate_next_agenda(summary: MeetingSummary) -> str:
    """Generate a clean next meeting agenda markdown from unresolved items."""
    lines = [
        f"# Next Meeting Agenda — Follow-Up to {summary.filename}",
        f"> **Base Meeting ID:** {summary.id}  |  **Generated:** {summary.created_at}",
        "",
        "## 1. Review of Pending Action Items",
    ]

    pending = [ai for ai in summary.action_items if ai.status != "completed"]
    if pending:
        for ai in pending:
            owner = f" ({ai.owner})" if ai.owner else " (Unassigned)"
            due = f" — Due: {ai.due_date}" if ai.due_date else ""
            lines.append(f"- [ ] **[{ai.id}]** {ai.description}{owner}{due}")
    else:
        lines.append("_All action items from previous session were completed!_")

    lines += ["", "## 2. Unresolved Open Questions for Discussion"]
    if summary.open_questions:
        for q in summary.open_questions:
            lines.append(f"- [ ] {q}")
    else:
        lines.append("_No open questions carried over._")

    lines += [
        "",
        "## 3. New Topics & Project Updates",
        "- [ ] Open floor for team updates",
        "- [ ] Review upcoming milestones",
        "",
        "---",
        "_Generated automatically by Debrief AI Meeting Intelligence._",
    ]

    return "\n".join(lines)
