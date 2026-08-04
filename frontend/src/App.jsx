import React, { useState, useEffect, useRef } from "react";
import { uploadMeetingAudio, fetchMeetingSummary, exportMeeting, checkHealth } from "./api";

// ── Sample Audio Helper for Demo / Testing ───────────────────────────
function createSampleAudioBlob() {
  // Generate a brief valid silent WAV byte header for instant demo upload
  const sampleRate = 8000;
  const numChannels = 1;
  const bitsPerSample = 16;
  const numSamples = sampleRate * 2; // 2 seconds
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
  view.setUint16(20, 1, true); // PCM format
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
  // Health & connection state
  const [health, setHealth] = useState(null);

  // File upload state
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [pipelineStage, setPipelineStage] = useState(0); // 0: Idle, 1: Validating, 2: Transcribing, 3: Extracting, 4: Emailing
  const [errorMsg, setErrorMsg] = useState("");

  // Summary state
  const [summary, setSummary] = useState(null);
  const [activeTab, setActiveTab] = useState("overview"); // "overview" | "transcript" | "email"
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [filterOwner, setFilterOwner] = useState("all");

  // History & Drawer state
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);
  const [pastMeetingIdInput, setPastMeetingIdInput] = useState("");

  const fileInputRef = useRef(null);

  useEffect(() => {
    checkHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "warn", gemini_api_key_configured: false }));
  }, []);

  // ── Drag & Drop Handlers ──────────────────────────────────────────
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
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
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

  // ── Pipeline Execution Handler ────────────────────────────────────
  const handleStartProcessing = async () => {
    if (!selectedFile || uploading) return;
    setUploading(true);
    setErrorMsg("");
    setPipelineStage(1);

    try {
      // Step 1: Validation
      await new Promise((r) => setTimeout(r, 600));
      setPipelineStage(2); // Transcribing

      // Step 2: Call upload endpoint (executes transcription + extraction + email draft on backend)
      const summaryResult = await uploadMeetingAudio(selectedFile);
      setPipelineStage(3); // Extracting

      await new Promise((r) => setTimeout(r, 400));
      setPipelineStage(4); // Emailing

      await new Promise((r) => setTimeout(r, 300));
      setSummary(summaryResult);
      setActiveTab("overview");
    } catch (err) {
      setErrorMsg(err.message || "Failed to process meeting audio.");
    } finally {
      setUploading(false);
      setPipelineStage(0);
    }
  };

  // ── Email Copy & Export Handlers ──────────────────────────────────
  const handleCopyEmail = () => {
    if (!summary?.email_draft) return;
    navigator.clipboard.writeText(summary.email_draft);
    setCopiedEmail(true);
    setTimeout(() => setCopiedEmail(false), 2000);
  };

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

  const handleFetchPastMeeting = async (idToFetch) => {
    const id = idToFetch || pastMeetingIdInput.trim();
    if (!id) return;
    try {
      const res = await fetchMeetingSummary(id);
      setSummary(res);
      setShowHistoryDrawer(false);
      setActiveTab("overview");
    } catch (err) {
      alert("Error: " + err.message);
    }
  };

  // ── Derived Owners List for Filtering ─────────────────────────────
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
      {/* ── Top Navigation Bar ────────────────────────────────────── */}
      <header className="header">
        <div className="brand-logo" onClick={() => setSummary(null)}>
          <div className="brand-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="22" />
            </svg>
          </div>
          <span>Debrief</span>
          <span className="brand-tag">AI Meeting Intelligence</span>
        </div>

        <div className="header-right">
          {health && (
            <div className="status-chip" title="Gemini 2.5 API Status">
              <span className={`status-dot ${health.status === "healthy" ? "healthy" : "warn"}`} />
              <span>{health.status === "healthy" ? "Gemini 2.5 Active" : "Check API Key"}</span>
            </div>
          )}

          <button className="btn" onClick={() => setShowHistoryDrawer(true)}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Lookup Past Meeting
          </button>
        </div>
      </header>

      {/* ── Main View Container ───────────────────────────────────── */}
      <main className="main-content">
        {!summary && (
          <>
            {/* Hero Banner */}
            <div className="hero-section">
              <h1 className="hero-title">
                Turn Meeting Audio into <span className="hero-gradient">Verified Action & Decisions</span>
              </h1>
              <p className="hero-subtitle">
                Upload your meeting recording. Native Gemini audio understanding produces timestamped transcripts,
                grounded action items with owner assignment, decisions with exact source quotes, and a ready-to-send email draft.
              </p>
            </div>

            {/* Dropzone Upload Card */}
            <div
              className={`upload-card ${dragActive ? "drag-active" : ""}`}
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
              <div className="upload-icon-wrapper">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>
              <div className="upload-title">
                {selectedFile ? selectedFile.name : "Drop meeting audio recording here"}
              </div>
              <div className="upload-desc">
                {selectedFile
                  ? `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · Click to change file`
                  : "or click to browse from your computer (MP3, WAV, M4A, AAC, FLAC, WebM)"}
              </div>
              <div className="format-chips">
                <span className="format-chip">MP3</span>
                <span className="format-chip">WAV</span>
                <span className="format-chip">M4A</span>
                <span className="format-chip">FLAC</span>
                <span className="format-chip">WEBM</span>
                <span className="format-chip">Max 500MB</span>
              </div>
            </div>

            {/* Selected File Action Bar */}
            {selectedFile && (
              <div className="audio-preview-card">
                <div className="audio-info">
                  <div className="audio-icon-box">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M9 18V5l12-2v13" />
                      <circle cx="6" cy="18" r="3" />
                      <circle cx="18" cy="16" r="3" />
                    </svg>
                  </div>
                  <div>
                    <div className="audio-filename">{selectedFile.name}</div>
                    <div className="audio-meta">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · Ready for processing</div>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 10 }}>
                  <button className="btn" onClick={() => setSelectedFile(null)} disabled={uploading}>
                    Remove
                  </button>
                  <button className="btn btn-primary" onClick={handleStartProcessing} disabled={uploading}>
                    {uploading ? (
                      <>
                        <div className="spinner" /> Processing Audio…
                      </>
                    ) : (
                      "🚀 Generate Debrief Summary"
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Quick Demo Sample Loader */}
            {!selectedFile && (
              <div style={{ textAlign: "center" }}>
                <span style={{ fontSize: 13, color: "var(--text-3)", marginRight: 8 }}>Need a test file?</span>
                <button className="btn" onClick={handleLoadSampleAudio}>
                  ⚡ Load Sample Meeting Audio
                </button>
              </div>
            )}

            {/* Error Message Display */}
            {errorMsg && (
              <div
                style={{
                  marginTop: 20,
                  padding: "14px 18px",
                  background: "rgba(251, 113, 133, 0.1)",
                  border: "1px solid var(--rose)",
                  borderRadius: "var(--radius-md)",
                  color: "var(--rose)",
                  fontSize: 13,
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                }}
              >
                ⚠️ <span>{errorMsg}</span>
              </div>
            )}

            {/* Pipeline Stage Progress Tracker */}
            {uploading && (
              <div className="progress-card">
                <div className="progress-header">
                  <span>Gemini Native Processing Pipeline</span>
                  <span style={{ fontSize: 12, color: "var(--brand-hi)" }}>Stage {pipelineStage} of 4</span>
                </div>
                <div className="stage-steps">
                  <div className={`stage-step ${pipelineStage === 1 ? "active" : pipelineStage > 1 ? "completed" : ""}`}>
                    <div className="stage-number">{pipelineStage > 1 ? "✓" : "1"}</div>
                    <div className="stage-label">Audio Validation</div>
                  </div>
                  <div className={`stage-step ${pipelineStage === 2 ? "active" : pipelineStage > 2 ? "completed" : ""}`}>
                    <div className="stage-number">{pipelineStage > 2 ? "✓" : "2"}</div>
                    <div className="stage-label">Gemini Audio Transcription</div>
                  </div>
                  <div className={`stage-step ${pipelineStage === 3 ? "active" : pipelineStage > 3 ? "completed" : ""}`}>
                    <div className="stage-number">{pipelineStage > 3 ? "✓" : "3"}</div>
                    <div className="stage-label">Grounded Extraction</div>
                  </div>
                  <div className={`stage-step ${pipelineStage === 4 ? "active" : pipelineStage > 4 ? "completed" : ""}`}>
                    <div className="stage-number">{pipelineStage > 4 ? "✓" : "4"}</div>
                    <div className="stage-label">Follow-up Email Synthesis</div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* ── Meeting Summary Dashboard View ────────────────────────────── */}
        {summary && (
          <div className="summary-container">
            {/* Summary Top Bar */}
            <div className="summary-header-card">
              <div className="summary-title-group">
                <div className="summary-filename">{summary.filename}</div>
                <div className="summary-meta-row">
                  <span className="meta-badge">📅 {summary.created_at}</span>
                  <span className="meta-badge">🆔 {summary.id}</span>
                  <span className="meta-badge">📝 {summary.transcript?.segments?.length || 0} Spoken Segments</span>
                  <span className="meta-badge">⚡ {summary.action_items?.length || 0} Action Items</span>
                </div>
              </div>

              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button className="btn" onClick={() => setSummary(null)}>
                  ← Upload New Recording
                </button>
                <button className="btn" onClick={() => handleDownloadExport("markdown")}>
                  ⬇️ Export Markdown
                </button>
                <button className="btn btn-primary" onClick={() => setActiveTab("email")}>
                  ✉️ View Email Draft
                </button>
              </div>
            </div>

            {/* Confidence Note Banner if degraded */}
            {summary.confidence_note && (
              <div
                style={{
                  padding: "12px 18px",
                  background: "rgba(251, 191, 36, 0.1)",
                  border: "1px solid var(--amber)",
                  borderRadius: "var(--radius-md)",
                  color: "var(--amber)",
                  fontSize: 13,
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                }}
              >
                ⚠️ <span><strong>Analyst Note:</strong> {summary.confidence_note}</span>
              </div>
            )}

            {/* Tabs Navigation */}
            <div className="tabs-bar">
              <button
                className={`tab-btn ${activeTab === "overview" ? "active" : ""}`}
                onClick={() => setActiveTab("overview")}
              >
                📊 Overview & Grounded Extractions
              </button>
              <button
                className={`tab-btn ${activeTab === "transcript" ? "active" : ""}`}
                onClick={() => setActiveTab("transcript")}
              >
                🎙️ Timestamped Transcript
              </button>
              <button
                className={`tab-btn ${activeTab === "email" ? "active" : ""}`}
                onClick={() => setActiveTab("email")}
              >
                ✉️ Follow-Up Email Draft
              </button>
            </div>

            {/* TAB 1: OVERVIEW & EXTRACTIONS */}
            {activeTab === "overview" && (
              <div className="content-grid">
                {/* Action Items Card */}
                <div className="section-card">
                  <div className="card-header">
                    <div className="card-title">
                      <span>⚡ Grounded Action Items</span>
                      <span className="meta-badge" style={{ background: "var(--brand-dim)", color: "var(--brand-hi)" }}>
                        {filteredActionItems.length}
                      </span>
                    </div>

                    {/* Owner Filter Dropdown */}
                    {uniqueOwners.length > 0 && (
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 12, color: "var(--text-3)" }}>Filter owner:</span>
                        <select
                          value={filterOwner}
                          onChange={(e) => setFilterOwner(e.target.value)}
                          style={{
                            background: "var(--surface-2)",
                            color: "var(--text-1)",
                            border: "1px solid var(--border)",
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
                    <div style={{ fontSize: 13, color: "var(--text-3)", padding: "16px 0" }}>
                      No action items matching filter criteria.
                    </div>
                  ) : (
                    <div className="action-items-list">
                      {filteredActionItems.map((ai) => (
                        <div key={ai.id} className="action-item-card">
                          <div className="action-item-top">
                            <div className="action-desc">
                              <span style={{ color: "var(--brand-hi)", marginRight: 6 }}>[{ai.id}]</span>
                              {ai.description}
                            </div>
                            <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                              <span className={`owner-pill ${!ai.owner ? "unassigned" : ""}`}>
                                👤 {ai.owner || "Unassigned"}
                              </span>
                              {ai.due_date && <span className="due-pill">📅 Due: {ai.due_date}</span>}
                            </div>
                          </div>

                          {/* Traceable Source Excerpt Quote */}
                          <div className="source-excerpt-box">
                            <span className="source-icon">💬 Quote:</span>
                            <span>"{ai.source_excerpt}"</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Decisions Made Card */}
                <div className="section-card">
                  <div className="card-header">
                    <div className="card-title">
                      <span>🎯 Agreed Decisions</span>
                      <span className="meta-badge" style={{ background: "rgba(52, 211, 153, 0.15)", color: "var(--emerald)" }}>
                        {summary.decisions?.length || 0}
                      </span>
                    </div>
                  </div>

                  {(!summary.decisions || summary.decisions.length === 0) ? (
                    <div style={{ fontSize: 13, color: "var(--text-3)", padding: "16px 0" }}>
                      No explicit decisions recorded in this session.
                    </div>
                  ) : (
                    <div className="decisions-list">
                      {summary.decisions.map((d) => (
                        <div key={d.id} className="decision-card">
                          <div className="decision-desc">
                            <span style={{ color: "var(--emerald)", marginRight: 6 }}>[{d.id}]</span>
                            {d.description}
                          </div>
                          <div className="source-excerpt-box">
                            <span className="source-icon" style={{ color: "var(--emerald)" }}>💬 Quote:</span>
                            <span>"{d.source_excerpt}"</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Key Discussion Points & Open Questions Grid */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
                  {/* Key Discussion Points */}
                  <div className="section-card">
                    <div className="card-header">
                      <div className="card-title">📌 Key Discussion Points</div>
                    </div>
                    <div className="bullets-list">
                      {summary.key_discussion_points?.map((pt, i) => (
                        <div key={i} className="bullet-item">
                          <div className="bullet-dot" />
                          <span>{pt}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Open Questions */}
                  <div className="section-card">
                    <div className="card-header">
                      <div className="card-title">❓ Open Questions</div>
                    </div>
                    {(!summary.open_questions || summary.open_questions.length === 0) ? (
                      <div style={{ fontSize: 13, color: "var(--text-3)" }}>All questions resolved.</div>
                    ) : (
                      <div className="bullets-list">
                        {summary.open_questions.map((q, i) => (
                          <div key={i} className="bullet-item">
                            <div className="bullet-dot amber" />
                            <span>{q}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: FULL TIMESTAMPED TRANSCRIPT */}
            {activeTab === "transcript" && (
              <div className="section-card">
                <div className="card-header">
                  <div className="card-title">🎙️ Speaker-Segmented Transcript</div>
                  <button className="btn" onClick={() => navigator.clipboard.writeText(summary.transcript?.full_text)}>
                    📋 Copy Full Text
                  </button>
                </div>

                <div className="transcript-box">
                  {summary.transcript?.segments?.map((seg, i) => (
                    <div key={i} className="transcript-segment">
                      <div className="segment-header">
                        <div className="speaker-badge">
                          <div className="speaker-avatar">
                            {(seg.speaker || "U")[0].toUpperCase()}
                          </div>
                          <span>{seg.speaker || "Participant"}</span>
                        </div>

                        {(seg.start_time !== null && seg.start_time !== undefined) && (
                          <span className="timestamp-chip">
                            ⏱️ {Math.floor(seg.start_time / 60)}:{(seg.start_time % 60).toFixed(0).padStart(2, "0")}
                            {seg.end_time ? ` - ${Math.floor(seg.end_time / 60)}:${(seg.end_time % 60).toFixed(0).padStart(2, "0")}` : ""}
                          </span>
                        )}
                      </div>
                      <div className="segment-text">{seg.text}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 3: FOLLOW-UP EMAIL DRAFT */}
            {activeTab === "email" && (
              <div className="section-card">
                <div className="card-header">
                  <div className="card-title">✉️ Synthesized Follow-Up Email Draft</div>
                  <button className="btn btn-primary" onClick={handleCopyEmail}>
                    {copiedEmail ? "✓ Copied to Clipboard!" : "📋 Copy Email Body"}
                  </button>
                </div>

                <div className="draft-label-banner">
                  ℹ️ [DRAFT — PLEASE REVIEW BEFORE SENDING] · Review action items and owners before sending to participants.
                </div>

                <div className="email-draft-card">{summary.email_draft}</div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── Past Meeting Lookup Drawer ───────────────────────────────── */}
      {showHistoryDrawer && (
        <div className="drawer-backdrop" onClick={() => setShowHistoryDrawer(false)}>
          <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div style={{ fontSize: 16, fontWeight: 700 }}>Lookup Past Meeting</div>
              <button className="close-btn" onClick={() => setShowHistoryDrawer(false)}>
                ✕
              </button>
            </div>

            <div style={{ fontSize: 13, color: "var(--text-2)" }}>
              Enter a meeting ID to load a previously processed summary.
            </div>

            <div style={{ display: "flex", gap: 10 }}>
              <input
                type="text"
                placeholder="e.g. meet_8f3a912b"
                value={pastMeetingIdInput}
                onChange={(e) => setPastMeetingIdInput(e.target.value)}
                style={{
                  flex: 1,
                  background: "var(--surface-2)",
                  border: "1px solid var(--border)",
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
