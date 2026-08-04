"""
meeting_diff.py — Meeting Series Diff Engine

Compares two meeting summaries to track progress across meeting series:
  - Resolved vs ongoing vs new action items
  - Cumulative decisions made
  - Unresolved open questions diff
"""
from typing import Dict, List
from src.models.schemas import MeetingSummary


def compare_meetings(current: MeetingSummary, previous: MeetingSummary) -> Dict:
    """
    Compare current meeting against a previous meeting in a series.

    Returns a dict with:
      - newly_added_action_items
      - resolved_previous_action_items
      - ongoing_action_items
      - new_decisions
      - carryover_open_questions
    """
    prev_tasks = {ai.description.lower().strip(): ai for ai in previous.action_items}
    curr_tasks = {ai.description.lower().strip(): ai for ai in current.action_items}

    newly_added = [ai for key, ai in curr_tasks.items() if key not in prev_tasks]
    ongoing = [ai for key, ai in curr_tasks.items() if key in prev_tasks]
    resolved = [ai for key, ai in prev_tasks.items() if key not in curr_tasks or ai.status == "completed"]

    prev_decisions = {d.description.lower().strip() for d in previous.decisions}
    new_decisions = [d for d in current.decisions if d.description.lower().strip() not in prev_decisions]

    prev_questions = set(previous.open_questions)
    carryover_questions = [q for q in current.open_questions if q in prev_questions]

    return {
        "current_meeting_id": current.id,
        "previous_meeting_id": previous.id,
        "newly_added_action_items": newly_added,
        "resolved_previous_action_items": resolved,
        "ongoing_action_items": ongoing,
        "new_decisions": new_decisions,
        "carryover_open_questions": carryover_questions,
    }
