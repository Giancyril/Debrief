"""
sentiment_analyzer.py — Meeting Dynamics & Talk-Time Analytics

Computes per-speaker talk-time percentages, meeting tone classification,
and a participation balance index from a Transcript.
"""
from typing import Dict
from src.models.schemas import Transcript, MeetingAnalytics


def analyze_meeting_dynamics(transcript: Transcript) -> MeetingAnalytics:
    """
    Analyze a meeting transcript for talk-time distribution and meeting tone.

    Returns a MeetingAnalytics object with:
      - talk_time_percentages: dict of speaker -> % of words spoken
      - meeting_tone: 'Productive' | 'Consensus-Heavy' | 'Debated'
      - participation_ratio: 1.0 = balanced, < 0.5 = dominated
      - total_words: total word count in transcript
    """
    speaker_words: Dict[str, int] = {}
    total_words = 0

    for seg in transcript.segments:
        word_count = len(seg.text.split())
        total_words += word_count
        label = seg.speaker or "Unknown"
        speaker_words[label] = speaker_words.get(label, 0) + word_count

    if total_words == 0:
        return MeetingAnalytics(
            talk_time_percentages={},
            meeting_tone="Productive",
            participation_ratio=1.0,
            total_words=0,
        )

    # Compute percentages
    talk_pct = {
        speaker: round((words / total_words) * 100, 1)
        for speaker, words in speaker_words.items()
    }

    # Participation ratio: fraction of speakers contributing >= 15% talk time
    significant = sum(1 for pct in talk_pct.values() if pct >= 15)
    n_speakers = len(talk_pct)
    ratio = round(significant / n_speakers, 2) if n_speakers > 0 else 1.0

    # Simple heuristic tone classification
    if n_speakers <= 1:
        tone = "Monologue"
    elif ratio >= 0.7:
        tone = "Productive"
    elif ratio >= 0.4:
        tone = "Consensus-Heavy"
    else:
        tone = "Debated"

    return MeetingAnalytics(
        talk_time_percentages=talk_pct,
        meeting_tone=tone,
        participation_ratio=ratio,
        total_words=total_words,
    )
