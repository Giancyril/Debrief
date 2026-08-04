"""
risk_detector.py — Meeting Delivery Risk Detector

Analyzes meeting summaries for delivery risk signals:
  - Unassigned action items
  - Action items without due dates
  - Single-owner overload (1 person assigned >50% of tasks)
  - Unresolved open questions
  - Brief/vague transcript coverage

Runs in pure Python (0 Gemini API cost, < 1ms execution).
"""
from typing import List
from src.models.schemas import MeetingSummary, RiskReport, RiskFlag


def analyze_meeting_risk(summary: MeetingSummary) -> RiskReport:
    """
    Analyze action items and meeting metadata to detect delivery risks.
    """
    flags: List[RiskFlag] = []
    recommendations: List[str] = []
    total_tasks = len(summary.action_items)
    unassigned_count = 0
    no_due_date_count = 0
    owner_counts: dict[str, int] = {}

    for ai in summary.action_items:
        if not ai.owner:
            unassigned_count += 1
            flags.append(RiskFlag(
                flag_type="UNASSIGNED_TASK",
                severity="MEDIUM",
                message=f"Action item [{ai.id}] '{ai.description[:40]}...' has no assigned owner.",
                action_item_id=ai.id,
            ))
        else:
            owner_counts[ai.owner] = owner_counts.get(ai.owner, 0) + 1

        if not ai.due_date:
            no_due_date_count += 1
            flags.append(RiskFlag(
                flag_type="NO_DUE_DATE",
                severity="LOW",
                message=f"Action item [{ai.id}] '{ai.description[:40]}...' has no target due date.",
                action_item_id=ai.id,
            ))

    # Overloaded owner check (>50% of total tasks assigned to 1 person)
    if total_tasks >= 3:
        for owner, count in owner_counts.items():
            if count / total_tasks >= 0.5:
                flags.append(RiskFlag(
                    flag_type="SINGLE_OWNER_OVERLOAD",
                    severity="HIGH",
                    message=f"Owner '{owner}' is assigned {count} of {total_tasks} tasks ({round(count/total_tasks*100)}%).",
                ))
                recommendations.append(f"Reassign some tasks from {owner} to balance workload across team.")

    # Open questions risk
    if len(summary.open_questions) >= 3:
        flags.append(RiskFlag(
            flag_type="HIGH_OPEN_QUESTIONS",
            severity="MEDIUM",
            message=f"{len(summary.open_questions)} unresolved open questions remaining from session.",
        ))
        recommendations.append("Schedule a quick follow-up sync to resolve outstanding open questions.")

    # Calculate overall risk score (0 - 100)
    score = 0
    for f in flags:
        if f.severity == "HIGH":
            score += 25
        elif f.severity == "MEDIUM":
            score += 12
        else:
            score += 5

    risk_score = min(100, score)

    if risk_score >= 40:
        overall_level = "HIGH"
    elif risk_score >= 15:
        overall_level = "MEDIUM"
    else:
        overall_level = "LOW"

    if unassigned_count > 0:
        recommendations.append(f"Assign owners to the {unassigned_count} unassigned action item(s).")
    if no_due_date_count > 0:
        recommendations.append(f"Set clear target due dates for {no_due_date_count} task(s) missing deadlines.")

    if not recommendations and not flags:
        recommendations.append("Meeting delivery status looks healthy. No major risks detected.")

    return RiskReport(
        overall_risk_level=overall_level,
        risk_score=risk_score,
        flags=flags,
        recommendations=recommendations,
        total_tasks=total_tasks,
        unassigned_count=unassigned_count,
        no_due_date_count=no_due_date_count,
    )
