import React, { useState, useEffect, useRef } from 'react';
import { Search, Menu, Play, Headphones, Bookmark, ThumbsUp, ThumbsDown, Watch } from 'lucide-react';
import { logInteraction, isBookmarked, saveBookmark, removeBookmark } from './engine.jsx';
import { playVoice, stopVoice } from './newsroom-voice.jsx';
import { recordInteraction } from './api.js';

// ── Dwell tracking ────────────────────────────────────────────
// 2 s visible at 50% → dwell_short   (quick glance, mild negative signal)
// 6 s visible at 50% → dwell_long    (actual read, strong positive signal)
function useDwell(a, rank) {
  const elRef   = useRef(null);
  const timerRef = useRef(null);
  const sentRef  = useRef(null); // null | 'dwell_short' | 'dwell_long'

  useEffect(() => {
    sentRef.current = null; // reset when article changes
  }, [a?.id]);

  useEffect(() => {
    const el = elRef.current;
    if (!el || !a?.id) return;

    const send = (action) => {
      if (sentRef.current === 'dwell_long') return;
      sentRef.current = action;
      logInteraction(action, a);
      const uid = localStorage.getItem("margin_uid");
      const sid = localStorage.getItem("margin_sid");
      if (uid && sid) recordInteraction(uid, sid, a.id, action, rank).catch(() => {});
    };

    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        timerRef.current = setTimeout(() => {
          send('dwell_short');
          timerRef.current = setTimeout(() => send('dwell_long'), 4000); // 2+4 = 6s total
        }, 2000);
      } else {
        clearTimeout(timerRef.current);
      }
    }, { threshold: 0.5 });

    observer.observe(el);
    return () => { observer.disconnect(); clearTimeout(timerRef.current); };
  }, [a?.id, rank]);

  return elRef;
}

function ActionRow({ a, size = 14, hideListen = false, rank = 1 }) {
  const [act, setAct] = useState(() => ({
    like: false, dislike: false, listen: false,
    save: a ? isBookmarked(a.id) : false,
  }));
  
  const handleAct = async (e, type) => {
    e.preventDefault();
    e.stopPropagation();
    const wasActive = act[type];
    setAct(p => ({ ...p, [type]: !p[type] }));
    
    const uid = localStorage.getItem("margin_uid");
    const sid = localStorage.getItem("margin_sid");

    if (!wasActive) {
      logInteraction(type, a);
      if (type === "save") saveBookmark(a);
      if (type === "listen") playVoice(a?.headline, a?.author, a?.topic);
      if (uid && sid && a?.id) {
        // rank position is not known here, defaulting to 1 for now
        let actionStr = type;
        if (type === "like") actionStr = "dwell_long";
        if (type === "dislike") actionStr = "skip";
        if (type === "save") actionStr = "share";
        if (type === "listen") actionStr = "dwell_long";
        recordInteraction(uid, sid, a.id, actionStr, rank).catch(e => console.error(e));
      }
    } else {
      if (type === "save") removeBookmark(a?.id);
      if (type === "listen") stopVoice();
    }
  };

  const btnStyle = (type) => ({
    background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center",
    transition: "transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)", 
    transform: act[type] ? "scale(1.2)" : "scale(1)", padding: 4, margin: -4, position: "relative", zIndex: 10
  });
  
  const iconProps = (type, onCol) => ({
    size,
    color: act[type] ? onCol : "var(--ink)",
    fill: act[type] ? onCol : "none",
    style: { pointerEvents: "none", opacity: act[type] ? 1 : 0.45, transition: "all 0.2s ease" }
  });

  return (
    <div style={{ display: "flex", gap: size * 0.8, alignItems: "center" }}>
      <button title="Like" onClick={(e) => handleAct(e, "like")} style={btnStyle("like")} aria-label="Like">
        <ThumbsUp {...iconProps("like", "#1E7A3A")} />
      </button>
      <button title="Dislike" onClick={(e) => handleAct(e, "dislike")} style={btnStyle("dislike")} aria-label="Dislike">
        <ThumbsDown {...iconProps("dislike", "#C21E3B")} />
      </button>
      <button title="Save" onClick={(e) => handleAct(e, "save")} style={btnStyle("save")} aria-label="Save">
        <Bookmark {...iconProps("save", "#B8860B")} />
      </button>
      {!hideListen && (
        <button title="Listen" onClick={(e) => handleAct(e, "listen")} style={btnStyle("listen")} aria-label="Listen">
          <Headphones size={size} color={act.listen ? "#C21E3B" : "var(--ink)"} style={{ pointerEvents: "none", opacity: act.listen ? 1 : 0.45, transition: "all 0.2s ease" }} strokeWidth={act.listen ? 2.5 : 2} />
        </button>
      )}
    </div>
  );
}

// ── Image placeholder ─────────────────────────────────────────
const CATEGORY_GRADIENTS = {
  AI:            { from: "#4F46E5", to: "#7C3AED" },
  Bitcoin:       { from: "#F59E0B", to: "#D97706" },
  Business:      { from: "#1E40AF", to: "#3B82F6" },
  Cricket:       { from: "#15803D", to: "#22C55E" },
  Crypto:        { from: "#7C3AED", to: "#A855F7" },
  Education:     { from: "#0E7490", to: "#06B6D4" },
  Elections:     { from: "#B91C1C", to: "#EF4444" },
  Entertainment: { from: "#BE185D", to: "#EC4899" },
  Environment:   { from: "#047857", to: "#10B981" },
  Finance:       { from: "#0369A1", to: "#0EA5E9" },
  Health:        { from: "#0F766E", to: "#14B8A6" },
  IPL:           { from: "#4D7C0F", to: "#84CC16" },
  Inflation:     { from: "#C2410C", to: "#F97316" },
  Markets:       { from: "#4338CA", to: "#6366F1" },
  Movies:        { from: "#7E22CE", to: "#A855F7" },
  OpenAI:        { from: "#18181B", to: "#3F3F46" },
  Politics:      { from: "#991B1B", to: "#DC2626" },
  Science:       { from: "#155E75", to: "#0891B2" },
  Sports:        { from: "#166534", to: "#16A34A" },
  Startups:      { from: "#5B21B6", to: "#7C3AED" },
  Technology:    { from: "#1E3A8A", to: "#2563EB" },
  Tesla:         { from: "#9F1239", to: "#E11D48" },
  War:           { from: "#450A0A", to: "#991B1B" },
  World:         { from: "#312E81", to: "#4F46E5" },
};

export function NewsImg({ a, ratio = "16 / 10", isHero = false }) {
  const category = a?.topic || "World";
  const grad = CATEGORY_GRADIENTS[category] || { from: "#374151", to: "#6B7280" };

  return (
    <div className="relative w-full overflow-hidden" style={{
      aspectRatio: ratio,
      background: `linear-gradient(135deg, ${grad.from} 0%, ${grad.to} 100%)`,
    }}>
      <div className="absolute inset-0 flex items-center justify-center">
        <span style={{
          fontFamily: "'Inter', sans-serif",
          fontSize: isHero ? 16 : 12,
          fontWeight: 700,
          letterSpacing: "0.3em",
          textTransform: "uppercase",
          color: "rgba(255,255,255,0.2)",
        }}>{category}</span>
      </div>
      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent pointer-events-none" />
      <div className="absolute bottom-0 left-0 right-0 p-[12px] flex items-center justify-center font-mono text-[10px] tracking-[0.25em] uppercase text-center text-white/90 pointer-events-none z-10 drop-shadow-md">
        [ {category} · #{String(a?.id || "0").slice(0, 5).padStart(3, "0")} ]
      </div>
    </div>
  );
}

// ── Match chip ────────────────────────────────────────────────
export function MatchChip({ pct, compact }) {
  return (
    <span className={`inline-flex items-center gap-1.5 border border-neutral-900 bg-white font-mono font-medium text-neutral-900 tracking-[0.15em] ${compact ? 'px-[7px] py-[2px] text-[9px]' : 'px-[9px] py-[3px] text-[10px]'}`}>
      <span className="w-[5px] h-[5px] rounded-full" style={{ background: pct > 85 ? "#1E7A3A" : pct > 65 ? "#B8860B" : "#888" }} />
      {pct}% MATCH
    </span>
  );
}

// ── Live clock ────────────────────────────────────────────────
export function NewsClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(t);
  }, []);

  const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  return (
    <span className="font-sans text-xs font-medium text-neutral-900">
      {days[now.getDay()]}, {months[now.getMonth()]} {now.getDate()}, {now.getFullYear()}
    </span>
  );
}

// ── Masthead ─────────────────────────────────────────────────
export function NewsMasthead({ brand }) {
  return (
    <div className="text-center pt-7 pb-3.5">
      <h1 className="font-serif text-[72px] leading-[0.95] m-0 tracking-[-0.02em] text-neutral-900 font-medium italic">
        {brand}
        <span className="not-italic ml-0.5 text-[#C21E3B]">*</span>
      </h1>
    </div>
  );
}

// ── Top bar ──────────────────────────────────────────────────
export function NewsTopBar({ onOpenFilter, onOpenSearch, onToggleMenu, region, onOpenAnalytics, onOpenBookmarks, onToggleWatch, ctx }) {
  return (
    <div className="flex justify-between items-center py-5">
      <div className="flex items-center gap-4">
        <NewsClock />
        {region && region !== "Global" && (
          <>
            <span className="text-neutral-900/20">|</span>
            <span className="font-sans text-[10px] font-bold tracking-[0.2em] uppercase flex items-center gap-[4px] text-neutral-900">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
              {region}
            </span>
          </>
        )}
      </div>
      <div className="flex gap-3 items-center">
        <button onClick={onToggleWatch} title="Connect Biometrics" className={`bg-transparent border ${ctx?.smartwatchConnected ? 'border-[#C21E3B] text-[#C21E3B]' : 'border-neutral-900 text-neutral-900'} p-1.5 cursor-pointer inline-flex items-center gap-1.5 justify-center hover:bg-neutral-900 hover:text-white transition-colors`}>
          <Watch size={14} className="stroke-[2]" />
          {ctx?.smartwatchConnected && <span className="font-sans text-[10px] font-bold tracking-[0.1em] uppercase pr-1">{ctx.heartRate || "--"} BPM</span>}
        </button>
        <button onClick={onOpenAnalytics} title="Behaviour Analytics" className="bg-transparent border border-neutral-900 p-1.5 cursor-pointer text-neutral-900 inline-flex items-center gap-1.5 justify-center hover:bg-neutral-900 hover:text-white transition-colors">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
          <span className="font-sans text-[10px] font-bold tracking-[0.2em] uppercase pr-1">Behaviour</span>
        </button>
        <button onClick={onOpenBookmarks} title="Saved Articles" className="bg-transparent border border-[#B8860B] p-1.5 cursor-pointer text-[#B8860B] inline-flex items-center gap-1.5 justify-center hover:bg-[#B8860B] hover:text-white transition-colors">
          <Bookmark size={14} className="stroke-[2]" />
          <span className="font-sans text-[10px] font-bold tracking-[0.2em] uppercase pr-1">Saved</span>
        </button>
        <span className="text-neutral-900/20">|</span>
        <button onClick={onOpenSearch} className="bg-transparent border border-neutral-900 p-1.5 cursor-pointer text-neutral-900 inline-flex items-center justify-center hover:bg-neutral-100 transition-colors">
          <Search size={14} className="stroke-[1.5]" />
        </button>
        <button onClick={onOpenFilter} title="Personalize feed" className="bg-transparent border border-neutral-900 p-1.5 cursor-pointer text-[#C21E3B] border-[#C21E3B] inline-flex items-center gap-1.5 justify-center hover:bg-[#C21E3B] hover:text-white transition-colors">
          <Menu size={14} className="stroke-[2]" />
          <span className="font-sans text-[10px] font-bold tracking-[0.2em] uppercase pr-1">Personalize</span>
        </button>
      </div>
    </div>
  );
}

// ── Nav ──────────────────────────────────────────────────────
export function NewsNav({ active, onChange, categories = [] }) {
  return (
    <nav className="flex py-3 border-y border-neutral-900 mb-10 overflow-x-auto" style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}>
      {categories.map((c, i) => (
        <button
          key={c}
          onClick={() => onChange && onChange(c)}
          className={`relative bg-transparent border-none cursor-pointer px-[14px] py-1 font-sans text-xs font-semibold text-neutral-900 whitespace-nowrap flex-shrink-0 ${c === active ? 'opacity-100' : 'opacity-70 hover:opacity-100'
            } ${i < categories.length - 1 ? 'border-r border-neutral-900/10' : ''}`}
        >
          {c}
          {c === active && (
            <span className="absolute left-1/2 -bottom-[13px] -translate-x-1/2 w-1 h-1 rounded-full bg-[#C21E3B]" />
          )}
        </button>
      ))}
    </nav>
  );
}

// ── Hero top story (bound to top-ranked article) ─────────
export function NewsHero({ a, match, rank = 1 }) {
  const [hov, setHov] = useState(false);
  const dwellRef = useDwell(a, rank);
  if (!a) return null;

  const handleArticleClick = () => {
    logInteraction("read", a);
    const url = a.canonical_url || a.url || a.link;
    if (url) window.open(url, '_blank');
  };

  return (
    <article ref={dwellRef} onClick={handleArticleClick} onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{ margin: "28px 0 18px", cursor: "pointer" }}>
      <div style={{ position: "relative", overflow: "hidden" }}>
        <div style={{
          transform: hov ? "scale(1.015)" : "scale(1)",
          transition: "transform 500ms cubic-bezier(.2,.7,.2,1)",
        }}>
          <NewsImg a={a} ratio="16 / 7.5" isHero={true} />
        </div>
        <div style={{
          position: "absolute", top: 0, left: 0,
          background: "var(--bone)", padding: "7px 12px",
          border: "1px solid var(--ink)", borderTop: "none", borderLeft: "none",
          fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 600,
          letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--ink)",
        }}>Top Story · #{String(a?.id).padStart(3, "0")}</div>
        <div style={{
          position: "absolute", top: 14, right: 14,
        }}>
          <MatchChip pct={match} />
        </div>
      </div>
      <div style={{ marginTop: 18, display: "flex", gap: 10, alignItems: "center" }}>
        <span style={{
          border: "1px solid var(--ink)", padding: "3px 9px",
          fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 600,
          letterSpacing: "0.2em", textTransform: "uppercase",
        }}>{a?.topic}</span>
        <span style={{
          fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 500,
          letterSpacing: "0.2em", textTransform: "uppercase", color: "var(--ink)", opacity: 0.55,
        }}>Top Pick · {a?.minutes} min</span>
      </div>
      <h2 style={{
        margin: "14px 0 10px",
        fontFamily: "'Playfair Display', serif",
        fontSize: 38, lineHeight: 1.15, fontWeight: 500,
        letterSpacing: "-0.01em", color: "var(--ink)",
        textWrap: "pretty", maxWidth: 920,
        textDecoration: hov ? "underline" : "none",
        textDecorationThickness: "1px", textUnderlineOffset: "6px",
      }}>{a?.headline}</h2>
      <p style={{
        margin: 0, maxWidth: 780,
        fontFamily: "'Inter', sans-serif", fontSize: 15, lineHeight: 1.6,
        color: "var(--ink)", opacity: 0.72,
      }}>{a?.summary}</p>
      <div style={{
        marginTop: 14, display: "flex", gap: 14, alignItems: "center",
        fontFamily: "'Inter', sans-serif", fontSize: 11,
        color: "var(--ink)", opacity: 0.6,
      }}>
        <span>By {a?.author}</span>
        <span>·</span>
        <span>{a?.source}</span>
        <span>·</span>
        <span>{a?.minutes} min read</span>
        
        <div style={{ marginLeft: 16 }}>
          <ActionRow a={a} size={18} rank={rank} />
        </div>

        <span style={{ marginLeft: "auto", opacity: 0.7 }}>— Read the full dispatch</span>
      </div>
    </article>
  );
}

// ── Section header ──────────────────────────────
export function NewsSection({ label, children, viewAll = true }) {
  return (
    <section style={{ marginTop: 56 }}>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "baseline",
        paddingBottom: 14, borderBottom: "1px solid var(--ink)", marginBottom: 24,
      }}>
        <h3 style={{
          margin: 0, fontFamily: "'Inter', sans-serif",
          fontSize: 13, fontWeight: 700, letterSpacing: "0.28em",
          textTransform: "uppercase", color: "var(--ink)",
        }}>{label}</h3>
        {viewAll && (
          <a href="#" style={{
            fontFamily: "'Inter', sans-serif", fontSize: 11, fontWeight: 500,
            letterSpacing: "0.2em", textTransform: "uppercase",
            color: "var(--ink)", opacity: 0.65, textDecoration: "none",
            display: "inline-flex", alignItems: "center", gap: 6,
          }}>View All <span style={{ fontSize: 14 }}>→</span></a>
        )}
      </div>
      {children}
    </section>
  );
}

// ── Story card (clean, no geometric shapes) ─────────
export function NewsCard({ a, variant = "compact", match, rank = 1 }) {
  const [hov, setHov] = useState(false);
  const dwellRef = useDwell(a, rank);
  if (!a) return null;
  const pct = match ?? Math.round((a?.score || 0) * 100);

  const handleArticleClick = () => {
    logInteraction("read", a);
    const url = a.canonical_url || a.url || a.link;
    if (url) window.open(url, '_blank');
  };

  if (variant === "row") {
    return (
      <article ref={dwellRef} onClick={handleArticleClick} onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
        style={{
          display: "grid", gridTemplateColumns: "1fr 140px", gap: 16,
          padding: "14px 0", borderBottom: "1px solid rgba(0,0,0,0.1)",
          cursor: "pointer",
        }}>
        <div>
          <div style={{
            fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 500,
            letterSpacing: "0.2em", color: "var(--ink)", opacity: 0.55, marginBottom: 8,
            display: "flex", justifyContent: "space-between", alignItems: "center"
          }}>
            <span>{a?.author} · {a?.minutes} min</span>
            <ActionRow a={a} size={14} rank={rank} />
          </div>
          <h4 style={{
            margin: "0 0 8px", fontFamily: "'Playfair Display', serif",
            fontSize: 17, fontWeight: 500, lineHeight: 1.3, color: "var(--ink)",
            textDecoration: hov ? "underline" : "none",
            textDecorationThickness: "1px", textUnderlineOffset: "4px",
          }}>{a?.headline}</h4>
          <MatchChip pct={pct} compact />
        </div>
        <NewsImg a={a} ratio="4 / 3" />
      </article>
    );
  }

  if (variant === "large") {
    return (
      <article ref={dwellRef} onClick={handleArticleClick} onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
        style={{ cursor: "pointer" }}>
        <div style={{ overflow: "hidden", position: "relative" }}>
          <div style={{
            transform: hov ? "scale(1.02)" : "scale(1)",
            transition: "transform 500ms cubic-bezier(.2,.7,.2,1)",
          }}>
            <NewsImg a={a} ratio="16 / 10" />
          </div>
          <div style={{ position: "absolute", top: 12, right: 12 }}>
            <MatchChip pct={pct} compact />
          </div>
        </div>
        <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            marginTop: 14, fontFamily: "'Inter', sans-serif", fontSize: 10,
            letterSpacing: "0.18em", color: "var(--ink)", opacity: 0.6, textTransform: "uppercase"
          }}>
            <div style={{ display: "flex", gap: 10 }}>
              <span>{a?.topic}</span>
              <span>·</span>
              <span>{a?.author}</span>
            </div>
            <ActionRow a={a} size={16} rank={rank} />
          </div>
          <h3 style={{
          margin: "8px 0 8px", fontFamily: "'Playfair Display', serif",
          fontSize: 22, fontWeight: 500, lineHeight: 1.25, color: "var(--ink)",
          textDecoration: hov ? "underline" : "none",
          textDecorationThickness: "1px", textUnderlineOffset: "4px",
        }}>{a?.headline}</h3>
        <p style={{
          margin: "0 0 10px", fontFamily: "'Inter', sans-serif", fontSize: 13,
          lineHeight: 1.55, color: "var(--ink)", opacity: 0.72,
          display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
        }}>{a?.summary}</p>
      </article>
    );
  }

  // compact
  return (
    <article ref={dwellRef} onClick={handleArticleClick} onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{ cursor: "pointer" }}>
      <div style={{ overflow: "hidden", position: "relative" }}>
        <div style={{
          transform: hov ? "scale(1.03)" : "scale(1)",
          transition: "transform 450ms cubic-bezier(.2,.7,.2,1)",
        }}>
          <NewsImg a={a} ratio="4 / 3" />
        </div>
        <div style={{ position: "absolute", top: 8, right: 8 }}>
          <MatchChip pct={pct} compact />
        </div>
      </div>
      <h4 style={{
        margin: "12px 0 6px", fontFamily: "'Playfair Display', serif",
        fontSize: 16, fontWeight: 500, lineHeight: 1.3, color: "var(--ink)",
        textDecoration: hov ? "underline" : "none",
        textDecorationThickness: "1px", textUnderlineOffset: "3px",
      }}>{a?.headline}</h4>
      <div style={{
        fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 500,
        letterSpacing: "0.18em", color: "var(--ink)", opacity: 0.55, textTransform: "uppercase",
        display: "flex", justifyContent: "space-between", alignItems: "center"
      }}>
        <span>{a?.author} · {a?.minutes} min</span>
        <ActionRow a={a} size={12} rank={rank} />
      </div>
    </article>
  );
}


// ── Footer ────────────────────────────────────────
export function NewsFooter({ brand }) {
  const socials = ["IG", "𝕏", "TT", "YT", "RSS"];
  return (
    <footer style={{ marginTop: 80, borderTop: "3px solid var(--ink)", paddingTop: 28 }}>
      <div style={{ textAlign: "center", padding: "8px 0 18px" }}>
        <h2 style={{
          fontFamily: "'Playfair Display', serif", fontStyle: "italic",
          fontSize: 32, margin: 0, fontWeight: 500, color: "var(--ink)",
          letterSpacing: "-0.01em",
        }}>
          {brand}<span style={{ fontStyle: "normal", color: "var(--accent)" }}>*</span>
        </h2>
      </div>
      <div style={{
        borderTop: "1px solid var(--ink)", padding: "16px 0",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        fontFamily: "'Inter', sans-serif", fontSize: 11,
      }}>
        <span style={{ color: "var(--ink)", opacity: 0.7 }}>
          Copyright © 2026 · {brand} · All rights reserved
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          {socials.map(s => (
            <a key={s} href="#" style={{
              width: 26, height: 26, border: "1px solid var(--ink)",
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
              color: "var(--ink)", textDecoration: "none",
            }}>{s}</a>
          ))}
        </div>
      </div>
    </footer>
  );
}
