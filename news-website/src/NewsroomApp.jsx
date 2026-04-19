import React, { useState, useEffect, useMemo } from "react";

import PersonalizationDrawer from "./PersonalizationDrawer.jsx";
import AnalyticsDrawer from "./AnalyticsDrawer.jsx";
import BookmarksDrawer from "./BookmarksDrawer.jsx";
import SearchOverlay from "./SearchOverlay.jsx";
import { BACKEND_ARCHETYPES, NewsOnboarding, defaultMoodVector } from "./newsroom-onboarding.jsx";
import {
  NewsTopBar, NewsMasthead, NewsNav,
  NewsHero, NewsSection, NewsCard, NewsFooter,
  NewsImg, MatchChip
} from "./newsroom-content.jsx";
import { TOPICS, mapBackendToFrontend } from "./engine.jsx";
import { startSession, fetchRecommendations } from "./api.js";



export default function NewsroomApp() {
  const BRAND = "The Margin";
  const [onboarded, setOnboarded] = useState(false);
  const [activeCat, setActiveCat] = useState("Home");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [analyticsOpen, setAnalyticsOpen] = useState(false);
  const [bookmarksOpen, setBookmarksOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchResult, setSearchResult] = useState(null);
  const [reranking, setReranking] = useState(false);
  const [ranked, setRanked] = useState([]);
  const [latencySec, setLatencySec] = useState(0);
  const [sessionId, setSessionId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const userId = useMemo(() => {
    let id = localStorage.getItem("margin_uid");
    if (!id) {
      id = "user_" + Math.random().toString(36).substring(2, 10);
      localStorage.setItem("margin_uid", id);
    }
    return id;
  }, []);

  const [ctx, setCtx] = useState(() => {
    try {
      const stored = localStorage.getItem("margin_ctx");
      return stored ? JSON.parse(stored) : { 
        profile: "cold_start", timeContext: "morning", env: "", region: "Global", moodVector: defaultMoodVector() 
      };
    } catch {
      return { profile: "cold_start", timeContext: "morning", env: "", region: "Global", moodVector: defaultMoodVector() };
    }
  });

  const handleOnboardingComplete = (newCtx) => {
    setCtx(newCtx);
    localStorage.setItem("margin_ctx", JSON.stringify(newCtx));
    localStorage.setItem("margin_onb", "1");
    setOnboarded(true);
  };

  console.log("NewsroomApp rendering. drawerOpen=", drawerOpen);

  useEffect(() => {
    if (!onboarded) return;
    let isMounted = true;
    
    async function loadFeed() {
      setReranking(true);
      try {
        // 1. Start or update session
        const sessRes = await startSession(userId, ctx.moodVector, ctx.region, ctx.profile);
        setSessionId(sessRes.session_id);
        localStorage.setItem("margin_sid", sessRes.session_id);
        
        // 2. Fetch recommendations
        const recs = await fetchRecommendations(userId, sessRes.session_id, activeCat);
        if (!isMounted) return;
        
        setRanked(recs.articles.map(mapBackendToFrontend));
        setLatencySec(recs.latency_sec);
      } catch (err) {
        console.error("Failed to load feed:", err);
      } finally {
        if (isMounted) setReranking(false);
      }
    }
    loadFeed();
    return () => { isMounted = false; };
  }, [ctx, onboarded, userId, activeCat, refreshKey]);

  const confidence = useMemo(() => {
    if (ctx.profile === "cold_start") return 0.50;
    const top = ranked.slice(0, 8);
    if (top.length === 0) return 0.5;
    return top.reduce((s, a) => s + (a.score || 0.8), 0) / top.length;
  }, [ranked, ctx.profile]);

  useEffect(() => {
    if (!ctx.smartwatchConnected) return;
    const id = setInterval(() => {
      const hr = Math.round(65 + Math.random() * 40);
      setCtx(c => ({ ...c, heartRate: hr }));
    }, 3000);
    return () => clearInterval(id);
  }, [ctx.smartwatchConnected]);

  const cssVars = {
    "--bone": "#FFFFFF",
    "--ink": "#111111",
    "--accent": "#C21E3B",
  };

  // The backend already correctly filters categories via the fast-loop API.
  const hero = ranked[0];
  const gridA_large = ranked[1];
  const gridA_side = ranked.slice(2, 4); 
  const gridB_compact = ranked.slice(4, 7); 
  const gridC_main = ranked[7];
  const gridC_side = ranked.slice(8, 11); 
  const gridD_compact = ranked.slice(11, 15);

  if (!onboarded) {
    return (
      <div style={{ ...cssVars, background: "var(--bone)", minHeight: "100vh", fontFamily: "'Inter', sans-serif" }}>
        <NewsOnboarding onComplete={handleOnboardingComplete} />
      </div>
    );
  }

  const handleUpdateFeed = (newCtx) => {
    setCtx(newCtx);
    localStorage.setItem("margin_ctx", JSON.stringify(newCtx));
  };

  return (
    <div style={{
      ...cssVars, background: "var(--bone)", minHeight: "100vh",
      fontFamily: "'Inter', sans-serif", color: "var(--ink)"
    }}>
      <div style={{ maxWidth: 1240, margin: "0 auto", padding: "0 48px" }}>
        <NewsTopBar
          onOpenFilter={() => setDrawerOpen(true)}
          onOpenAnalytics={() => setAnalyticsOpen(true)}
          onOpenBookmarks={() => setBookmarksOpen(true)}
          onToggleWatch={() => {
            const next = !ctx.smartwatchConnected;
            const newCtx = { ...ctx, smartwatchConnected: next, heartRate: next ? 75 : undefined };
            setCtx(newCtx);
            localStorage.setItem("margin_ctx", JSON.stringify(newCtx));
          }}
          ctx={ctx}
          onOpenSearch={() => setSearchOpen(true)}
          onToggleMenu={() => { }}
          region={ctx.region}
        />
        <NewsMasthead brand={BRAND} />

        {/* Single-article search result view */}
        {searchResult ? (
          <>
            <div style={{
              marginTop: 16, marginBottom: 24,
              display: "flex", alignItems: "center", gap: 14,
            }}>
              <button onClick={() => setSearchResult(null)} style={{
                background: "var(--ink)", color: "var(--bone)",
                border: "none", padding: "10px 22px", cursor: "pointer",
                fontFamily: "'Inter', sans-serif", fontSize: 11, fontWeight: 600,
                letterSpacing: "0.18em", textTransform: "uppercase",
                display: "flex", alignItems: "center", gap: 8,
              }}>← Back to Feed</button>
              <span style={{
                fontFamily: "'Inter', sans-serif", fontSize: 11,
                letterSpacing: "0.15em", textTransform: "uppercase",
                opacity: 0.5, fontWeight: 500,
              }}>Search Result</span>
            </div>
            <main>
              <NewsHero a={searchResult} match={Math.round((searchResult?.score || 0.75) * 100)} />
              <NewsFooter brand={BRAND} />
            </main>
          </>
        ) : (
          <>
        <NewsNav active={activeCat} onChange={setActiveCat}
          categories={["Home", ...TOPICS]} />

        {/* Re-rank status line */}
        <div style={{
          marginTop: 8, padding: "10px 14px",
          border: "1px solid rgba(0,0,0,0.12)",
          display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16,
          fontFamily: "'Inter', sans-serif", fontSize: 11,
          letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--ink)",
        }}>
          <div style={{ display: "flex", gap: 14, alignItems: "center", minWidth: 0, flexWrap: "wrap" }}>
            <span style={{
              width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
              background: reranking ? "var(--accent)" : "#1E7A3A",
              animation: reranking ? "blink 0.6s ease-in-out infinite alternate" : "none",
            }} />
            <span style={{ fontWeight: 600 }}>
              {reranking ? "Re-ranking feed…" : `Feed tuned for ${BACKEND_ARCHETYPES[ctx.profile]?.name || "You"}`}
            </span>
            <span style={{ opacity: 0.45 }}>·</span>
            <span style={{ opacity: 0.7 }}>{Math.round(confidence * 100)}% match</span>
            <span style={{ opacity: 0.45 }}>·</span>
            <span style={{ opacity: 0.7 }}>
              {ctx.timeContext === "morning" ? "Morning rush" :
                ctx.timeContext === "deepwork" ? "Deep work" : "Wind-down"}
            </span>
          </div>
          <button
            onClick={() => !reranking && setRefreshKey(k => k + 1)}
            disabled={reranking}
            style={{
              background: "none",
              border: "1px solid rgba(0,0,0,0.25)",
              cursor: reranking ? "not-allowed" : "pointer",
              fontFamily: "'Inter', sans-serif",
              fontSize: 10, fontWeight: 600,
              letterSpacing: "0.18em", textTransform: "uppercase",
              color: "var(--ink)", padding: "5px 13px",
              display: "flex", alignItems: "center", gap: 7,
              opacity: reranking ? 0.35 : 1,
              transition: "opacity 0.2s ease, background 0.15s ease",
              flexShrink: 0,
            }}
            onMouseEnter={e => { if (!reranking) e.currentTarget.style.background = "var(--ink)", e.currentTarget.style.color = "var(--bone)"; }}
            onMouseLeave={e => { e.currentTarget.style.background = "none"; e.currentTarget.style.color = "var(--ink)"; }}
          >
            <span style={{
              display: "inline-block",
              animation: reranking ? "spin 1s linear infinite" : "none",
              fontSize: 12, lineHeight: 1,
            }}>↺</span>
            Refresh Feed
          </button>
        </div>

        {reranking && ranked.length === 0 ? (
          <div style={{ marginTop: 40, opacity: 0.6, animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite" }}>
            <div style={{ height: 420, background: "rgba(0,0,0,0.04)", marginBottom: 40 }} />
            <div style={{ display: "grid", gridTemplateColumns: "1.15fr 1fr", gap: 40 }}>
              <div style={{ height: 320, background: "rgba(0,0,0,0.04)" }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                 <div style={{ height: 96, background: "rgba(0,0,0,0.04)" }} />
                 <div style={{ height: 96, background: "rgba(0,0,0,0.04)" }} />
                 <div style={{ height: 96, background: "rgba(0,0,0,0.04)" }} />
              </div>
            </div>
          </div>
        ) : (
        <main
          className={reranking ? "opacity-40 transition-opacity duration-500 pointer-events-none" : "transition-opacity duration-500"}
        >
        {hero && <NewsHero a={hero} match={Math.round((hero?.score || 0) * 100)} />}

        {/* Latest */}
        <NewsSection label="Top Recommended">
          <div style={{
            display: "grid", gridTemplateColumns: "1.15fr 1fr", gap: 40,
            animation: reranking ? "fadeIn 500ms ease" : "none",
          }}>
            {gridA_large && <NewsCard a={gridA_large} variant="large" match={Math.round((gridA_large?.score || 0) * 100)} />}
            <div style={{ display: "flex", flexDirection: "column" }}>
              {gridA_side.map(a => (
                a && <NewsCard key={a.id} a={a} variant="row" match={Math.round((a?.score || 0) * 100)} />
              ))}
            </div>
          </div>
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 30,
            marginTop: 34, paddingTop: 30, borderTop: "1px solid rgba(0,0,0,0.1)",
            animation: reranking ? "fadeIn 500ms ease" : "none",
          }}>
            {gridB_compact.map(a => (
              a && <NewsCard key={a.id} a={a} variant="compact" match={Math.round((a?.score || 0) * 100)} />
            ))}
          </div>
        </NewsSection>

        {/* World */}
        <NewsSection label="Deep Dive Focus">
          <div style={{
            display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 36,
            animation: reranking ? "fadeIn 500ms ease" : "none",
          }}>
            {gridC_main && (
            <article style={{ display: "flex", flexDirection: "column" }}>
              <NewsImg a={gridC_main} ratio="4 / 3" />
              <div style={{
                transform: "translateY(-40px)", margin: "0 auto",
                background: "var(--bone)", padding: "18px 22px", maxWidth: 420,
                border: "1px solid var(--ink)",
              }}>
                <h3 style={{
                  margin: 0, fontFamily: "'Playfair Display', serif",
                  fontSize: 22, fontWeight: 500, lineHeight: 1.25, color: "var(--ink)",
                }}>{gridC_main.headline}</h3>
                <div style={{
                  marginTop: 10,
                  fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 500,
                  letterSpacing: "0.18em", color: "var(--ink)", opacity: 0.6,
                  textTransform: "uppercase"
                }}>
                  By {gridC_main.author} · {gridC_main.minutes} min
                </div>
              </div>
            </article>
            )}
            <div style={{ display: "flex", flexDirection: "column" }}>
              {gridC_side.map(a => (
                a && <NewsCard key={a.id} a={a} variant="row" match={Math.round((a?.score || 0) * 100)} />
              ))}
            </div>
          </div>
        </NewsSection>

        {/* Technology */}
        <NewsSection label="Keep Exploring">
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 24,
            animation: reranking ? "fadeIn 500ms ease" : "none",
          }}>
            {gridD_compact.map(a => (
              a && <NewsCard key={a.id} a={a} variant="compact" match={Math.round((a?.score || 0) * 100)} />
            ))}
          </div>
        </NewsSection>



        <NewsFooter brand={BRAND} />
        </main>
        )}
          </>
        )}
      </div>

      <PersonalizationDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        context={ctx}
        onSave={handleUpdateFeed}
        confidence={confidence}
        latency={latencySec}
      />
      <AnalyticsDrawer 
        open={analyticsOpen} 
        onClose={() => setAnalyticsOpen(false)} 
      />
      <BookmarksDrawer
        open={bookmarksOpen}
        onClose={() => setBookmarksOpen(false)}
      />
      <SearchOverlay
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSelectArticle={(a) => setSearchResult(a)}
      />
    </div>
  );
}
