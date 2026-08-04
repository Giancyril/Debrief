import React, { useState, useEffect, useRef } from "react";
import {
  uploadMeetingAudio,
  fetchMeetingSummary,
  exportMeeting,
  exportTasks,
  checkHealth,
  updateSpeakerNames,
  updateActionStatus,
  redraftEmailTone,
  searchMeetings,
  fetchBoardroomBrief,
  fetchNextAgenda,
} from "./api";

function createSampleAudioBlob() {
  const sampleRate = 8000;
  const numChannels = 1;
  const bitsPerSample = 16;
  const numSamples = sampleRate * 2;
  const blockAlign = (numChannels * bitsPerSample) / 8;
  const byteRate = sampleRate * blockAlign;
  const dataSize = numSamples * blockAlign;

  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  function writeString(offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitsPerSample, true);
  writeString(36, "data");
  view.setUint32(40, dataSize, true);

  return new Blob([buffer], { type: "audio/wav" });
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [pipelineStage, setPipelineStage] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");
  const [outputLanguage, setOutputLanguage] = useState("English");

  const [summary, setSummary] = useState(null);
  const [activeTab, setActiveTab] = useState("overview"); // "overview" | "analytics" | "transcript" | "email" | "agenda"
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [filterOwner, setFilterOwner] = useState("all");

  // Advanced features state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [renameSpeakerInput, setRenameSpeakerInput] = useState({ oldName: "", newName: "" });
  const [boardroomBriefText, setBoardroomBriefText] = useState("");
  const [showBriefModal, setShowBriefModal] = useState(false);
  const [nextAgendaText, setNextAgendaText] = useState("");
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);
  const [pastMeetingIdInput, setPastMeetingIdInput] = useState("");

  // Audio player state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [activeSegmentIndex, setActiveSegmentIndex] = useState(-1);
  const audioRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    checkHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "warn", gemini_api_key_configured: false }));
  }, []);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
      setErrorMsg("");
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setErrorMsg("");
    }
  };

  const handleLoadSampleAudio = () => {
    const sampleBlob = createSampleAudioBlob();
    const sampleFile = new File([sampleBlob], "sprint_planning_sync.wav", { type: "audio/wav" });
    setSelectedFile(sampleFile);
    setErrorMsg("");
  };

  const handleStartProcessing = async () => {
    if (!selectedFile || uploading) return;
    setUploading(true);
    setErrorMsg("");
    setPipelineStage(1);

    try {
      await new Promise((r) => setTimeout(r, 400));
      setPipelineStage(2);

      const summaryResult = await uploadMeetingAudio(selectedFile, outputLanguage);
      setPipelineStage(3);

      await new Promise((r) => setTimeout(r, 300));
      setPipelineStage(4);

      await new Promise((r) => setTimeout(r, 200));
      setSummary(summaryResult);
      setActiveTab("overview");
    } catch (err) {
      setErrorMsg(err.message || "Failed to process meeting audio.");
    } finally {
      setUploading(false);
      setPipelineStage(0);
    }
  };

  // Task Status Toggle
  const handleToggleTaskStatus = async (actionId, currentStatus) => {
    if (!summary?.id) return;
    const nextStatus = currentStatus === "completed" ? "open" : "completed";
    try {
      const updated = await updateActionStatus(summary.id, actionId, nextStatus);
      setSummary(updated);
    } catch (err) {
      alert("Failed to update status: " + err.message);
    }
  };

  // Speaker Rename
  const handleRenameSpeaker = async () => {
    if (!summary?.id || !renameSpeakerInput.oldName || !renameSpeakerInput.newName) return;
    try {
      const updated = await updateSpeakerNames(summary.id, {
        [renameSpeakerInput.oldName]: renameSpeakerInput.newName,
      });
      setSummary(updated);
      setShowRenameModal(false);
      setRenameSpeakerInput({ oldName: "", newName: "" });
    } catch (err) {
      alert("Failed to rename speaker: " + err.message);
    }
  };

  // Email Tone Re-draft
  const handleRedraftEmail = async (tone) => {
    if (!summary?.id) return;
    try {
      const res = await redraftEmailTone(summary.id, tone);
      setSummary((prev) => ({ ...prev, email_draft: res.email_draft, email_tone: tone }));
    } catch (err) {
      alert("Failed to re-draft email: " + err.message);
    }
  };

  // Export handlers
  const handleDownloadExport = async (format = "markdown") => {
    if (!summary?.id) return;
    try {
      const res = await exportMeeting(summary.id, format);
      const blob = new Blob([res.content], { type: format === "markdown" ? "text/markdown" : "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `meeting_summary_${summary.id}.${format === "markdown" ? "md" : "txt"}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert("Failed to export meeting: " + err.message);
    }
  };

  const handleExportTasksFormat = async (format) => {
    if (!summary?.id) return;
    try {
      const text = await exportTasks(summary.id, format);
      const ext = format === "ics" ? "ics" : format === "csv" ? "csv" : "md";
      const blob = new Blob([text], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `action_items_${summary.id}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert("Failed to export tasks: " + err.message);
    }
  };

  const handleOpenBoardroomBrief = async () => {
    if (!summary?.id) return;
    try {
      const brief = await fetchBoardroomBrief(summary.id);
      setBoardroomBriefText(brief);
      setShowBriefModal(true);
    } catch (err) {
      alert("Failed to fetch brief: " + err.message);
    }
  };

  const handleLoadNextAgenda = async () => {
    if (!summary?.id) return;
    try {
      const agenda = await fetchNextAgenda(summary.id);
      setNextAgendaText(agenda);
      setActiveTab("agenda");
    } catch (err) {
      alert("Failed to fetch agenda: " + err.message);
    }
  };

  const handleHeaderSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const res = await searchMeetings(searchQuery);
      setSearchResults(res);
    } catch (err) {
      console.error(err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleFetchPastMeeting = async (idToFetch) => {
    const id = idToFetch || pastMeetingIdInput.trim();
    if (!id) return;
    try {
      const res = await fetchMeetingSummary(id);
      setSummary(res);
      setShowHistoryDrawer(false);
      setSearchResults([]);
      setSearchQuery("");
      setActiveTab("overview");
    } catch (err) {
      alert("Error: " + err.message);
    }
  };

  // Audio playback time sync
  const handleTimeUpdate = () => {
    if (!audioRef.current || !summary?.transcript?.segments) return;
    const time = audioRef.current.currentTime;
    setCurrentTime(time);

    const idx = summary.transcript.segments.findIndex(
      (seg) => seg.start_time !== null && seg.end_time !== null && time >= seg.start_time && time <= seg.end_time
    );
    if (idx !== -1 && idx !== activeSegmentIndex) {
      setActiveSegmentIndex(idx);
    }
  };

  const uniqueOwners = summary?.action_items
    ? Array.from(new Set(summary.action_items.map((ai) => ai.owner).filter(Boolean)))
    : [];

  const filteredActionItems = summary?.action_items
    ? summary.action_items.filter((ai) => {
        if (filterOwner === "all") return true;
        if (filterOwner === "unassigned") return !ai.owner;
        return ai.owner === filterOwner;
      })
    : [];

  return (
    <div className="app-layout">
      {/* ── Header Navigation Bar ────────────────────────────────────────── */}
      <header className="header">
        <div className="brand-logo" onClick={() => setSummary(null)}>
          <div className="brand-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
          </div>
          <span>Debrief</span>
          <span className="brand-tag">Executive Intelligence</span>
        </div>

        {/* Global Search Bar */}
        <form onSubmit={handleHeaderSearch} style={{ display: "flex", gap: 6, flex: "0 1 320px" }}>
          <input
            type="text"
            placeholder="Search transcripts & tasks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              background: "var(--surface-2)",
              border: "1px solid var(--border-hi)",
              color: "var(--text-1)",
              padding: "5px 10px",
              borderRadius: "var(--radius-sm)",
              fontSize: 12,
            }}
          />
        </form>

        <div className="header-right">
          {health && (
            <div className="status-chip" title="Gemini API Connectivity">
              <span className={`status-dot ${health.status === "healthy" ? "healthy" : "warn"}`} />
              <span>{health.status === "healthy" ? "Gemini Active" : "Key Needed"}</span>
            </div>
          )}

          <button className="btn btn-ghost" onClick={() => setShowHistoryDrawer(true)}>
            Lookup Past Meeting
          </button>
        </div>
      </header>

      {/* Search Results Popover Drawer */}
      {searchResults.length > 0 && (
        <div style={{ background: "var(--surface-1)", borderBottom: "1px solid var(--border-hi)", padding: "12px 24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 700 }}>Search Matches ({searchResults.length})</span>
            <button className="btn btn-ghost" onClick={() => setSearchResults([])} style={{ fontSize: 11 }}>Clear</button>
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {searchResults.map((r) => (
              <div
                key={r.id}
                onClick={() => handleFetchPastMeeting(r.id)}
                style={{
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-sm)",
                  cursor: "pointer",
                  fontSize: 12,
                }}
              >
                <div style={{ fontWeight: 600 }}>{r.filename}</div>
                <div style={{ color: "var(--text-3)", fontSize: 11 }}>ID: {r.id} · Match score: {r.match_score}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Main Content Area ────────────────────────────────────────────── */}
      <main className="main-content">
        {!summary && (
          <>
            <div className="page-intro">
              <h1 className="page-title">Meeting Intelligence Workbench</h1>
              <p className="page-subtitle">
                Upload meeting audio to generate verifiable, grounded action items with transcript quotes, agreed decisions, and follow-up email drafts.
              </p>
            </div>

            <div className="workbench-grid">
              {/* Left Column: Dropzone & File Selection */}
              <div>
                <div
                  className={`upload-panel ${dragActive ? "drag-active" : ""}`}
                  onDragEnter={handleDrag}
                  onDragOver={handleDrag}
                  onDragLeave={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    style={{ display: "none" }}
                    accept="audio/*,.mp3,.wav,.m4a,.aac,.flac,.ogg,.webm"
                    onChange={handleFileSelect}
                  />

                  <div className="upload-icon-row">
                    <div className="upload-glyph">
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <path d="M12 2v10" />
                        <path d="M17 7l-5-5-5 5" />
                        <path d="M2 17v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2" />
                      </svg>
                    </div>
                    <div>
                      <div className="upload-heading">
                        {selectedFile ? selectedFile.name : "Select or drag meeting audio recording"}
                      </div>
                      <div className="upload-subheading">
                        {selectedFile
                          ? `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · Ready for pipeline processing`
                          : "Click to select file from your system"}
                      </div>
                    </div>
                  </div>

                  <div className="specs-row">
                    <span className="spec-chip">MP3</span>
                    <span className="spec-chip">WAV</span>
                    <span className="spec-chip">M4A</span>
                    <span className="spec-chip">FLAC</span>
                    <span className="spec-chip">WEBM</span>
                    <span className="spec-chip" style={{ color: "var(--text-3)" }}>Max 500 MB</span>
                  </div>
                </div>

                {/* Target Language Selection */}
                <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 12, color: "var(--text-3)" }}>Target Output Language:</span>
                  <select
                    value={outputLanguage}
                    onChange={(e) => setOutputLanguage(e.target.value)}
                    style={{
                      background: "var(--surface-2)",
                      color: "var(--text-1)",
                      border: "1px solid var(--border-hi)",
                      padding: "4px 8px",
                      borderRadius: "var(--radius-sm)",
                      fontSize: 12,
                    }}
                  >
                    <option value="English">English</option>
                    <option value="Spanish">Spanish</option>
                    <option value="French">French</option>
                    <option value="German">German</option>
                    <option value="Japanese">Japanese</option>
                    <option value="Chinese">Chinese</option>
                  </select>
                </div>

                {/* Selected File Bar */}
                {selectedFile && (
                  <div className="selected-file-card">
                    <div className="file-meta-group">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} style={{ color: "var(--accent-hi)", flexShrink: 0 }}>
                        <path d="M9 18V5l12-2v13" />
                        <circle cx="6" cy="18" r="3" />
                        <circle cx="18" cy="16" r="3" />
                      </svg>
                      <div>
                        <div className="file-name">{selectedFile.name}</div>
                        <div className="file-size">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</div>
                      </div>
                    </div>

                    <div style={{ display: "flex", gap: 8 }}>
                      <button className="btn btn-ghost" onClick={() => setSelectedFile(null)} disabled={uploading}>
                        Remove
                      </button>
                      <button className="btn btn-primary" onClick={handleStartProcessing} disabled={uploading}>
                        {uploading ? (
                          <>
                            <div className="stage-spinner" /> Processing…
                          </>
                        ) : (
                          "Run Pipeline"
                        )}
                      </button>
                    </div>
                  </div>
                )}

                {/* Sample Loader */}
                {!selectedFile && (
                  <div style={{ marginTop: 16 }}>
                    <button className="btn btn-ghost" onClick={handleLoadSampleAudio} style={{ fontSize: 12 }}>
                      Load Sample Meeting Audio (.wav)
                    </button>
                  </div>
                )}
              </div>

              {/* Right Column: Process Explanation */}
              <div className="explanation-panel">
                <div className="explanation-title">Pipeline Workflow</div>
                <div className="process-step-list">
                  <div className="process-step-item">
                    <div className="process-step-num">1</div>
                    <div>
                      <div className="process-step-title">Native Audio Transcription</div>
                      <div className="process-step-desc">
                        Gemini 2.5 ingests audio directly to produce timestamped, speaker-labeled text.
                      </div>
                    </div>
                  </div>

                  <div className="process-step-item">
                    <div className="process-step-num">2</div>
                    <div>
                      <div className="process-step-title">Grounded Extraction</div>
                      <div className="process-step-desc">
                        Extracts action items and decisions with exact transcript quotes. No unstated task assignments.
                      </div>
                    </div>
                  </div>

                  <div className="process-step-item">
                    <div className="process-step-num">3</div>
                    <div>
                      <div className="process-step-title">Executive Email Synthesis</div>
                      <div className="process-step-desc">
                        Formats extracted notes into a reviewable draft ready for email delivery.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {errorMsg && (
              <div
                style={{
                  marginTop: 20,
                  padding: "12px 16px",
                  background: "var(--rose-dim)",
                  border: "1px solid var(--rose)",
                  borderRadius: "var(--radius-md)",
                  color: "var(--rose)",
                  fontSize: 13,
                }}
              >
                ⚠️ {errorMsg}
              </div>
            )}

            {uploading && (
              <div className="processing-panel">
                <div className="processing-title">
                  <span>Processing Meeting Audio</span>
                  <span style={{ fontSize: 12, color: "var(--text-3)", fontFamily: "var(--font-mono)" }}>
                    Stage {pipelineStage} / 4
                  </span>
                </div>

                <div className="pipeline-rail">
                  <div className={`rail-stage ${pipelineStage === 1 ? "active" : pipelineStage > 1 ? "completed" : ""}`}>
                    <div className="rail-stage-icon">{pipelineStage > 1 ? "✓" : "1"}</div>
                    <div className="rail-stage-label">Audio Validation</div>
                  </div>

                  <div className={`rail-stage ${pipelineStage === 2 ? "active" : pipelineStage > 2 ? "completed" : ""}`}>
                    <div className="rail-stage-icon">{pipelineStage > 2 ? "✓" : "2"}</div>
                    <div className="rail-stage-label">Transcribing Audio</div>
                  </div>

                  <div className={`rail-stage ${pipelineStage === 3 ? "active" : pipelineStage > 3 ? "completed" : ""}`}>
                    <div className="rail-stage-icon">{pipelineStage > 3 ? "✓" : "3"}</div>
                    <div className="rail-stage-label">Grounded Extractions</div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* ── Results Summary View ────────────────────────────────────────── */}
        {summary && (
          <div className="results-container">
            {/* Results Top Card */}
            <div className="results-header-card">
              <div>
                <div className="results-filename">{summary.filename}</div>
                <div className="results-meta-row">
                  <span className="meta-chip">{summary.created_at}</span>
                  <span className="meta-chip" style={{ fontFamily: "var(--font-mono)" }}>ID: {summary.id}</span>
                  <span className="meta-chip">{summary.transcript?.segments?.length || 0} Segments</span>
                  <span className="meta-chip" style={{ color: "var(--amber)" }}>{summary.action_items?.length || 0} Tasks</span>
                  <span className="meta-chip" style={{ color: "var(--emerald)" }}>{summary.decisions?.length || 0} Decisions</span>
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="btn btn-ghost" onClick={() => setSummary(null)}>
                  ← New Upload
                </button>
                <button className="btn" onClick={() => setShowRenameModal(true)}>
                  ✏️ Rename Speakers
                </button>
                <button className="btn" onClick={handleOpenBoardroomBrief}>
                  📜 Boardroom Brief
                </button>

                {/* Task Exporter Dropdown */}
                <select
                  onChange={(e) => {
                    if (e.target.value) {
                      handleExportTasksFormat(e.target.value);
                      e.target.value = "";
                    }
                  }}
                  style={{
                    background: "var(--surface-2)",
                    color: "var(--text-1)",
                    border: "1px solid var(--border-hi)",
                    padding: "6px 10px",
                    borderRadius: "var(--radius-sm)",
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                >
                  <option value="">Export Tasks...</option>
                  <option value="csv">CSV Spreadsheet</option>
                  <option value="ics">iCalendar (.ics)</option>
                  <option value="markdown">Markdown Checklist</option>
                </select>

                <button className="btn btn-primary" onClick={() => setActiveTab("email")}>
                  View Email Draft
                </button>
              </div>
            </div>

            {summary.confidence_note && (
              <div
                style={{
                  padding: "10px 16px",
                  background: "var(--amber-dim)",
                  border: "1px solid var(--amber)",
                  borderRadius: "var(--radius-md)",
                  color: "var(--amber)",
                  fontSize: 13,
                }}
              >
                ⚠️ <strong>Analyst Note:</strong> {summary.confidence_note}
              </div>
            )}

            {/* Navigation Tabs */}
            <div className="results-tabs">
              <button
                className={`tab-item ${activeTab === "overview" ? "active" : ""}`}
                onClick={() => setActiveTab("overview")}
              >
                Overview & Extractions
              </button>
              <button
                className={`tab-item ${activeTab === "analytics" ? "active" : ""}`}
                onClick={() => setActiveTab("analytics")}
              >
                📊 Dynamics & Talk-Time
              </button>
              <button
                className={`tab-item ${activeTab === "transcript" ? "active" : ""}`}
                onClick={() => setActiveTab("transcript")}
              >
                Transcript Reference
              </button>
              <button
                className={`tab-item ${activeTab === "email" ? "active" : ""}`}
                onClick={() => setActiveTab("email")}
              >
                Follow-Up Email Draft
              </button>
              <button
                className={`tab-item ${activeTab === "agenda" ? "active" : ""}`}
                onClick={handleLoadNextAgenda}
              >
                📅 Next Agenda
              </button>
            </div>

            {/* TAB 1: OVERVIEW & EXTRACTIONS */}
            {activeTab === "overview" && (
              <div className="content-section">
                {/* Action Items List with Checkboxes */}
                <div className="section-block">
                  <div className="section-header-row">
                    <div className="section-heading">
                      <span>Action Items</span>
                      <span className="count-badge">{filteredActionItems.length}</span>
                    </div>

                    {uniqueOwners.length > 0 && (
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 12, color: "var(--text-3)" }}>Filter owner:</span>
                        <select
                          value={filterOwner}
                          onChange={(e) => setFilterOwner(e.target.value)}
                          style={{
                            background: "var(--surface-2)",
                            color: "var(--text-1)",
                            border: "1px solid var(--border-hi)",
                            padding: "4px 8px",
                            borderRadius: "var(--radius-sm)",
                            fontSize: 12,
                          }}
                        >
                          <option value="all">All Owners</option>
                          {uniqueOwners.map((owner) => (
                            <option key={owner} value={owner}>
                              {owner}
                            </option>
                          ))}
                          <option value="unassigned">Unassigned</option>
                        </select>
                      </div>
                    )}
                  </div>

                  {filteredActionItems.length === 0 ? (
                    <div style={{ fontSize: 13, color: "var(--text-3)", padding: "8px 0" }}>
                      No action items recorded for this filter.
                    </div>
                  ) : (
                    <div className="action-list">
                      {filteredActionItems.map((ai) => (
                        <div key={ai.id} className="action-card">
                          <div className="action-card-header">
                            <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                              <input
                                type="checkbox"
                                checked={ai.status === "completed"}
                                onChange={() => handleToggleTaskStatus(ai.id, ai.status)}
                                style={{ marginTop: 3, cursor: "pointer" }}
                              />
                              <div>
                                <span className="action-id">[{ai.id}]</span>
                                <span
                                  className="action-title"
                                  style={{
                                    textDecoration: ai.status === "completed" ? "line-through" : "none",
                                    color: ai.status === "completed" ? "var(--text-3)" : "var(--text-1)",
                                  }}
                                >
                                  {ai.description}
                                </span>
                              </div>
                            </div>

                            <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                              <span className={`owner-tag ${!ai.owner ? "unassigned" : ""}`}>
                                {ai.owner ? `Assignee: ${ai.owner}` : "No owner specified"}
                              </span>
                              {ai.due_date && <span className="due-tag">Due: {ai.due_date}</span>}
                            </div>
                          </div>

                          <div className="grounding-quote-box">
                            <span className="grounding-label">Transcript Quote</span>
                            <span>"{ai.source_excerpt}"</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Agreed Decisions */}
                <div className="section-block">
                  <div className="section-header-row">
                    <div className="section-heading">
                      <span>Agreed Decisions</span>
                      <span className="count-badge" style={{ color: "var(--emerald)" }}>
                        {summary.decisions?.length || 0}
                      </span>
                    </div>
                  </div>

                  {(!summary.decisions || summary.decisions.length === 0) ? (
                    <div style={{ fontSize: 13, color: "var(--text-3)", padding: "8px 0" }}>
                      No explicit consensus decisions recorded.
                    </div>
                  ) : (
                    <div className="decision-list">
                      {summary.decisions.map((d) => (
                        <div key={d.id} className="decision-card">
                          <div>
                            <span className="decision-id">[{d.id}]</span>
                            <span className="decision-text">{d.description}</span>
                          </div>

                          <div className="grounding-quote-box">
                            <span className="grounding-label" style={{ color: "var(--emerald)" }}>Transcript Quote</span>
                            <span>"{d.source_excerpt}"</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Discussion Points & Open Questions */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                  <div className="section-block">
                    <div className="section-header-row">
                      <div className="section-heading">Key Topics Covered</div>
                    </div>
                    <div className="bullet-list">
                      {summary.key_discussion_points?.map((pt, i) => (
                        <div key={i} className="bullet-row">
                          <div className="bullet-marker" />
                          <span>{pt}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="section-block">
                    <div className="section-header-row">
                      <div className="section-heading">Open Questions</div>
                    </div>
                    {(!summary.open_questions || summary.open_questions.length === 0) ? (
                      <div style={{ fontSize: 13, color: "var(--text-3)" }}>All questions resolved.</div>
                    ) : (
                      <div className="bullet-list">
                        {summary.open_questions.map((q, i) => (
                          <div key={i} className="bullet-row">
                            <div className="bullet-marker amber" />
                            <span>{q}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: DYNAMICS & TALK-TIME ANALYTICS */}
            {activeTab === "analytics" && (
              <div className="section-block">
                <div className="section-header-row">
                  <div className="section-heading">📊 Meeting Dynamics & Talk-Time Analytics</div>
                </div>

                {summary.analytics && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                    <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
                      <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", padding: "14px 20px", borderRadius: "var(--radius-md)", flex: 1 }}>
                        <div style={{ fontSize: 12, color: "var(--text-3)" }}>Meeting Tone</div>
                        <div style={{ fontSize: 18, fontWeight: 700, color: "var(--accent-hi)", marginTop: 4 }}>{summary.analytics.meeting_tone}</div>
                      </div>

                      <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", padding: "14px 20px", borderRadius: "var(--radius-md)", flex: 1 }}>
                        <div style={{ fontSize: 12, color: "var(--text-3)" }}>Total Words Spoken</div>
                        <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text-1)", marginTop: 4 }}>{summary.analytics.total_words}</div>
                      </div>

                      <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", padding: "14px 20px", borderRadius: "var(--radius-md)", flex: 1 }}>
                        <div style={{ fontSize: 12, color: "var(--text-3)" }}>Participation Balance Index</div>
                        <div style={{ fontSize: 18, fontWeight: 700, color: "var(--emerald)", marginTop: 4 }}>{summary.analytics.participation_ratio}</div>
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Speaker Talk-Time Distribution</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                        {Object.entries(summary.analytics.talk_time_percentages || {}).map(([speaker, pct]) => (
                          <div key={speaker}>
                            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                              <span>{speaker}</span>
                              <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent-hi)" }}>{pct}%</span>
                            </div>
                            <div style={{ background: "var(--surface-3)", height: 8, borderRadius: 4, overflow: "hidden" }}>
                              <div style={{ background: "var(--accent)", height: "100%", width: `${pct}%` }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: TRANSCRIPT REFERENCE */}
            {activeTab === "transcript" && (
              <div className="section-block">
                <div className="section-header-row">
                  <div className="section-heading">Timestamped Transcript Reference</div>
                  <button className="btn btn-ghost" onClick={() => navigator.clipboard.writeText(summary.transcript?.full_text)}>
                    Copy Text
                  </button>
                </div>

                <div className="transcript-doc">
                  {summary.transcript?.segments?.map((seg, i) => (
                    <div key={i} className={`transcript-row ${activeSegmentIndex === i ? "active-segment" : ""}`}>
                      <div className="transcript-meta">
                        <div className="speaker-tag">
                          <div className="speaker-avatar-initial">
                            {(seg.speaker || "P")[0].toUpperCase()}
                          </div>
                          <span>{seg.speaker || "Participant"}</span>
                        </div>

                        {(seg.start_time !== null && seg.start_time !== undefined) && (
                          <span className="timestamp-tag">
                            {Math.floor(seg.start_time / 60)}:{(seg.start_time % 60).toFixed(0).padStart(2, "0")}
                            {seg.end_time ? ` - ${Math.floor(seg.end_time / 60)}:${(seg.end_time % 60).toFixed(0).padStart(2, "0")}` : ""}
                          </span>
                        )}
                      </div>
                      <div className="transcript-body">{seg.text}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 4: FOLLOW-UP EMAIL DRAFT */}
            {activeTab === "email" && (
              <div className="section-block">
                <div className="section-header-row">
                  <div className="section-heading">Follow-Up Email Draft</div>
                  <div style={{ display: "flex", gap: 8 }}>
                    {/* Executive Tone Switcher */}
                    <select
                      value={summary.email_tone || "action_oriented"}
                      onChange={(e) => handleRedraftEmail(e.target.value)}
                      style={{
                        background: "var(--surface-2)",
                        color: "var(--text-1)",
                        border: "1px solid var(--border-hi)",
                        padding: "4px 8px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: 12,
                      }}
                    >
                      <option value="action_oriented">Tone: Action Oriented</option>
                      <option value="formal_boardroom">Tone: Formal Boardroom</option>
                      <option value="concise_slack">Tone: Concise Slack</option>
                    </select>

                    <button className="btn btn-primary" onClick={handleCopyEmail}>
                      {copiedEmail ? "✓ Copied Body" : "Copy Email Body"}
                    </button>
                  </div>
                </div>

                <div className="email-client-container">
                  <div className="email-header-bar">
                    <div className="email-header-field">
                      <strong>To:</strong> <span>[Meeting Participants]</span>
                    </div>
                    <div className="email-header-field">
                      <strong>Subject:</strong> <span>Follow-Up: {summary.filename}</span>
                    </div>
                  </div>

                  <div style={{ padding: 12 }}>
                    <div className="draft-watermark">
                      <span>DRAFT — PLEASE REVIEW BEFORE SENDING</span>
                      <span style={{ fontSize: 11, fontWeight: 500 }}>Editable</span>
                    </div>
                  </div>

                  <div className="email-body-area">{summary.email_draft}</div>
                </div>
              </div>
            )}

            {/* TAB 5: NEXT MEETING AGENDA */}
            {activeTab === "agenda" && (
              <div className="section-block">
                <div className="section-header-row">
                  <div className="section-heading">📅 Next Meeting Agenda</div>
                  <button className="btn btn-primary" onClick={() => navigator.clipboard.writeText(nextAgendaText)}>
                    Copy Agenda Markdown
                  </button>
                </div>

                <div className="email-body-area">{nextAgendaText}</div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── Speaker Rename Modal ───────────────────────────────────────────── */}
      {showRenameModal && (
        <div className="drawer-backdrop" onClick={() => setShowRenameModal(false)}>
          <div className="drawer-content" onClick={(e) => e.stopPropagation()} style={{ width: 380 }}>
            <div className="drawer-title-row">
              <div style={{ fontSize: 15, fontWeight: 700 }}>Rename Speaker Label</div>
              <button className="btn btn-ghost" onClick={() => setShowRenameModal(false)}>✕</button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--text-3)", display: "block", marginBottom: 4 }}>Original Speaker Label:</label>
                <input
                  type="text"
                  placeholder="e.g. Speaker 1"
                  value={renameSpeakerInput.oldName}
                  onChange={(e) => setRenameSpeakerInput({ ...renameSpeakerInput, oldName: e.target.value })}
                  style={{ width: "100%", background: "var(--surface-2)", border: "1px solid var(--border)", color: "var(--text-1)", padding: "8px 12px", borderRadius: "var(--radius-sm)" }}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, color: "var(--text-3)", display: "block", marginBottom: 4 }}>New Custom Name:</label>
                <input
                  type="text"
                  placeholder="e.g. Sarah Connor"
                  value={renameSpeakerInput.newName}
                  onChange={(e) => setRenameSpeakerInput({ ...renameSpeakerInput, newName: e.target.value })}
                  style={{ width: "100%", background: "var(--surface-2)", border: "1px solid var(--border)", color: "var(--text-1)", padding: "8px 12px", borderRadius: "var(--radius-sm)" }}
                />
              </div>

              <button className="btn btn-primary" onClick={handleRenameSpeaker}>
                Save Speaker Mapping
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Boardroom Brief Modal ─────────────────────────────────────────── */}
      {showBriefModal && (
        <div className="drawer-backdrop" onClick={() => setShowBriefModal(false)}>
          <div className="drawer-content" onClick={(e) => e.stopPropagation()} style={{ width: 680 }}>
            <div className="drawer-title-row">
              <div style={{ fontSize: 15, fontWeight: 700 }}>📜 Executive Boardroom Brief</div>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-primary" onClick={() => window.print()}>🖨️ Print Brief</button>
                <button className="btn btn-ghost" onClick={() => setShowBriefModal(false)}>✕</button>
              </div>
            </div>

            <pre style={{ background: "var(--surface-2)", padding: 16, borderRadius: "var(--radius-sm)", fontFamily: "var(--font-mono)", fontSize: 12, whiteSpace: "pre-wrap" }}>
              {boardroomBriefText}
            </pre>
          </div>
        </div>
      )}

      {/* ── Past Meeting Lookup Drawer ───────────────────────────────────── */}
      {showHistoryDrawer && (
        <div className="drawer-backdrop" onClick={() => setShowHistoryDrawer(false)}>
          <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-title-row">
              <div style={{ fontSize: 15, fontWeight: 700 }}>Lookup Past Meeting</div>
              <button className="btn btn-ghost" onClick={() => setShowHistoryDrawer(false)}>
                ✕
              </button>
            </div>

            <div style={{ fontSize: 13, color: "var(--text-2)" }}>
              Enter a saved meeting ID to retrieve its summary and grounded extractions.
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <input
                type="text"
                placeholder="e.g. meet_8f3a912b"
                value={pastMeetingIdInput}
                onChange={(e) => setPastMeetingIdInput(e.target.value)}
                style={{
                  flex: 1,
                  background: "var(--surface-2)",
                  border: "1px solid var(--border-hi)",
                  color: "var(--text-1)",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-sm)",
                  fontSize: 13,
                }}
              />
              <button className="btn btn-primary" onClick={() => handleFetchPastMeeting()}>
                Load
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
