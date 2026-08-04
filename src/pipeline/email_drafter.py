"""
email_drafter.py — Stage 5: Follow-Up Email Drafting

Synthesizes structured extraction (action items, decisions, key points)
into a professional, ready-to-send follow-up email draft.

This output is always labeled as a DRAFT. It must never be auto-sent.
The user reviews and sends manually.
"""

import logging
from typing import Any, Optional

from src.services.gemini_client import GeminiService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Email drafting prompt
# ---------------------------------------------------------------------------

EMAIL_SYSTEM_INSTRUCTION = """
You are a professional executive assistant. Your task is to write a clear,
well-structured follow-up email based on meeting notes provided to you.

RULES:
- Write a professional, concise follow-up email.
- Structure it with:
    1. A warm greeting/opening ("Thank you for joining today's meeting...")
    2. A brief 1-2 sentence summary of what the meeting covered.
    3. A "Decisions Made" section (bulleted, if any decisions exist).
    4. An "Action Items" section (bulleted, with owner and due date where available).
    5. An "Open Questions" section (bulleted, if any exist).
    6. A professional sign-off.
- Begin the email with the line: [DRAFT — PLEASE REVIEW BEFORE SENDING]
- Do NOT add any prefix, commentary, or metadata outside the email body.
- If there are no action items, say "No specific action items were identified."
- If there are no decisions, omit the Decisions section rather than saying "none."
- Keep the tone professional but approachable.
- Output only the email body text (no subject line needed, just the body).
""".strip()


def _build_email_prompt(extraction: dict[str, Any]) -> str:
    action_items = extraction.get("action_items", [])
    decisions = extraction.get("decisions", [])
    key_points = extraction.get("key_discussion_points", [])
    open_questions = extraction.get("open_questions", [])

    lines = ["Here are the structured meeting notes to turn into a follow-up email:\n"]

    if key_points:
        lines.append("KEY TOPICS DISCUSSED:")
        for pt in key_points:
            lines.append(f"  - {pt}")
        lines.append("")

    if decisions:
        lines.append("DECISIONS MADE:")
        for d in decisions:
            lines.append(f"  - {d.description}")
        lines.append("")

    if action_items:
        lines.append("ACTION ITEMS:")
        for ai in action_items:
            owner_str = f" (Owner: {ai.owner})" if ai.owner else " (Owner: TBD)"
            due_str = f" — Due: {ai.due_date}" if ai.due_date else ""
            lines.append(f"  - {ai.description}{owner_str}{due_str}")
        lines.append("")
    else:
        lines.append("ACTION ITEMS: None identified.\n")

    if open_questions:
        lines.append("OPEN QUESTIONS / UNRESOLVED ITEMS:")
        for q in open_questions:
            lines.append(f"  - {q}")
        lines.append("")

    lines.append("Please write a professional follow-up email based on the above.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def draft_follow_up_email(
    gemini: GeminiService,
    extraction: dict[str, Any],
) -> str:
    """
    Draft a professional follow-up email from structured meeting extraction.

    Returns a string containing the email body, always prefixed with
    [DRAFT — PLEASE REVIEW BEFORE SENDING].
    """
    if not any([
        extraction.get("action_items"),
        extraction.get("decisions"),
        extraction.get("key_discussion_points"),
    ]):
        logger.info("No meeting content found; returning minimal email draft.")
        return (
            "[DRAFT — PLEASE REVIEW BEFORE SENDING]\n\n"
            "Thank you for joining today's meeting.\n\n"
            "No specific action items or decisions were recorded for this session.\n\n"
            "Best regards"
        )

    prompt = _build_email_prompt(extraction)

    raw = gemini.generate_text(
        prompt=prompt,
        system_instruction=EMAIL_SYSTEM_INSTRUCTION,
        temperature=0.4,
    )

    draft = raw.strip()

    # Ensure the DRAFT label is present even if Gemini omits it
    if "[DRAFT" not in draft.upper():
        draft = "[DRAFT — PLEASE REVIEW BEFORE SENDING]\n\n" + draft

    logger.info("Follow-up email draft generated.")
    return draft
