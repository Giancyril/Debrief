"""
email_tone_drafter.py — Executive Email Tone Synthesizer

Re-drafts follow-up emails in distinct executive styles:
  - formal_boardroom: Formal executive memo style
  - concise_slack: Brief Slack/Teams chat summary style
  - action_oriented: Task & deadline focused bulleted style
"""
import logging
from typing import Any
from src.services.gemini_client import GeminiService

logger = logging.getLogger(__name__)

TONE_INSTRUCTIONS = {
    "formal_boardroom": (
        "Write a formal executive boardroom follow-up email. Use professional corporate "
        "salutations, clear strategic overview, formal decisions list, and structured action items."
    ),
    "concise_slack": (
        "Write a concise, friendly chat digest suitable for Slack or Microsoft Teams. "
        "Use bullet points, bold names, and concise 1-sentence summaries. Keep it short."
    ),
    "action_oriented": (
        "Write an action-oriented, task-focused follow-up email. Lead immediately with "
        "Action Items (Owner & Due Date), followed by Agreed Decisions and Key Topics."
    ),
}


def redraft_email_tone(
    gemini: GeminiService,
    extraction: dict[str, Any],
    tone: str = "action_oriented",
) -> str:
    """Re-draft follow-up email in the requested executive tone style."""
    instruction = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["action_oriented"])
    
    action_items = extraction.get("action_items", [])
    decisions = extraction.get("decisions", [])
    key_points = extraction.get("key_discussion_points", [])

    prompt = (
        f"Style Directive: {instruction}\n\n"
        f"Meeting Key Points: {key_points}\n"
        f"Agreed Decisions: {[d.description for d in decisions]}\n"
        f"Action Items: {[(ai.description, ai.owner, ai.due_date) for ai in action_items]}\n\n"
        f"Draft the follow-up email body now. Prefix with [DRAFT — PLEASE REVIEW BEFORE SENDING]."
    )

    draft = gemini.generate_text(
        prompt=prompt,
        system_instruction="You are an executive assistant drafting follow-up emails.",
        temperature=0.3,
    )

    if "[DRAFT" not in draft.upper():
        draft = "[DRAFT — PLEASE REVIEW BEFORE SENDING]\n\n" + draft.strip()

    return draft.strip()
