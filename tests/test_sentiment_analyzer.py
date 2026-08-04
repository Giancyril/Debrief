import pytest
from src.models.schemas import Transcript, TranscriptSegment
from src.output.sentiment_analyzer import analyze_meeting_dynamics


def test_analyze_empty_transcript():
    t = Transcript(segments=[], full_text="")
    res = analyze_meeting_dynamics(t)
    assert res.total_words == 0
    assert res.talk_time_percentages == {}


def test_analyze_balanced_conversation():
    t = Transcript(
        segments=[
            TranscriptSegment(speaker="Alice", text="Welcome everyone to the sprint planning session today."),
            TranscriptSegment(speaker="Bob", text="Thanks Alice. I am ready to review our active task backlog."),
        ],
        full_text="Alice: Welcome everyone to the sprint planning session today.\nBob: Thanks Alice. I am ready to review our active task backlog."
    )
    res = analyze_meeting_dynamics(t)
    assert res.total_words > 0
    assert "Alice" in res.talk_time_percentages
    assert "Bob" in res.talk_time_percentages
    assert res.meeting_tone == "Productive"


def test_analyze_monologue():
    t = Transcript(
        segments=[
            TranscriptSegment(speaker="Solo", text="This is a solo presentation explaining the Q3 financial report.")
        ],
        full_text="Solo: This is a solo presentation explaining the Q3 financial report."
    )
    res = analyze_meeting_dynamics(t)
    assert res.meeting_tone == "Monologue"
