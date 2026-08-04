import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from src.config import Config
from src.models.schemas import MeetingSummary
from src.pipeline.audio_validator import get_audio_mime_type, validate_audio_bytes
from src.storage.file_manager import FileManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["Meetings"])

# ---------------------------------------------------------------------------
# Dependency: shared Config instance
# ---------------------------------------------------------------------------

def get_config() -> Config:
    return Config()


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
    file: UploadFile = File(..., description="Meeting audio file (MP3, WAV, M4A, AAC, FLAC, OGG, WebM)."),
    cfg: Config = Depends(get_config),
) -> MeetingSummary:
    """
    Upload a meeting audio file.

    Pipeline:
    1. Read & validate audio bytes.
    2. Save to temporary storage.
    3. Run full pipeline: transcribe → extract → draft email.
    4. Persist summary JSON to `output/`.
    5. Delete temporary audio.
    6. Return MeetingSummary.
    """
    # --- Read bytes ---
    try:
        audio_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        )

    filename = file.filename or "meeting_audio"

    # --- Validate ---
    validate_audio_bytes(
        data=audio_bytes,
        filename=filename,
        allowed_extensions=cfg.allowed_audio_extensions,
        max_size_bytes=cfg.max_upload_size_mb * 1024 * 1024,
    )

    # --- Save temporarily ---
    fm = FileManager(cfg.upload_dir)
    audio_path = fm.save(audio_bytes, filename)

    try:
        mime_type = get_audio_mime_type(filename)

        # --- Pipeline ---
        from src.services.gemini_client import GeminiService
        from src.pipeline.transcriber import transcribe_audio
        from src.pipeline.extractor import extract_meeting_data
        from src.pipeline.email_drafter import draft_follow_up_email
        import uuid
        from datetime import datetime, timezone

        gemini = GeminiService(
            api_key=cfg.gemini_api_key,
            model_name=cfg.gemini_model,
            inline_threshold_mb=cfg.inline_audio_threshold_mb,
        )

        # Stage 3: Transcription
        transcript = transcribe_audio(gemini, audio_path, mime_type)

        # Stage 4: Extraction
        extraction = extract_meeting_data(gemini, transcript)

        # Stage 5: Email draft
        email_draft = draft_follow_up_email(gemini, extraction)

        # Build summary
        meeting_id = f"meet_{uuid.uuid4().hex[:8]}"
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
        )

        # Persist JSON
        output_path = cfg.output_dir / f"{meeting_id}.json"
        output_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"Meeting summary saved: {output_path}")

        return summary

    finally:
        fm.delete(audio_path)


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
    """Fetch a saved meeting summary by its ID."""
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
    """
    Rename speaker labels across transcript segments, action item owners, and store mapping.
    """
    from src.pipeline.speaker_manager import rename_speakers

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
        updated = rename_speakers(summary, mapping)
        json_path.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
        return updated
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update speakers: {exc}",
        )



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
    """Update action item status: 'open', 'in_progress', or 'completed'."""
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
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


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
    """Export action items from a meeting summary as CSV, ICS, or Markdown checklist."""
    from src.output.task_exporter import export_to_csv, export_to_ics, export_to_markdown_checklist
    from fastapi.responses import PlainTextResponse

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
    """
    Export a saved meeting summary in markdown or plain text format.
    """
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


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

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
