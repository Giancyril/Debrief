/**
 * API client for Debrief backend service.
 */

export async function checkHealth() {
  const res = await fetch("/health");
  if (!res.ok) {
    throw new Error("Health check failed.");
  }
  return res.json();
}

export async function uploadMeetingAudio(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch("/meetings/upload", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed with status ${res.status}`);
  }

  return res.json(); // Returns MeetingSummary
}

export async function fetchMeetingSummary(meetingId) {
  const res = await fetch(`/meetings/${encodeURIComponent(meetingId)}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to fetch meeting summary.");
  }
  return res.json();
}

export async function exportMeeting(meetingId, format = "markdown") {
  const res = await fetch(
    `/meetings/${encodeURIComponent(meetingId)}/export?format=${format}`
  );
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to export meeting.");
  }
  return res.json(); // { meeting_id, format, content }
}
