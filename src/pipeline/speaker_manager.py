import logging
from typing import Dict
from src.models.schemas import MeetingSummary, SpeakerMap

logger = logging.getLogger(__name__)


def rename_speakers(summary: MeetingSummary, mapping: Dict[str, str]) -> MeetingSummary:
    """
    Rename speaker labels across a MeetingSummary transcript, action item owners,
    and update speaker_map.
    """
    if not mapping:
        return summary

    # Clean mapping
    clean_map = {k.strip(): v.strip() for k, v in mapping.items() if k.strip() and v.strip()}
    if not clean_map:
        return summary

    # Update transcript segments
    for seg in summary.transcript.segments:
        if seg.speaker and seg.speaker in clean_map:
            seg.speaker = clean_map[seg.speaker]

    # Re-flatten full text
    parts = []
    for seg in summary.transcript.segments:
        if seg.speaker:
            parts.append(f"{seg.speaker}: {seg.text}")
        else:
            parts.append(seg.text)
    summary.transcript.full_text = "\n".join(parts)

    # Update action item owners if matching old speaker names
    for ai in summary.action_items:
        if ai.owner and ai.owner in clean_map:
            ai.owner = clean_map[ai.owner]

    # Update stored speaker_map
    if summary.speaker_map is None:
        summary.speaker_map = SpeakerMap(mapping=clean_map)
    else:
        summary.speaker_map.mapping.update(clean_map)

    logger.info(f"Renamed speakers in summary {summary.id}: {clean_map}")
    return summary
