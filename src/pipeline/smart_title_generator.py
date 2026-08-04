"""
smart_title_generator.py — AI-Powered Meeting Title Generator

Uses Google Gemini to generate a concise, professional 5-8 word meeting title
from the transcript's key discussion points and filename context.
"""
import logging
import re
from typing import Any
from src.services.gemini_client import GeminiService

logger = logging.getLogger(__name__)


def generate_meeting_title(
    gemini: GeminiService,
    key_discussion_points: list[str],
    filename: str,
) -> str:
    """
    Generate a sharp, professional 5-8 word meeting title from discussion points.

    Falls back to a cleaned filename if Gemini returns an unusable response.
    """
    if not key_discussion_points:
        return _clean_filename_title(filename)

    topics = "; ".join(key_discussion_points[:5])

    prompt = (
        "Generate a concise, professional meeting title in 5-8 words.\n"
        "The title should be specific, informative, and suitable for a meeting calendar invite.\n"
        "Do not use generic titles like 'Team Meeting' or 'Discussion'.\n"
        "Do not include quotes, punctuation at the end, or any prefix like 'Title:'.\n"
        "Return ONLY the title text.\n\n"
        f"Key topics discussed: {topics}\n"
        f"Original filename: {filename}"
    )

    try:
        raw = gemini.generate_text(prompt=prompt, temperature=0.3)
        title = raw.strip().strip('"').strip("'").strip()
        # Reject suspiciously long or empty responses
        if title and len(title.split()) <= 12:
            return title
    except Exception as exc:
        logger.warning(f"Title generation failed, using filename fallback: {exc}")

    return _clean_filename_title(filename)


def _clean_filename_title(filename: str) -> str:
    """Convert a filename like 'sprint_review_q3.mp3' to 'Sprint Review Q3'."""
    name = re.sub(r"\.[a-zA-Z0-9]+$", "", filename)  # strip extension
    name = re.sub(r"[_\-]+", " ", name)              # underscores/dashes to spaces
    name = re.sub(r"\s+", " ", name).strip()
    return name.title()
