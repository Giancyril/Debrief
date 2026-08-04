import json
import logging
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse

from src.config import Config
from src.models.schemas import MeetingSummary, MeetingAnalytics, RiskReport
from src.pipeline.audio_validator import get_audio_mime_type, validate_audio_bytes
from src.storage.file_manager import FileManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["Meetings"])


def get_config() -> Config:
    return Config()


# ---------------------------------------------------------------------------
# GET /meetings/search
# ---------------------------------------------------------------------------

@router.get(
    "/search",
    summary="Search past meeting summaries by keyword.",
)
def search_meetings(
    q: str = Query(..., description="Search query string"),
    cfg: Config = Depends(get_config),
):
    """Perform keyword search across saved meeting summaries."""
    from src.storage.meeting_search import search_past_meetings
    return search_past_meetings(cfg.output_dir, q)


# ---------------------------------------------------------------------------
# POST /meetings/upload
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=MeetingSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Upload meeting audio and return a full meeting summary.",
)
async def upload_meeting(
    file: UploadFile = File(..., description="Meeting audio file."),
    output_language: str = Query(default="English", description="Target prose output language"),
    cfg: Config = Depends(get_config),
) -> MeetingSummary:
    try:
        audio_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        )

    filename = file.filename or "meeting_audio"

    validate_audio_bytes(
        data=audio_bytes,
        filename=filename,
        allowed_extensions=cfg.allowed_audio_extensions,
        max_size_bytes=cfg.max_upload_size_mb * 1024 * 1024,
    )

    fm = FileManager(cfg.upload_dir)
    audio_path = fm.save(audio_bytes, filename)

    try:
        mime_type = get_audio_mime_type(filename)

        from src.services.gemini_client import GeminiService
        from src.pipeline.transcriber import transcribe_audio
        from src.pipeline.extractor import extract_meeting_data
        from src.pipeline.email_drafter import draft_follow_up_email
        from src.output.sentiment_analyzer import analyze_meeting_dynamics
        import uuid

        gemini = GeminiService(
            api_key=cfg.gemini_api_key,
            model_name=cfg.gemini_model,
            inline_threshold_mb=cfg.inline_audio_threshold_mb,
        )

        transcript = transcribe_audio(gemini, audio_path, mime_type)
        extraction = extract_meeting_data(gemini, transcript)
        email_draft = draft_follow_up_email(gemini, extraction)
        analytics = analyze_meeting_dynamics(transcript)

        meeting_id = f"meet_{uuid.uuid4().hex[:8]}"

        from src.pipeline.smart_title_generator import generate_meeting_title
        meeting_title = generate_meeting_title(
            gemini,
            key_discussion_points=extraction.get("key_discussion_points", []),
            filename=filename,
        )

        summary = MeetingSummary(
            id=meeting_id,
            filename=filename,
            transcript=transcript,
            key_discussion_points=extraction.get("key_discussion_points", []),
            decisions=extraction.get("decisions", []),
            action_items=extraction.get("action_items", []),
            open_questions=extraction.get("open_questions", []),
            email_draft=email_draft,
            confidence_note=extraction.get("confidence_note"),
            analytics=analytics,
            output_language=output_language,
            meeting_title=meeting_title,
        )

        output_path = cfg.output_dir / f"{meeting_id}.json"
        output_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"Meeting summary saved: {output_path}")

        return summary

    finally:
        fm.delete(audio_path)


# ---------------------------------------------------------------------------
# POST /meetings/{meeting_id}/generate-title
# ---------------------------------------------------------------------------

@router.post(
    "/{meeting_id}/generate-title",
    response_model=dict,
    summary="(Re-)generate a professional AI meeting title for an existing summary.",
)
def generate_title(
    meeting_id: str,
    cfg: Config = Depends(get_config),
) -> dict:
    """Use Gemini to generate or refresh the meeting title from key discussion points."""
    from src.pipeline.smart_title_generator import generate_meeting_title
    from src.services.gemini_client import GeminiService

    safe_id = Path(meeting_id).name
    json_path = cfg.output_dir / f"{safe_id}.json"

    if not json_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{safe_id}' not found.")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    summary = MeetingSummary.model_validate(data)

    gemini = GeminiService(api_key=cfg.gemini_api_key, model_name=cfg.gemini_model)
    new_title = generate_meeting_title(gemini, summary.key_discussion_points, summary.filename)

    summary.meeting_title = new_title
    json_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")

    return {"meeting_id": meeting_id, "meeting_title": new_title}


# ---------------------------------------------------------------------------
# GET /meetings/{meeting_id}

# ---------------------------------------------------------------------------

@router.get(
    "/{meeting_id}",
    response_model=MeetingSummary,
    summary="Retrieve a previously processed meeting summary.",
)
def get_meeting(
    meeting_id: str,
    cfg: Config = Depends(get_config),
) -> MeetingSummary:
    safe_id = Path(meeting_id).name
    json_path = cfg.output_dir / f"{safe_id}.json"

    if not json_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting '{safe_id}' not found.",
        )

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return MeetingSummary.model_validate(data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load meeting summary: {exc}",
        )


# ---------------------------------------------------------------------------
# PATCH /meetings/{meeting_id}/speakers
# ---------------------------------------------------------------------------

@router.patch(
    "/{meeting_id}/speakers",
    response_model=MeetingSummary,
    summary="Rename speaker labels across a meeting transcript and action items.",
)
def update_speakers(
    meeting_id: str,
    mapping: dict[str, str],
    cfg: Config = Depends(get_config),
) -> MeetingSummary:
    from src.pipeline.speaker_manager import rename_speakers

    safe_id = Path(meeting_id).name
    json_path = cfg.output_dir / f"{safe_id}.json"

    if not json_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{safe_id}' not found.")

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        summary = MeetingSummary.model_validate(data)
        updated = rename_speakers(summary, mapping)
        json_path.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
        return updated
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ---------------------------------------------------------------------------
# PATCH /meetings/{meeting_id}/actions/{action_id}
# ---------------------------------------------------------------------------

@router.patch(
    "/{meeting_id}/actions/{action_id}",
    response_model=MeetingSummary,
    summary="Update the status of a specific action item.",
)
def update_action_item_status(
    meeting_id: str,
    action_id: str,
    status_body: dict,
    cfg: Config = Depends(get_config),
) -> MeetingSummary:
    from src.pipeline.action_status_manager import update_action_status

    safe_id = Path(meeting_id).name
    json_path = cfg.output_dir / f"{safe_id}.json"

    if not json_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{safe_id}' not found.")

    new_status = status_body.get("status", "open")
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        summary = MeetingSummary.model_validate(data)
        updated = update_action_status(summary, action_id, new_status)
        json_path.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
        return updated
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /meetings/{meeting_id}/analytics
# ---------------------------------------------------------------------------

@router.get(
    "/{meeting_id}/analytics",
    response_model=MeetingAnalytics,
    summary="Compute meeting speaker talk-time distribution and tone dynamics.",
)
def get_meeting_analytics(
    meeting_id: str,
    cfg: Config = Depends(get_config),
) -> MeetingAnalytics:
    from src.output.sentiment_analyzer import analyze_meeting_dynamics

    safe_id = Path(meeting_id).name
    json_path = cfg.output_dir / f"{safe_id}.json"

    if not json_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{safe_id}' not found.")

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        summary = MeetingSummary.model_validate(data)
        return analyze_meeting_dynamics(summary.transcript)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /meetings/{meeting_id}/risk-report
# ---------------------------------------------------------------------------

@router.get(
    "/{meeting_id}/risk-report",
    response_model=RiskReport,
    summary="Analyze meeting delivery risk signals and recommendations.",
)
def get_meeting_risk_report(
    meeting_id: str,
    cfg: Config = Depends(get_config),
) -> RiskReport:
    """Analyze action items and open questions to compute delivery risk score and recommendations."""
    from src.output.risk_detector import analyze_meeting_risk

    safe_id = Path(meeting_id).name
    json_path = cfg.output_dir / f"{safe_id}.json"

    if not json_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{safe_id}' not found.")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    summary = MeetingSummary.model_validate(data)
    return analyze_meeting_risk(summary)


# ---------------------------------------------------------------------------
# GET /meetings/{meeting_id}/brief

# ---------------------------------------------------------------------------

@router.get(
    "/{meeting_id}/brief",
    response_class=PlainTextResponse,
    summary="Generate a 1-page boardroom memo brief.",
)
def get_boardroom_brief(
    meeting_id: str,
    cfg: Config = Depends(get_config),
):
    from src.output.boardroom_brief import generate_boardroom_brief

    safe_id = Path(meeting_id).name
    json_path = cfg.output_dir / f"{safe_id}.json"

    if not json_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{safe_id}' not found.")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    summary = MeetingSummary.model_validate(data)
    brief = generate_boardroom_brief(summary)
    return PlainTextResponse(content=brief, media_type="text/plain")


# ---------------------------------------------------------------------------
# GET /meetings/{meeting_id}/next-agenda
# ---------------------------------------------------------------------------

@router.get(
    "/{meeting_id}/next-agenda",
    response_class=PlainTextResponse,
    summary="Generate next meeting agenda markdown from pending items.",
)
def get_next_agenda(
    meeting_id: str,
    cfg: Config = Depends(get_config),
):
    from src.output.agenda_generator import generate_next_agenda

    safe_id = Path(meeting_id).name
    json_path = cfg.output_dir / f"{safe_id}.json"

    if not json_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{safe_id}' not found.")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    summary = MeetingSummary.model_validate(data)
    agenda = generate_next_agenda(summary)
    return PlainTextResponse(content=agenda, media_type="text/markdown")


# ---------------------------------------------------------------------------
# GET /meetings/{meeting_id}/diff
# ---------------------------------------------------------------------------

@router.get(
    "/{meeting_id}/diff",
    summary="Compare current meeting with a previous meeting in a series.",
)
def get_meeting_diff(
    meeting_id: str,
    against: str = Query(..., description="Previous meeting ID to compare against"),
    cfg: Config = Depends(get_config),
):
    from src.output.meeting_diff import compare_meetings

    path_curr = cfg.output_dir / f"{Path(meeting_id).name}.json"
    path_prev = cfg.output_dir / f"{Path(against).name}.json"

    if not path_curr.exists() or not path_prev.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or both meeting IDs not found.")

    curr = MeetingSummary.model_validate(json.loads(path_curr.read_text(encoding="utf-8")))
    prev = MeetingSummary.model_validate(json.loads(path_prev.read_text(encoding="utf-8")))
    return compare_meetings(curr, prev)


# ---------------------------------------------------------------------------
# POST /meetings/{meeting_id}/re-draft-email
# ---------------------------------------------------------------------------

@router.post(
    "/{meeting_id}/re-draft-email",
    response_model=dict,
    summary="Re-draft follow-up email in a specific executive tone.",
)
def redraft_email(
    meeting_id: str,
    tone: str = Query(default="action_oriented", enum=["formal_boardroom", "concise_slack", "action_oriented"]),
    cfg: Config = Depends(get_config),
):
    from src.services.gemini_client import GeminiService
    from src.output.email_tone_drafter import redraft_email_tone

    safe_id = Path(meeting_id).name
    json_path = cfg.output_dir / f"{safe_id}.json"

    if not json_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{safe_id}' not found.")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    summary = MeetingSummary.model_validate(data)

    gemini = GeminiService(api_key=cfg.gemini_api_key, model_name=cfg.gemini_model)
    extraction = {
        "action_items": summary.action_items,
        "decisions": summary.decisions,
        "key_discussion_points": summary.key_discussion_points,
    }
    new_draft = redraft_email_tone(gemini, extraction, tone)
    summary.email_draft = new_draft
    summary.email_tone = tone
    json_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")

    return {"meeting_id": meeting_id, "tone": tone, "email_draft": new_draft}


# ---------------------------------------------------------------------------
# GET /meetings/{meeting_id}/tasks/export
# ---------------------------------------------------------------------------

@router.get(
    "/{meeting_id}/tasks/export",
    summary="Export action items as CSV, ICS iCalendar, or Markdown checklist.",
)
def export_tasks(
    meeting_id: str,
    format: str = Query(default="csv", enum=["csv", "ics", "markdown"]),
    cfg: Config = Depends(get_config),
):
    from src.output.task_exporter import export_to_csv, export_to_ics, export_to_markdown_checklist

    safe_id = Path(meeting_id).name
    json_path = cfg.output_dir / f"{safe_id}.json"

    if not json_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{safe_id}' not found.")

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        summary = MeetingSummary.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    if format == "csv":
        content = export_to_csv(summary.action_items)
        media_type = "text/csv"
    elif format == "ics":
        content = export_to_ics(summary.action_items, summary.filename)
        media_type = "text/calendar"
    else:
        content = export_to_markdown_checklist(summary.action_items, summary.filename)
        media_type = "text/markdown"

    return PlainTextResponse(content=content, media_type=media_type)


# ---------------------------------------------------------------------------
# GET /meetings/{meeting_id}/export
# ---------------------------------------------------------------------------

@router.get(
    "/{meeting_id}/export",
    response_model=dict,
    summary="Export a meeting summary as plain text or Markdown.",
)
def export_meeting(
    meeting_id: str,
    format: str = Query(default="markdown", enum=["markdown", "text"]),
    cfg: Config = Depends(get_config),
) -> dict:
    safe_id = Path(meeting_id).name
    json_path = cfg.output_dir / f"{safe_id}.json"

    if not json_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting '{safe_id}' not found.",
        )

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        summary = MeetingSummary.model_validate(data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load meeting summary: {exc}",
        )

    if format == "markdown":
        content = _to_markdown(summary)
    else:
        content = _to_plain_text(summary)

    return {"meeting_id": meeting_id, "format": format, "content": content}


def _to_markdown(s: MeetingSummary) -> str:
    lines = [
        f"# Meeting Summary: {s.filename}",
        f"> **Date:** {s.created_at}  |  **ID:** {s.id}",
        "",
        "## Transcript",
        s.transcript.full_text or "_No transcript available._",
        "",
    ]

    if s.key_discussion_points:
        lines += ["## Key Discussion Points", ""]
        for pt in s.key_discussion_points:
            lines.append(f"- {pt}")
        lines.append("")

    if s.decisions:
        lines += ["## Decisions Made", ""]
        for d in s.decisions:
            lines.append(f"- **{d.id}**: {d.description}")
            lines.append(f"  > *Source:* \"{d.source_excerpt}\"")
        lines.append("")

    if s.action_items:
        lines += ["## Action Items", ""]
        for ai in s.action_items:
            owner = f" — **Owner:** {ai.owner}" if ai.owner else ""
            due = f" | **Due:** {ai.due_date}" if ai.due_date else ""
            lines.append(f"- **{ai.id}**: {ai.description}{owner}{due}")
            lines.append(f"  > *Source:* \"{ai.source_excerpt}\"")
        lines.append("")

    if s.open_questions:
        lines += ["## Open Questions", ""]
        for q in s.open_questions:
            lines.append(f"- {q}")
        lines.append("")

    if s.confidence_note:
        lines += [f"> ⚠️ **Analyst Note:** {s.confidence_note}", ""]

    lines += ["## Follow-Up Email Draft", "", s.email_draft]
    return "\n".join(lines)


def _to_plain_text(s: MeetingSummary) -> str:
    lines = [
        f"MEETING SUMMARY: {s.filename}",
        f"Date: {s.created_at}  |  ID: {s.id}",
        "=" * 60,
        "",
        "TRANSCRIPT",
        "-" * 40,
        s.transcript.full_text or "(No transcript available.)",
        "",
    ]

    if s.key_discussion_points:
        lines += ["KEY DISCUSSION POINTS", "-" * 40]
        for pt in s.key_discussion_points:
            lines.append(f"  * {pt}")
        lines.append("")

    if s.decisions:
        lines += ["DECISIONS MADE", "-" * 40]
        for d in s.decisions:
            lines.append(f"  [{d.id}] {d.description}")
            lines.append(f"        Source: \"{d.source_excerpt}\"")
        lines.append("")

    if s.action_items:
        lines += ["ACTION ITEMS", "-" * 40]
        for ai in s.action_items:
            owner = f" [Owner: {ai.owner}]" if ai.owner else ""
            due = f" [Due: {ai.due_date}]" if ai.due_date else ""
            lines.append(f"  [{ai.id}] {ai.description}{owner}{due}")
            lines.append(f"        Source: \"{ai.source_excerpt}\"")
        lines.append("")

    if s.open_questions:
        lines += ["OPEN QUESTIONS", "-" * 40]
        for q in s.open_questions:
            lines.append(f"  ? {q}")
        lines.append("")

    if s.confidence_note:
        lines += [f"NOTE: {s.confidence_note}", ""]

    lines += ["FOLLOW-UP EMAIL DRAFT", "-" * 40, s.email_draft]
    return "\n".join(lines)
