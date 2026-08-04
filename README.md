# Debrief — AI Meeting Intelligence Platform

A production-grade meeting intelligence platform powered by **FastAPI** and **Google Gemini 2.5**. Ingests meeting audio uploads (MP3, WAV, M4A, AAC, FLAC, OGG, WebM), generates timestamped transcripts with speaker diarization using Gemini's native audio understanding (supporting inline audio & Files API), extracts strictly grounded action items and decisions (traceable via `source_excerpt`), drafts ready-to-send follow-up emails, and provides Markdown, CSV, ICS iCalendar, and Text export options.

---

## 🚀 Advanced Features Suite

1. **Speaker Diarization & Speaker Renaming**: Interactive speaker avatar editor to rename `"Speaker 1"` to `"Sarah Connor"` across the transcript, action items, and stored speaker mapping.
2. **Audio Player & Timestamp Synchronization**: Audio playback markers and real-time segment highlighting.
3. **Multi-Format Task Exporter**: Export action items directly as **CSV spreadsheets**, **iCalendar (.ics)** event files for calendars, or **Markdown checklists**.
4. **Interactive Task Status Checkboxes**: Check off tasks, set status (`open`, `in_progress`, `completed`), and persist updates.
5. **Meeting Dynamics & Talk-Time Analytics**: Speaker talk-time distribution %, meeting tone classification (*Productive*, *Consensus-Heavy*, *Debated*), and participation balance index.
6. **Multi-Language Synthesis**: Synthesize transcripts, summaries, and follow-up emails in 6+ target languages (English, Spanish, French, German, Japanese, Chinese).
7. **Executive Email Tone Selector**: Re-draft follow-up emails in distinct tones (*Action-Oriented*, *Formal Boardroom*, *Concise Slack*).
8. **Meeting Series Comparison & Sync Delta**: Compare two meeting summaries (e.g. Sprint Sync #1 vs #2) to track resolved vs ongoing vs newly added action items.
9. **Printable 1-Page Boardroom Brief**: Condenses meetings into an executive boardroom memo with 1-click printing support.
10. **Full-Text Meeting Search Engine**: Real-time keyword search across past meeting transcripts, tasks, and decisions.
11. **Next Meeting Agenda Generator**: Automatically creates the next meeting agenda based on unresolved open questions & pending action items.
12. **Meeting Tagging & Categories**: Categorize meetings (`Sprint`, `Sales Call`, `1-on-1`, `All-Hands`).

---

## Project Structure

```
ai-meeting-summarizer/
├── src/
│   ├── main.py                    # FastAPI application entrypoint
│   ├── config.py                  # Environment config & thresholds
│   ├── pipeline/
│   │   ├── audio_validator.py     # Extension, MIME, & size validation
│   │   ├── transcriber.py         # Gemini native audio -> Transcript
│   │   ├── extractor.py           # Grounded ActionItem & Decision extraction
│   │   ├── email_drafter.py       # Follow-up email draft generator
│   │   ├── speaker_manager.py     # Speaker label remapping engine
│   │   ├── action_status_manager.py # Action status toggle manager
│   │   └── translator.py         # Multi-language synthesis
│   ├── output/
│   │   ├── task_exporter.py       # CSV, ICS iCalendar, and Markdown exporter
│   │   ├── sentiment_analyzer.py  # Talk-time & meeting dynamics analyzer
│   │   ├── email_tone_drafter.py  # Executive tone re-drafter
│   │   ├── meeting_diff.py        # Meeting series diff engine
│   │   ├── boardroom_brief.py     # 1-page boardroom memo generator
│   │   └── agenda_generator.py    # Next meeting agenda generator
│   ├── storage/
│   │   ├── file_manager.py        # Temporary audio file storage
│   │   └── meeting_search.py      # Full-text search engine
│   ├── models/
│   │   └── schemas.py             # Pydantic data models
│   └── routes/
│       └── meetings.py            # API endpoints (/upload, /search, /speakers, /export, /analytics, /brief)
├── tests/
│   ├── test_audio_validator.py
│   ├── test_transcriber.py
│   ├── test_extractor.py
│   ├── test_email_drafter.py
│   ├── test_speaker_manager.py
│   ├── test_action_status_manager.py
│   ├── test_task_exporter.py
│   ├── test_sentiment_analyzer.py
│   ├── test_advanced_features.py
│   └── test_integration.py
├── frontend/                      # React + Vite UI
└── README.md
```

---

## Quick Start

### 1. Environment Setup

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

### 2. Install Dependencies & Run Backend

```bash
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

### 3. Run Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Running Tests

```bash
pytest tests/ -v
```
