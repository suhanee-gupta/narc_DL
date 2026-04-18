import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Search, X, Clock, TrendingUp, ArrowRight } from 'lucide-react';
import { CORPUS } from './engine.jsx';

export default function SearchOverlay({ open, onClose, onSelectArticle }) {
  const [query, setQuery] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
    if (!open) setQuery("");
  }, [open]);

  // Escape key closes
  useEffect(() => {
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    if (open) window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  const suggestions = useMemo(() => {
    if (!query || query.length < 2) return [];
    const q = query.toLowerCase();
    return CORPUS
      .filter(a => a.headline?.toLowerCase().includes(q) || a.topic?.toLowerCase().includes(q) || a.author?.toLowerCase().includes(q))
      .slice(0, 8);
  }, [query]);

  const trendingTopics = ["Tech", "Finance", "Geopolitics", "Health", "Culture", "Lifestyle"];

  const handleSelect = (article) => {
    onSelectArticle(article);
    onClose();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (suggestions.length > 0) {
      handleSelect(suggestions[0]);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose} style={{
        position: "fixed", inset: 0,
        background: "rgba(10,10,10,0.6)",
        backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
        opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none",
        transition: "opacity 300ms ease", zIndex: 60,
      }} />

      {/* Search Panel */}
      <div style={{
        position: "fixed", top: 0, left: 0, right: 0,
        zIndex: 70,
        transform: open ? "translateY(0)" : "translateY(-100%)",
        transition: "transform 350ms cubic-bezier(.2,.7,.2,1)",
        pointerEvents: open ? "auto" : "none",
      }}>
        <div style={{
          maxWidth: 720, margin: "0 auto", padding: "40px 24px 0",
        }}>
          {/* Search Input */}
          <form onSubmit={handleSubmit} style={{
            background: "var(--bone, #fff)", border: "2px solid var(--ink, #111)",
            display: "flex", alignItems: "center", gap: 14,
            padding: "18px 22px",
            boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
          }}>
            <Search size={20} color="var(--ink, #111)" style={{ opacity: 0.4, flexShrink: 0 }} />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search articles, topics, authors..."
              style={{
                flex: 1, border: "none", outline: "none", background: "transparent",
                fontFamily: "'Playfair Display', serif", fontSize: 22, fontWeight: 400,
                color: "var(--ink, #111)", letterSpacing: "-0.01em",
              }}
            />
            {query && (
              <button type="button" onClick={() => setQuery("")} style={{
                background: "none", border: "none", cursor: "pointer",
                display: "flex", padding: 4, opacity: 0.4,
              }}>
                <X size={18} color="var(--ink, #111)" />
              </button>
            )}
            <button type="button" onClick={onClose} style={{
              background: "var(--ink, #111)", border: "none", color: "#fff",
              padding: "8px 16px", cursor: "pointer",
              fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 600,
              letterSpacing: "0.2em", textTransform: "uppercase",
            }}>ESC</button>
          </form>

          {/* Results / Suggestions */}
          <div style={{
            background: "var(--bone, #fff)", borderLeft: "2px solid var(--ink, #111)",
            borderRight: "2px solid var(--ink, #111)", borderBottom: "2px solid var(--ink, #111)",
            maxHeight: "60vh", overflowY: "auto",
            boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
          }}>
            {/* Live suggestions */}
            {query.length >= 2 && suggestions.length > 0 && (
              <div style={{ padding: "8px 0" }}>
                <div style={{
                  padding: "10px 22px 8px",
                  fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 600,
                  letterSpacing: "0.2em", textTransform: "uppercase", opacity: 0.45,
                }}>
                  {suggestions.length} result{suggestions.length !== 1 ? "s" : ""} found
                </div>
                {suggestions.map((a) => (
                  <button
                    key={a.id}
                    onClick={() => handleSelect(a)}
                    style={{
                      display: "flex", alignItems: "flex-start", gap: 14,
                      width: "100%", textAlign: "left",
                      padding: "14px 22px",
                      background: "transparent", border: "none",
                      cursor: "pointer",
                      transition: "background 150ms ease",
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = "rgba(0,0,0,0.04)"}
                    onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        display: "flex", gap: 8, alignItems: "center", marginBottom: 4,
                      }}>
                        <span style={{
                          fontFamily: "'Inter', sans-serif", fontSize: 9, fontWeight: 700,
                          letterSpacing: "0.1em", textTransform: "uppercase",
                          background: "var(--ink, #111)", color: "var(--bone, #fff)",
                          padding: "2px 6px",
                        }}>{a.topic}</span>
                        <span style={{
                          fontFamily: "'Inter', sans-serif", fontSize: 10,
                          opacity: 0.5, fontWeight: 500,
                        }}>{a.author} · {a.minutes} min</span>
                      </div>
                      <div style={{
                        fontFamily: "'Playfair Display', serif", fontSize: 16,
                        fontWeight: 500, lineHeight: 1.3, color: "var(--ink, #111)",
                        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                      }}>
                        {highlightMatch(a.headline, query)}
                      </div>
                    </div>
                    <ArrowRight size={14} style={{ opacity: 0.25, marginTop: 8, flexShrink: 0 }} />
                  </button>
                ))}
              </div>
            )}

            {/* No results */}
            {query.length >= 2 && suggestions.length === 0 && (
              <div style={{
                padding: "40px 22px", textAlign: "center",
              }}>
                <p style={{
                  fontFamily: "'Inter', sans-serif", fontSize: 13, opacity: 0.5, margin: 0,
                }}>No articles found for "{query}"</p>
              </div>
            )}

            {/* Empty state — trending topics */}
            {query.length < 2 && (
              <div style={{ padding: "16px 22px 20px" }}>
                <div style={{
                  display: "flex", alignItems: "center", gap: 8, marginBottom: 14,
                  fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 600,
                  letterSpacing: "0.2em", textTransform: "uppercase", opacity: 0.45,
                }}>
                  <TrendingUp size={12} />
                  Trending Topics
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {trendingTopics.map(t => (
                    <button key={t} onClick={() => setQuery(t)} style={{
                      padding: "8px 16px", background: "transparent",
                      border: "1px solid rgba(0,0,0,0.15)", cursor: "pointer",
                      fontFamily: "'Inter', sans-serif", fontSize: 12, fontWeight: 500,
                      color: "var(--ink, #111)",
                      transition: "all 150ms ease",
                    }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--ink, #111)"; e.currentTarget.style.color = "#fff"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--ink, #111)"; }}
                    >
                      {t}
                    </button>
                  ))}
                </div>

                <div style={{
                  display: "flex", alignItems: "center", gap: 8, marginTop: 20, marginBottom: 10,
                  fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 600,
                  letterSpacing: "0.2em", textTransform: "uppercase", opacity: 0.45,
                }}>
                  <Clock size={12} />
                  Quick Tips
                </div>
                <p style={{
                  fontFamily: "'Inter', sans-serif", fontSize: 12, opacity: 0.5,
                  lineHeight: 1.6, margin: 0,
                }}>
                  Search by headline, topic name, or author. Results appear as you type.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function highlightMatch(text, query) {
  if (!text || !query) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <span style={{ background: "rgba(194,30,59,0.15)", color: "#C21E3B", fontWeight: 600 }}>
        {text.slice(idx, idx + query.length)}
      </span>
      {text.slice(idx + query.length)}
    </>
  );
}
