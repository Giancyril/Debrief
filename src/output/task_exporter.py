"""
task_exporter.py — Export action items to CSV, ICS iCalendar, and Markdown checklist.
"""
import csv
import io
import uuid
from datetime import datetime, timezone
from typing import List
from src.models.schemas import ActionItem


def export_to_csv(action_items: List[ActionItem]) -> str:
    """Export action items as a CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "description", "owner", "due_date", "status", "source_excerpt"],
        lineterminator="\n",
    )
    writer.writeheader()
    for ai in action_items:
        writer.writerow({
            "id": ai.id,
            "description": ai.description,
            "owner": ai.owner or "",
            "due_date": ai.due_date or "",
            "status": ai.status,
            "source_excerpt": ai.source_excerpt,
        })
    return output.getvalue()


def export_to_ics(action_items: List[ActionItem], meeting_filename: str = "Meeting") -> str:
    """Export action items as an ICS iCalendar file string."""
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Debrief AI//Meeting Summarizer//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for ai in action_items:
        uid = str(uuid.uuid4())
        due = ai.due_date or ""
        summary = ai.description.replace(",", "\\,").replace(";", "\\;")
        description = ai.source_excerpt.replace(",", "\\,").replace(";", "\\;")

        lines += [
            "BEGIN:VTODO",
            f"UID:{uid}",
            f"DTSTAMP:{now}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:From {meeting_filename}: {description}",
        ]
        if ai.owner:
            lines.append(f"ORGANIZER;CN={ai.owner}:mailto:unknown@debrief.app")
        if due:
            # Try to parse YYYY-MM-DD to YYYYMMDD
            due_clean = due.replace("-", "")[:8]
            if len(due_clean) == 8 and due_clean.isdigit():
                lines.append(f"DUE;VALUE=DATE:{due_clean}")
        lines.append(f"STATUS:{ai.status.upper()}")
        lines.append("END:VTODO")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def export_to_markdown_checklist(action_items: List[ActionItem], meeting_filename: str = "Meeting") -> str:
    """Export action items as a Markdown checklist."""
    lines = [f"# Action Items — {meeting_filename}", ""]
    for ai in action_items:
        check = "x" if ai.status == "completed" else " "
        owner_str = f" **({ai.owner})**" if ai.owner else " *(unassigned)*"
        due_str = f" — due {ai.due_date}" if ai.due_date else ""
        lines.append(f"- [{check}] [{ai.id}] {ai.description}{owner_str}{due_str}")
        lines.append(f"  > *Source:* \"{ai.source_excerpt}\"")
    return "\n".join(lines)
