import React, { useState, useEffect } from 'react';
import { loadBookmarks, removeBookmark } from './engine.jsx';
import { Bookmark, X, Trash2 } from 'lucide-react';

const fmtTime = (ts) => {
  const d = new Date(ts);
  const m = Math.floor((Date.now() - ts) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  if (m < 1440) return `${Math.floor(m / 60)}h ago`;
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
};

export default function BookmarksDrawer({ open, onClose }) {
  const [bookmarks, setBookmarks] = useState([]);

  useEffect(() => {
    const refresh = () => setBookmarks(loadBookmarks());
    if (open) refresh();
    window.addEventListener("margin:bookmarks", refresh);
    return () => window.removeEventListener("margin:bookmarks", refresh);
  }, [open]);

  const handleRemove = (id) => {
    removeBookmark(id);
  };

  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, background: "rgba(15,15,15,0.35)",
        opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none",
        transition: "opacity 240ms", zIndex: 40,
      }} />
      <aside style={{
        position: "fixed", top: 0, right: 0, bottom: 0,
        width: "min(420px, 92vw)", background: "var(--bone)",
        borderLeft: "1px solid var(--ink)", color: "var(--ink)",
        transform: `translateX(${open ? "0" : "100%"})`,
        transition: "transform 320ms cubic-bezier(.2,.7,.2,1)",
        zIndex: 50, display: "flex", flexDirection: "column",
        boxShadow: open ? "-20px 0 40px rgba(0,0,0,0.15)" : "none",
      }}>
        <header style={{
          padding: "22px 26px", borderBottom: "1px solid var(--ink)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div>
            <div style={{
              fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 600,
              letterSpacing: "0.22em", textTransform: "uppercase", opacity: 0.55, marginBottom: 6,
            }}>Your Collection</div>
            <h2 style={{
              margin: 0, fontFamily: "'Playfair Display', serif",
              fontSize: 28, fontWeight: 500, letterSpacing: "-0.01em",
              display: "flex", alignItems: "center", gap: 12,
            }}>
              <Bookmark size={22} color="#B8860B" fill="#B8860B" style={{ opacity: 0.8 }} />
              Saved Articles
            </h2>
          </div>
          <button onClick={onClose} aria-label="Close" style={{
            background: "transparent", border: "1px solid var(--ink)",
            width: 32, height: 32, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "var(--ink)",
          }}>
            <X size={14} />
          </button>
        </header>

        <div style={{
          flex: 1, overflowY: "auto", padding: "20px 26px",
        }}>
          {bookmarks.length === 0 && (
            <div style={{
              textAlign: "center", padding: "60px 20px",
              display: "flex", flexDirection: "column", alignItems: "center", gap: 16,
            }}>
              <Bookmark size={40} color="var(--ink)" style={{ opacity: 0.15 }} />
              <p style={{
                fontFamily: "'Inter', sans-serif", fontSize: 14, opacity: 0.5,
                lineHeight: 1.6, maxWidth: 260,
              }}>
                No saved articles yet. Tap the bookmark icon on any article to save it here.
              </p>
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {bookmarks.map((b, idx) => (
              <article key={b.id} style={{
                padding: "18px 0",
                borderBottom: idx < bookmarks.length - 1 ? "1px solid rgba(0,0,0,0.08)" : "none",
                display: "flex", gap: 14, alignItems: "flex-start",
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    display: "flex", gap: 8, alignItems: "center", marginBottom: 6,
                    fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 500,
                    letterSpacing: "0.15em", textTransform: "uppercase", opacity: 0.55,
                  }}>
                    <span style={{
                      background: "#B8860B", color: "#fff", padding: "1px 6px",
                      fontSize: 9, fontWeight: 700, letterSpacing: "0.1em",
                    }}>{b.topic}</span>
                    <span>{b.author}</span>
                    <span>·</span>
                    <span>{b.minutes} min</span>
                  </div>
                  <h4 style={{
                    margin: "0 0 6px", fontFamily: "'Playfair Display', serif",
                    fontSize: 16, fontWeight: 500, lineHeight: 1.3, color: "var(--ink)",
                  }}>{b.headline}</h4>
                  {b.summary && (
                    <p style={{
                      margin: 0, fontFamily: "'Inter', sans-serif", fontSize: 12,
                      lineHeight: 1.5, opacity: 0.6,
                      display: "-webkit-box", WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical", overflow: "hidden",
                    }}>{b.summary}</p>
                  )}
                  <div style={{
                    marginTop: 8, fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 10, opacity: 0.4,
                  }}>
                    Saved {fmtTime(b.savedAt)}
                  </div>
                </div>
                <button
                  onClick={() => handleRemove(b.id)}
                  title="Remove bookmark"
                  style={{
                    background: "transparent", border: "1px solid rgba(0,0,0,0.15)",
                    width: 30, height: 30, cursor: "pointer", flexShrink: 0,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: "var(--ink)", opacity: 0.4,
                    transition: "all 0.2s ease",
                    marginTop: 4,
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.opacity = "1"; e.currentTarget.style.borderColor = "#C21E3B"; e.currentTarget.style.color = "#C21E3B"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.opacity = "0.4"; e.currentTarget.style.borderColor = "rgba(0,0,0,0.15)"; e.currentTarget.style.color = "var(--ink)"; }}
                >
                  <Trash2 size={13} />
                </button>
              </article>
            ))}
          </div>
        </div>

        <footer style={{
          padding: "16px 26px", borderTop: "1px solid var(--ink)",
          fontFamily: "'Inter', sans-serif", fontSize: 11,
          display: "flex", justifyContent: "space-between", alignItems: "center",
          opacity: 0.6,
        }}>
          <span>{bookmarks.length} article{bookmarks.length !== 1 ? "s" : ""} saved</span>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>
            margin_bookmarks
          </span>
        </footer>
      </aside>
    </>
  );
}
