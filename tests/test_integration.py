import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.config import Config
from src.main import app
from src.models.schemas import MeetingSummary


client = TestClient(app)

# ---------------------------------------------------------------------------
# Mock Gemini Responses for Golden Test
# ---------------------------------------------------------------------------

GOLDEN_TRANSCRIPT_JSON = json.dumps([
    {
        "speaker": "Sarah",
        "start_time": 0.0,
        "end_time": 4.5,
        "text": "Welcome team. Today we need to decide on the database migration."
    },
    {
        "speaker": "Dave",
        "start_time": 4.6,
        "end_time": 10.2,
        "text": "I suggest we migrate to PostgreSQL by the end of August."
    },
    {
        "speaker": "Sarah",
        "start_time": 10.3,
        "end_time": 15.0,
        "text": "Agreed. Let's adopt PostgreSQL. Dave, can you write the migration script by August 25th?"
    },
    {
        "speaker": "Dave",
        "start_time": 15.1,
        "end_time": 18.0,
        "text": "Yes, I will handle the migration script by August 25th."
    }
])

GOLDEN_EXTRACTION_JSON = json.dumps({
    "action_items": [
        {
            "description": "Write the PostgreSQL database migration script.",
            "owner": "Dave",
            "due_date": "2026-08-25",
            "source_excerpt": "Dave: Yes, I will handle the migration script by August 25th."
        }
    ],
    "decisions": [
        {
            "description": "Migrate system database to PostgreSQL.",
            "source_excerpt": "Sarah: Agreed. Let's adopt PostgreSQL."
        }
    ],
    "key_discussion_points": [
        "Database migration planning",
        "PostgreSQL adoption and timeline"
    ],
    "open_questions": [
        "Who will perform the staging environment testing?"
    ],
    "confidence_note": None
})

GOLDEN_EMAIL_DRAFT = """[DRAFT — PLEASE REVIEW BEFORE SENDING]

Dear Team,

Thank you for participating in today's database migration sync. We agreed to adopt PostgreSQL for our core database.

Decisions Made:
  - Migrate system database to PostgreSQL.

Action Items:
  - Write the PostgreSQL database migration script (Owner: Dave — Due: 2026-08-25)

Open Questions:
  - Who will perform the staging environment testing?

Best regards"""


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "docs_url" in response.json()


# ---------------------------------------------------------------------------
# End-to-End Pipeline & Route Tests with Mocked Gemini
# ---------------------------------------------------------------------------

@patch("src.services.gemini_client.genai.Client")
def test_full_pipeline_upload_get_export_flow(mock_genai_client):
    """
    Golden-file Integration Test:
    1. Upload audio file to POST /meetings/upload
    2. Assert response contains grounded action items, decisions, and email draft
    3. Retrieve summary via GET /meetings/{id}
    4. Export as markdown and plain text via GET /meetings/{id}/export
    """
    # Mock Gemini Client API calls
    mock_instance = MagicMock()
    mock_genai_client.return_value = mock_instance

    def mock_generate_content(model, contents, config):
        mock_resp = MagicMock()
        # If contents is audio prompt (list with part + prompt) -> transcript
        if isinstance(contents, list) and len(contents) >= 2:
            mock_resp.text = GOLDEN_TRANSCRIPT_JSON
        else:
            prompt_str = str(contents)
            if "follow-up email" in prompt_str.lower():
                mock_resp.text = GOLDEN_EMAIL_DRAFT
            else:
                mock_resp.text = GOLDEN_EXTRACTION_JSON
        return mock_resp

    mock_instance.models.generate_content.side_effect = mock_generate_content

    # 1. POST /meetings/upload
    audio_content = b"FAKE_AUDIO_HEADER_DATA_12345"
    files = {"file": ("sprint_sync.mp3", audio_content, "audio/mpeg")}

    response = client.post("/meetings/upload", files=files)
    assert response.status_code == 201, response.text

    summary_data = response.json()
    assert summary_data["filename"] == "sprint_sync.mp3"
    assert len(summary_data["action_items"]) == 1
    assert summary_data["action_items"][0]["owner"] == "Dave"
    assert summary_data["action_items"][0]["source_excerpt"] != ""
    assert len(summary_data["decisions"]) == 1
    assert summary_data["decisions"][0]["description"] == "Migrate system database to PostgreSQL."
    assert summary_data["decisions"][0]["source_excerpt"] != ""
    assert "[DRAFT" in summary_data["email_draft"]

    meeting_id = summary_data["id"]

    # 2. GET /meetings/{meeting_id}
    get_res = client.get(f"/meetings/{meeting_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == meeting_id

    # 3. GET /meetings/{meeting_id}/export?format=markdown
    export_md = client.get(f"/meetings/{meeting_id}/export?format=markdown")
    assert export_md.status_code == 200
    md_content = export_md.json()["content"]
    assert "# Meeting Summary: sprint_sync.mp3" in md_content
    assert "Dave" in md_content
    assert "PostgreSQL" in md_content

    # 4. GET /meetings/{meeting_id}/export?format=text
    export_txt = client.get(f"/meetings/{meeting_id}/export?format=text")
    assert export_txt.status_code == 200
    txt_content = export_txt.json()["content"]
    assert "MEETING SUMMARY: sprint_sync.mp3" in txt_content


def test_get_nonexistent_meeting_returns_404():
    response = client.get("/meetings/nonexistent_id_9999")
    assert response.status_code == 404


def test_export_nonexistent_meeting_returns_404():
    response = client.get("/meetings/nonexistent_id_9999/export")
    assert response.status_code == 404
