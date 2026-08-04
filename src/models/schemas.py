from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    speaker: Optional[str] = Field(
        default=None,
        description="Speaker label (e.g. 'Speaker 1', 'Sarah'); None if unassigned or ambiguous.",
    )
    start_time: Optional[float] = Field(
        default=None,
        description="Start time in seconds from recording start.",
    )
    end_time: Optional[float] = Field(
        default=None,
        description="End time in seconds from recording start.",
    )
    text: str = Field(description="Transcribed spoken text segment.")


class Transcript(BaseModel):
    segments: List[TranscriptSegment] = Field(default_factory=list)
    full_text: str = Field(description="Flattened, concatenated transcript for easy display.")
    duration_seconds: Optional[float] = Field(default=None, description="Total audio duration in seconds.")


class ActionItem(BaseModel):
    id: str = Field(description="Unique action item identifier (e.g. 'A1', 'A2').")
    description: str = Field(description="Task or commitment description.")
    owner: Optional[str] = Field(
        default=None,
        description="Person assigned to the task if explicitly stated; None if unassigned.",
    )
    due_date: Optional[str] = Field(
        default=None,
        description="Explicitly mentioned deadline/date; None if no date was stated.",
    )
    status: str = Field(
        default="open",
        description="Action item status: 'open', 'in_progress', or 'completed'.",
    )
    source_excerpt: str = Field(
        description="Exact or near-exact quote/excerpt from transcript for grounding and auditability.",
    )


class Decision(BaseModel):
    id: str = Field(description="Unique decision identifier (e.g. 'D1', 'D2').")
    description: str = Field(description="Agreement, consensus, or decision made during the meeting.")
    source_excerpt: str = Field(
        description="Exact or near-exact quote/excerpt from transcript for grounding and auditability.",
    )


class SpeakerMap(BaseModel):
    mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of original speaker labels to custom names, e.g. {'Speaker 1': 'Sarah'}.",
    )


class MeetingAnalytics(BaseModel):
    talk_time_percentages: Dict[str, float] = Field(
        default_factory=dict,
        description="Percentage of total talk time per speaker.",
    )
    meeting_tone: str = Field(
        default="Productive",
        description="Overall meeting tone classification (e.g. 'Productive', 'Consensus-Heavy', 'Debated').",
    )
    participation_ratio: float = Field(
        default=1.0,
        description="Participation balance index (1.0 = balanced, <0.5 = dominated by one speaker).",
    )
    total_words: int = Field(default=0, description="Total word count in transcript.")


class RiskFlag(BaseModel):
    flag_type: str = Field(description="Risk category identifier (e.g. 'UNASSIGNED_TASK', 'NO_DUE_DATE').")
    severity: str = Field(description="Risk severity: 'LOW', 'MEDIUM', or 'HIGH'.")
    message: str = Field(description="Human-readable description of the risk.")
    action_item_id: Optional[str] = Field(
        default=None,
        description="Associated action item ID if flag is item-specific.",
    )


class RiskReport(BaseModel):
    overall_risk_level: str = Field(
        default="LOW",
        description="Aggregate risk level: 'LOW', 'MEDIUM', or 'HIGH'.",
    )
    risk_score: int = Field(default=0, description="Numeric risk score (0-100).")
    flags: List[RiskFlag] = Field(default_factory=list, description="Individual risk flags detected.")
    recommendations: List[str] = Field(
        default_factory=list,
        description="Actionable recommendations to mitigate identified risks.",
    )
    total_tasks: int = Field(default=0)
    unassigned_count: int = Field(default=0)
    no_due_date_count: int = Field(default=0)


class MeetingSummary(BaseModel):
    id: str = Field(description="Unique meeting summary identifier.")
    filename: str = Field(description="Original uploaded audio filename.")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        description="Timestamp of summary creation.",
    )
    transcript: Transcript = Field(description="Full timestamped and speaker-segmented transcript.")
    key_discussion_points: List[str] = Field(
        default_factory=list,
        description="Bullet points summarizing primary discussion topics.",
    )
    decisions: List[Decision] = Field(
        default_factory=list,
        description="Explicit decisions reached during the meeting.",
    )
    action_items: List[ActionItem] = Field(
        default_factory=list,
        description="Grounded action items extracted from the transcript.",
    )
    open_questions: List[str] = Field(
        default_factory=list,
        description="Unresolved questions or issues raised without a final consensus.",
    )
    email_draft: str = Field(description="Professional, ready-to-send follow-up email draft.")
    confidence_note: Optional[str] = Field(
        default=None,
        description="Warning or quality note if audio was degraded or extraction incomplete.",
    )
    speaker_map: Optional[SpeakerMap] = Field(default_factory=SpeakerMap)
    analytics: Optional[MeetingAnalytics] = Field(default=None)
    tags: List[str] = Field(default_factory=list, description="Categorization tags e.g. ['Sprint', 'Sales'].")
    output_language: str = Field(default="English", description="Target prose language.")
    email_tone: str = Field(default="action_oriented", description="Tone style of follow-up email.")
    meeting_title: Optional[str] = Field(
        default=None,
        description="AI-generated concise professional meeting title (5-8 words).",
    )
    risk_report: Optional[RiskReport] = Field(
        default=None,
        description="Meeting delivery risk analysis report.",
    )
