// engine.jsx
// Hyper-Personalization Engine — local storage logic for UI states

export const TOPICS = [
  "AI", "Bitcoin", "Business", "Cricket", "Crypto", "Education", "Elections",
  "Entertainment", "Environment", "Finance", "Health", "IPL", "Inflation",
  "Markets", "Movies", "OpenAI", "Politics", "Science", "Sports", "Startups",
  "Technology", "Tesla", "War", "World"
];

// Re-map front-end actions to backend archetypes if needed, though we will
// mainly use the backend archetypes directly now.

// ── Local Interaction Log ────────────────────────────────────
export function loadLog() {
  try {
    const raw = localStorage.getItem("margin_log");
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

export function logInteraction(type, article) {
  const log = loadLog();
  log.unshift({ id: article.story_id || article.id, type, topic: article.category || article.topic, ts: Date.now() });
  localStorage.setItem("margin_log", JSON.stringify(log.slice(0, 500)));
  window.dispatchEvent(new CustomEvent("margin:log"));
}

// ── Bookmarks persistence ────────────────────────────────
export function loadBookmarks() {
  try {
    const raw = localStorage.getItem("margin_bookmarks");
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

export function saveBookmark(article) {
  const bmarks = loadBookmarks();
  const aid = article.story_id || article.id;
  if (bmarks.some(b => b.id === aid)) return; // already saved
  bmarks.unshift({
    id: aid,
    headline: article.title || article.headline,
    author: article.publisher || article.author,
    source: article.publisher || article.source,
    topic: article.category || article.topic,
    minutes: article.minutes || Math.max(2, Math.round(((article.summary || "").length || 200) / 100)),
    summary: article.summary,
    savedAt: Date.now(),
  });
  localStorage.setItem("margin_bookmarks", JSON.stringify(bmarks.slice(0, 200)));
  window.dispatchEvent(new CustomEvent("margin:bookmarks"));
}

export function removeBookmark(articleId) {
  const bmarks = loadBookmarks().filter(b => b.id !== articleId && b.story_id !== articleId);
  localStorage.setItem("margin_bookmarks", JSON.stringify(bmarks));
  window.dispatchEvent(new CustomEvent("margin:bookmarks"));
}

export function isBookmarked(articleId) {
  return loadBookmarks().some(b => b.id === articleId || b.story_id === articleId);
}

export function aggregateStats(log) {
  const byTopic = {};
  const byType = {};
  for (const i of log) {
    byTopic[i.topic] = (byTopic[i.topic] || 0) + 1;
    byType[i.type] = (byType[i.type] || 0) + 1;
  }
  return { total: log.length, byTopic, byType };
}

// Map backend returned articles to frontend expected field names if needed
export function mapBackendToFrontend(a) {
  return {
    ...a,
    id: a.story_id,
    topic: a.category,
    headline: a.title,
    author: a.publisher || "Staff",
    source: a.publisher || "News",
    minutes: Math.max(2, Math.round(((a.summary || "").length || 200) / 100)),
    score: a.reranker_score || 0.8 // fallback for UI
  };
}
