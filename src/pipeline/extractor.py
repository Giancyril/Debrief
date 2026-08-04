"""
extractor.py — Stage 4: Structured Extraction

Sends the full transcript text to Gemini and extracts:
  - action_items (with mandatory source_excerpt; owner/due_date ONLY if explicit)
  - decisions     (with mandatory source_excerpt)
  - key_discussion_points
  - open_questions
  - confidence_note (if audio quality affected extraction)

CORE GROUNDING PRINCIPLE:
  Every action item and decision must include a source_excerpt that points to
  the exact/near-exact transcript excerpt where it was stated.
  Owner and due_date on ActionItem are ONLY populated if explicitly stated;
  they must NEVER be inferred or guessed.
  If no action items or decisions are found, empty lists are returned —
  this is a valid, honest output, not an error.
"""

import json
import logging
import re
import uuid
from typing import Any, Optional

from src.models.schemas import ActionItem, Decision, Transcript
from src.services.gemini_client import GeminiService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extraction prompt (this is the most important prompt in the pipeline)
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_INSTRUCTION = """
You are a precise meeting analyst. Your task is to extract structured information
from a meeting transcript.

CRITICAL GROUNDING RULES — YOU MUST FOLLOW THESE EXACTLY:

1. ACTION ITEMS:
   - Only extract tasks, commitments, or next steps that were EXPLICITLY stated
     or clearly agreed upon by participants in the transcript.
   - Do NOT infer, assume, or fabricate action items that were not actually stated.
   - For each action item, include a source_excerpt: copy the exact or near-exact
     phrase(s) from the transcript where this commitment was made.
   - owner: set ONLY if the transcript explicitly names who is responsible.
     If the owner is not explicitly stated, set to null. DO NOT GUESS.
   - due_date: set ONLY if an explicit date or deadline was mentioned (e.g.
     "by Friday", "before the end of the month"). If no date was stated, set to null.
     DO NOT DEFAULT TO TODAY OR ANY DATE. DO NOT GUESS.

2. DECISIONS:
   - Only extract decisions that were explicitly made or agreed upon by participants.
   - Include a source_excerpt for every decision.

3. OPEN QUESTIONS:
   - Things raised in the meeting that were not resolved or decided.

4. If the meeting had NO action items, return an empty array [].
   If the meeting had NO decisions, return an empty array [].
   Empty arrays are valid honest outputs. Fabrication is NOT acceptable.

OUTPUT FORMAT — output ONLY valid JSON, no markdown fences, no explanation:
{
  "action_items": [
    {
      "description": "Concise description of the task.",
      "owner": "Name" | null,
      "due_date": "YYYY-MM-DD or natural language like 'by Friday'" | null,
      "source_excerpt": "The exact or near-exact transcript quote where this was stated."
    }
  ],
  "decisions": [
    {
      "description": "What was decided.",
      "source_excerpt": "The exact or near-exact transcript quote confirming this decision."
    }
  ],
  "key_discussion_points": [
    "Brief bullet-point summary of a main topic discussed."
  ],
  "open_questions": [
    "An unresolved question or issue raised in the meeting."
  ],
  "confidence_note": "Optional. Note any concerns about transcript completeness or extraction quality. null if no issues."
}
""".strip()


def _make_extraction_prompt(transcript_text: str) -> str:
    return (
        f"Here is the full meeting transcript:\n\n"
        f"--- TRANSCRIPT START ---\n{transcript_text}\n--- TRANSCRIPT END ---\n\n"
        f"Extract the structured meeting data exactly as instructed."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_meeting_data(
    gemini: GeminiService,
    transcript: Transcript,
) -> dict[str, Any]:
    """
    Extract action items, decisions, key points, and open questions from
    a meeting Transcript.

    Returns a dict with keys:
      action_items, decisions, key_discussion_points, open_questions, confidence_note

    All action_items and decisions are Pydantic model instances.
    """
    if not transcript.full_text.strip():
        logger.warning("Empty transcript — skipping extraction.")
        return _empty_extraction()

    prompt = _make_extraction_prompt(transcript.full_text)

    raw = gemini.generate_text(
        prompt=prompt,
        system_instruction=EXTRACTION_SYSTEM_INSTRUCTION,
        temperature=0.1,
    )

    return _parse_extraction_response(raw)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_extraction_response(raw: str) -> dict[str, Any]:
    """Parse Gemini's JSON extraction response into typed objects."""
    cleaned = _strip_markdown_fences(raw.strip())

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Extractor received non-JSON from Gemini; attempting embedded extraction.")
        extracted = _extract_json_object(cleaned)
        if extracted is None:
            logger.error("Extraction failed to parse any JSON from Gemini response.")
            return _empty_extraction(
                confidence_note="Extraction output could not be parsed; returned empty results."
            )
        data = extracted

    action_items = _parse_action_items(data.get("action_items", []))
    decisions = _parse_decisions(data.get("decisions", []))
    key_points = [str(p) for p in data.get("key_discussion_points", []) if p]
    open_questions = [str(q) for q in data.get("open_questions", []) if q]
    confidence_note = data.get("confidence_note") or None

    logger.info(
        f"Extraction complete: {len(action_items)} action item(s), "
        f"{len(decisions)} decision(s), {len(key_points)} discussion point(s)."
    )

    return {
        "action_items": action_items,
        "decisions": decisions,
        "key_discussion_points": key_points,
        "open_questions": open_questions,
        "confidence_note": confidence_note,
    }


def _parse_action_items(raw_items: list) -> list[ActionItem]:
    items = []
    for i, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        description = str(item.get("description", "")).strip()
        source_excerpt = str(item.get("source_excerpt", "")).strip()
        if not description or not source_excerpt:
            logger.warning(f"Skipping action item {i+1}: missing description or source_excerpt.")
            continue
        items.append(ActionItem(
            id=f"A{i + 1}",
            description=description,
            owner=item.get("owner") or None,
            due_date=item.get("due_date") or None,
            source_excerpt=source_excerpt,
        ))
    return items


def _parse_decisions(raw_decisions: list) -> list[Decision]:
    decisions = []
    for i, d in enumerate(raw_decisions):
        if not isinstance(d, dict):
            continue
        description = str(d.get("description", "")).strip()
        source_excerpt = str(d.get("source_excerpt", "")).strip()
        if not description or not source_excerpt:
            logger.warning(f"Skipping decision {i+1}: missing description or source_excerpt.")
            continue
        decisions.append(Decision(
            id=f"D{i + 1}",
            description=description,
            source_excerpt=source_excerpt,
        ))
    return decisions


def _empty_extraction(confidence_note: Optional[str] = None) -> dict[str, Any]:
    return {
        "action_items": [],
        "decisions": [],
        "key_discussion_points": [],
        "open_questions": [],
        "confidence_note": confidence_note,
    }


def _strip_markdown_fences(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()


def _extract_json_object(text: str) -> Optional[dict]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None
