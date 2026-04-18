// engine.jsx
// Hyper-Personalization Engine — mock data + scoring

import newsData from "./google_news_5000.json";

export const TOPICS = ["Tech", "Finance", "Lifestyle", "Geopolitics", "Health", "Culture"];

export function loadLog() {
  try {
    const raw = localStorage.getItem("margin_log");
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}
export function logInteraction(type, article) {
  const log = loadLog();
  log.unshift({ id: article.id, type, topic: article.topic, ts: Date.now() });
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
  if (bmarks.some(b => b.id === article.id)) return; // already saved
  bmarks.unshift({
    id: article.id,
    headline: article.headline,
    author: article.author,
    source: article.source,
    topic: article.topic,
    minutes: article.minutes,
    summary: article.summary,
    savedAt: Date.now(),
  });
  localStorage.setItem("margin_bookmarks", JSON.stringify(bmarks.slice(0, 200)));
  window.dispatchEvent(new CustomEvent("margin:bookmarks"));
}

export function removeBookmark(articleId) {
  const bmarks = loadBookmarks().filter(b => b.id !== articleId);
  localStorage.setItem("margin_bookmarks", JSON.stringify(bmarks));
  window.dispatchEvent(new CustomEvent("margin:bookmarks"));
}

export function isBookmarked(articleId) {
  return loadBookmarks().some(b => b.id === articleId);
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

export function buildAffinity(log) {
  const c = {};
  for (const i of log) {
    const w = i.type === "save" ? 2.5 : i.type === "like" ? 1.8 : i.type === "listen" ? 1.5 : i.type === "read" ? 1.0 : i.type === "dislike" ? -2.0 : 0.2;
    c[i.topic] = (c[i.topic] || 0) + w;
  }
  return c;
}

function mapGoogleNewsToCorpus(a) {
  const topicMap = {
    "World": "Geopolitics",
    "Business": "Finance",
    "Technology": "Tech",
    "Health": "Health",
    "Entertainment": "Culture",
    "Sports": "Lifestyle",
    "Science": "Tech"
  };
  
  return {
    id: a.story_id || Math.floor(Math.random() * 1000000),
    topic: topicMap[a.category] || "Culture",
    tone: "serious", // Static per user request
    length: "quick", // Static for now as well
    minutes: Math.max(2, Math.round((a.summary?.length || 200) / 100)),
    headline: a.title,
    author: a.publisher || "Staff",
    source: a.publisher || "News",
    summary: a.summary || ""
  };
}

// Subsample strictly 500 items across the entire dataset to ensure deep category diversity (e.g. Culture was missing in the top 500)
export const CORPUS = newsData.filter((_, i) => i % 10 === 0).slice(0, 500).map(mapGoogleNewsToCorpus);

export const PROFILES = {
  analyst: {
    name: "The Analyst",
    bio: "Buy-side PM. Skims 30 headlines before coffee.",
    topicWeights: { Finance: 1.0, Tech: 0.85, Geopolitics: 0.75, Health: 0.3, Culture: 0.1, Lifestyle: 0.05 },
    toneBias:    { serious: 0.9, urgent: 0.85, relaxed: 0.25, uplifting: 0.3 },
    lengthBias:  { quick: 0.8, deep: 0.7 },
  },
  casual: {
    name: "The Casual Reader",
    bio: "Reads over breakfast. Loves a well-written essay.",
    topicWeights: { Lifestyle: 0.95, Culture: 0.9, Health: 0.6, Tech: 0.35, Finance: 0.2, Geopolitics: 0.25 },
    toneBias:    { relaxed: 0.95, uplifting: 0.85, serious: 0.4, urgent: 0.2 },
    lengthBias:  { quick: 0.85, deep: 0.55 },
  },
  newuser: {
    name: "The New User",
    bio: "Just signed up. No click history yet.",
    topicWeights: null, // cold-start
    toneBias: null,
    lengthBias: null,
  },
};

export function scoreArticle(a, ctx) {
  const { profile, mood, timeContext, env } = ctx;
  const p = PROFILES[profile] || PROFILES["casual"];
  let reasons = [];

  // Cold start
  if (!p.topicWeights) {
    const topicCoverage = { Tech: 0.75, Finance: 0.75, Geopolitics: 0.8, Lifestyle: 0.7, Culture: 0.7, Health: 0.7 };
    let score = topicCoverage[a.topic] ?? 0.6;
    if (a.tone === "urgent") score += 0.15;
    score += (Math.sin(a.id * 1.3) + 1) * 0.04;
    reasons.push("Trending globally", "Diverse picks for new readers");
    return { score: Math.min(1, score), reasons };
  }

  const topicW = p.topicWeights[a.topic] ?? 0.1;
  const toneW = p.toneBias[a.tone] ?? 0.3;
  const lenW = p.lengthBias[a.length] ?? 0.5;
  let score = topicW * 0.55 + toneW * 0.22 + lenW * 0.13;

  if (topicW > 0.7) reasons.push(`Matches your interest in ${a.topic}`);

  if (timeContext === "morning") {
    if (a.length === "quick") { score += 0.1; reasons.push("Quick morning-rush brief"); }
    if (a.tone === "urgent" || a.tone === "serious") score += 0.04;
  } else if (timeContext === "deepwork") {
    if (a.length === "deep") { score += 0.14; reasons.push("Deep analytical format"); }
  } else if (timeContext === "evening") {
    if (a.length === "quick") { score += 0.1; reasons.push("Quick evening unwind"); }
  }

  const v = ctx.moodVector || { happy: 0.5, sad: 0, angry: 0, anxious: 0, calm: 0.5, curious: 0.5 };
  if (v.sad > 0.2) {
    if (["Culture", "Lifestyle", "Health"].includes(a.topic)) { score += v.sad * 0.2; reasons.push("Uplifting"); }
    if (a.topic === "Geopolitics") score -= v.sad * 0.25;
  }
  if (v.angry > 0.2) {
    if (["Tech", "Finance", "Lifestyle"].includes(a.topic)) { score += v.angry * 0.18; reasons.push("Focused cooling read"); }
    if (a.topic === "Geopolitics") score -= v.angry * 0.2;
  }
  if (v.anxious > 0.2) {
    if (["Health", "Lifestyle"].includes(a.topic)) { score += v.anxious * 0.2; reasons.push("Calming topic"); }
    if (["Geopolitics", "Finance"].includes(a.topic)) score -= v.anxious * 0.15;
  }
  if (v.calm > 0.2) {
    if (["Geopolitics", "Finance", "Tech"].includes(a.topic)) { score += v.calm * 0.12; reasons.push("Deep analytical read"); }
  }
  if (v.happy > 0.4) {
    if (["Culture", "Tech", "Lifestyle"].includes(a.topic)) { score += v.happy * 0.1; }
  }
  if (v.curious > 0.4) {
    if (["Tech", "Geopolitics", "Health"].includes(a.topic)) { score += v.curious * 0.12; reasons.push("High curiosity pick"); }
  }

  // Behavioral Affinity Logic
  if (ctx.affinity) {
    const topicAff = ctx.affinity[a.topic] || 0;
    score += Math.tanh(topicAff / 5) * 0.18;
    if (topicAff > 3) reasons.push("Top behavioral match");
  }

  // Biometric Mock Logic
  if (ctx.heartRate && ctx.heartRate > 95) {
    if (a.topic === "Geopolitics") score -= 0.3; // Panic suppression
    if (a.topic === "Health" || a.topic === "Lifestyle") { score += 0.2; reasons.push("Calming pulse pick"); }
  }

  const env_l = (env || "").toLowerCase();
  if (env_l) {
    if (env_l.match(/gym|run|walk|workout|cardio/)) {
      if (a.topic === "Health") { score += 0.14; reasons.push("Matches fitness context"); }
      if (a.length === "quick") score += 0.05;
    }
    if (env_l.match(/commut|train|subway|bus|car/)) {
      if (a.length === "quick") { score += 0.1; reasons.push("Bite-sized for your commute"); }
    }
    if (env_l.match(/office|desk|work/)) {
      if (a.topic === "Finance" || a.topic === "Tech") { score += 0.08; reasons.push("Work-context relevant"); }
    }
    if (env_l.match(/home|couch|bed|night/)) {
      if (a.tone === "relaxed") { score += 0.09; reasons.push("Evening / at-home read"); }
    }
    if (env_l.match(/market|trading|portfolio|stocks/)) {
      if (a.topic === "Finance") { score += 0.18; reasons.push("Market-context priority"); }
    }
  }

  score = Math.max(0.05, Math.min(0.99, score));
  if (reasons.length === 0) reasons.push("Based on your reading history");
  return { score, reasons: reasons.slice(0, 2) };
}

export function getRankedNews(profileStr, context) {
  const ctx = { profile: profileStr || "analyst", ...context };
  
  const scored = CORPUS.map(a => {
    const { score, reasons } = scoreArticle(a, ctx);
    return { ...a, score, reasons };
  });
  
  scored.sort((a, b) => b.score - a.score);
  return scored;
}
