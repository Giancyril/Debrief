# AI Meeting Summarizer

A production-grade meeting intelligence platform powered by **FastAPI** and **Google Gemini 2.5**. Accepts meeting audio uploads (MP3, WAV, M4A, AAC, FLAC, OGG, WebM), generates timestamped transcripts with best-effort speaker diarization using Gemini's native audio understanding (handling both inline audio and the Files API), extracts strictly grounded action items and decisions (traceable via `source_excerpt`), drafts ready-to-send follow-up emails, and provides Markdown / Text export options.

---

## Key Features

- **Gemini Native Audio Understanding**: Directly ingests audio files using Google Gemini 2.5 Flash.
- **Smart Audio Routing**: Automatically routes small audio files (< 20 MB) inline and larger/longer files through the **Gemini Files API** with automatic remote file cleanup.
- **Strict Grounding & Auditability**: Every `ActionItem` and `Decision` includes a `source_excerpt` snippet pointing directly to the transcript quote where it was stated.
- **Zero Fabrication**: Unstated owners or deadlines remain `None`. Casual meetings without decisions/tasks return clean empty lists (`[]`).
- **Follow-Up Email Drafting**: Generates a professional follow-up email draft prefixed with `[DRAFT — PLEASE REVIEW BEFORE SENDING]`.
- **Export & Storage**: Export summaries as structured Markdown or plain text via `GET /meetings/{id}/export`.

---

## Project Structure

```
ai-meeting-summarizer/
├── src/
│   ├── main.py                    # FastAPI application entrypoint
│   ├── config.py                  # Environment config & thresholds
│   ├── pipeline/
│   │   ├── audio_validator.py     # Extension, MIME, & file size validation
│   │   ├── transcriber.py         # Gemini native audio -> Transcript
│   │   ├── extractor.py           # Grounded ActionItem & Decision extraction
│   │   └── email_drafter.py       # Follow-up email draft generator
│   ├── models/
│   │   └── schemas.py             # Pydantic models (Transcript, ActionItem, Decision, MeetingSummary)
│   ├── services/
│   │   └── gemini_client.py       # Gemini Client wrapper (Inline + Files API)
│   ├── storage/
│   │   └── file_manager.py        # Temporary audio file management & cleanup
│   └── routes/
│       └── meetings.py            # API routes (POST /upload, GET /{id}, GET /{id}/export)
├── tests/
│   ├── test_audio_validator.py
│   ├── test_transcriber.py
│   ├── test_extractor.py
│   ├── test_email_drafter.py
│   ├── test_schemas.py
│   └── test_integration.py
├── .env.example
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Environment Setup

Copy `.env.example` to `.env` and set your `GEMINI_API_KEY`:

```bash
cp .env.example .env
```

`.env`:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
MAX_UPLOAD_SIZE_MB=500
INLINE_AUDIO_THRESHOLD_MB=20
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the API Server

```bash
uvicorn src.main:app --reload --port 8000
```

Documentation will be available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

## API Endpoints

### `POST /meetings/upload`
Uploads a meeting audio file and executes the 3-stage pipeline:
1. `transcribe_audio`: Audio -> `Transcript`
2. `extract_meeting_data`: Transcript -> Action items, Decisions, Key points, Open questions
3. `draft_follow_up_email`: Extraction -> Follow-up Email Draft

**Request:** `multipart/form-data` with `file`

**Response:** `MeetingSummary` JSON object.

### `GET /meetings/{meeting_id}`
Retrieves a previously processed meeting summary JSON.

### `GET /meetings/{meeting_id}/export?format=markdown|text`
Exports a meeting summary as formatted Markdown or plain text.

---

## Running Tests

```bash
pytest tests/ -v
```
