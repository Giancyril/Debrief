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

export async function uploadMeetingAudio(file, outputLanguage = "English") {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`/meetings/upload?output_language=${encodeURIComponent(outputLanguage)}`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed with status ${res.status}`);
  }

  return res.json();
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
  return res.json();
}

export async function exportTasks(meetingId, format = "csv") {
  const res = await fetch(
    `/meetings/${encodeURIComponent(meetingId)}/tasks/export?format=${format}`
  );
  if (!res.ok) {
    throw new Error("Failed to export tasks.");
  }
  return res.text();
}

export async function updateSpeakerNames(meetingId, mapping) {
  const res = await fetch(`/meetings/${encodeURIComponent(meetingId)}/speakers`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(mapping),
  });
  if (!res.ok) {
    throw new Error("Failed to update speaker names.");
  }
  return res.json();
}

export async function updateActionStatus(meetingId, actionId, status) {
  const res = await fetch(`/meetings/${encodeURIComponent(meetingId)}/actions/${encodeURIComponent(actionId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) {
    throw new Error("Failed to update action status.");
  }
  return res.json();
}

export async function redraftEmailTone(meetingId, tone) {
  const res = await fetch(`/meetings/${encodeURIComponent(meetingId)}/re-draft-email?tone=${encodeURIComponent(tone)}`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error("Failed to re-draft email.");
  }
  return res.json();
}

export async function searchMeetings(query) {
  const res = await fetch(`/meetings/search?q=${encodeURIComponent(query)}`);
  if (!res.ok) {
    throw new Error("Search failed.");
  }
  return res.json();
}

export async function fetchBoardroomBrief(meetingId) {
  const res = await fetch(`/meetings/${encodeURIComponent(meetingId)}/brief`);
  if (!res.ok) {
    throw new Error("Failed to fetch brief.");
  }
  return res.text();
}

export async function fetchNextAgenda(meetingId) {
  const res = await fetch(`/meetings/${encodeURIComponent(meetingId)}/next-agenda`);
  if (!res.ok) {
    throw new Error("Failed to fetch next agenda.");
  }
  return res.text();
}

export async function generateMeetingTitle(meetingId) {
  const res = await fetch(`/meetings/${encodeURIComponent(meetingId)}/generate-title`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error("Failed to generate title.");
  }
  return res.json();
}
