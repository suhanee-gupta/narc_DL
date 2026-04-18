/**
 * api.js
 * Centralized API client for communicating with the NARC FastAPI backend.
 */

const API_BASE = '/api';

export async function startSession(userId, mood, location = "Global", archetype = "cold_start") {
  const res = await fetch(`${API_BASE}/session/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, mood, location, archetype })
  });
  if (!res.ok) throw new Error("Failed to start session");
  return await res.json();
}

export async function fetchRecommendations(userId, sessionId, category = null) {
  const params = new URLSearchParams({ user_id: userId, session_id: sessionId });
  if (category && category !== "Home") params.append("category", category);
  const res = await fetch(`${API_BASE}/recommendations?${params}`);
  if (!res.ok) throw new Error("Failed to fetch recommendations");
  return await res.json();
}

export async function recordInteraction(userId, sessionId, storyId, action, position = 1) {
  const res = await fetch(`${API_BASE}/interaction`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      session_id: sessionId,
      story_id: storyId,
      action,
      position
    })
  });
  if (!res.ok) throw new Error("Failed to record interaction");
  return await res.json();
}

export async function searchArticles(query) {
  const params = new URLSearchParams({ q: query });
  const res = await fetch(`${API_BASE}/search?${params}`);
  if (!res.ok) throw new Error("Search failed");
  return await res.json();
}

export async function getLogs(userId) {
  const params = new URLSearchParams({ user_id: userId });
  const res = await fetch(`${API_BASE}/logs?${params}`);
  if (!res.ok) throw new Error("Failed to fetch logs");
  return await res.json();
}
