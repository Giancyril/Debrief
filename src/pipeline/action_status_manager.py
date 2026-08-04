"""
action_status_manager.py — Update action item status within a saved meeting summary.
"""
import logging
from typing import Literal
from src.models.schemas import MeetingSummary

logger = logging.getLogger(__name__)

ActionStatus = Literal["open", "in_progress", "completed"]


def update_action_status(summary: MeetingSummary, action_id: str, new_status: ActionStatus) -> MeetingSummary:
    """Update the status of a specific action item within a MeetingSummary."""
    valid_statuses = {"open", "in_progress", "completed"}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of: {valid_statuses}")

    for ai in summary.action_items:
        if ai.id == action_id:
            old = ai.status
            ai.status = new_status
            logger.info(f"Action {action_id} status updated: {old} -> {new_status}")
            return summary

    raise KeyError(f"Action item '{action_id}' not found in meeting '{summary.id}'.")
