import React from 'react';
import { BACKEND_ARCHETYPES, MoodSliders, defaultMoodVector } from './newsroom-onboarding.jsx';

// Off-canvas personalization drawer
const { useState: dUS } = React;

export default function PersonalizationDrawer({ open, onClose, context, onSave, confidence, latency }) {
  const [draft, setDraft] = dUS(context);
  React.useEffect(() => { if (open) setDraft(context); }, [open, context]);

  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, background: "rgba(15,15,15,0.35)",
        opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none",
        transition: "opacity 240ms",
        zIndex: 40,
      }} />
      <aside style={{
        position: "fixed", top: 0, right: 0, bottom: 0,
        width: "min(440px, 92vw)", background: "var(--bone)",
        borderLeft: "1px solid var(--ink)",
        transform: `translateX(${open ? "0" : "100%"})`,
        transition: "transform 320ms cubic-bezier(.2,.7,.2,1)",
        zIndex: 50, display: "flex", flexDirection: "column",
        boxShadow: open ? "-20px 0 40px rgba(0,0,0,0.15)" : "none",
      }}>
        <header style={{
          padding: "22px 26px", borderBottom: "1px solid var(--ink)",
          display: "flex", justifyItems: "space-between", justifyContent: "space-between", alignItems: "flex-start",
        }}>
          <div>
            <div style={{
              fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 600,
              letterSpacing: "0.22em", textTransform: "uppercase",
              color: "var(--ink)", opacity: 0.55, marginBottom: 6,
            }}>Personalization</div>
            <h2 style={{
              margin: 0, fontFamily: "'Playfair Display', serif",
              fontSize: 28, fontWeight: 500, letterSpacing: "-0.01em",
            }}>Tune your feed</h2>
          </div>
          <button onClick={onClose} aria-label="Close" style={{
            background: "transparent", border: "1px solid var(--ink)",
            width: 32, height: 32, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "var(--ink)",
          }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.4">
              <path d="M2 2 L10 10 M10 2 L2 10" />
            </svg>
          </button>
        </header>

        <div style={{
          flex: 1, overflowY: "auto", padding: "24px 26px",
          display: "flex", flexDirection: "column", gap: 28
        }}>

          <DrawerField label="User Profile" note="Switch simulated reader. New User triggers cold-start.">
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {Object.entries(BACKEND_ARCHETYPES).map(([id, p]) => (
                <button key={id} onClick={() => setDraft({ ...draft, profile: id })}
                  style={{
                    textAlign: "left", padding: "12px 14px",
                    background: draft.profile === id ? "var(--ink)" : "var(--bone)",
                    color: draft.profile === id ? "var(--bone)" : "var(--ink)",
                    border: "1px solid var(--ink)", cursor: "pointer",
                    display: "flex", flexDirection: "column", gap: 3,
                    transition: "all 140ms",
                  }}>
                  <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 13, fontWeight: 600 }}>
                    {p.name}
                  </span>
                  <span style={{
                    fontSize: 11, opacity: 0.75,
                    fontFamily: "'Inter', sans-serif", lineHeight: 1.4
                  }}>{p.bio}</span>
                </button>
              ))}
            </div>
          </DrawerField>

          <DrawerField label="Psychological Tone" note="Tune individual psychological vectors.">
            <MoodSliders 
              value={draft.moodVector || defaultMoodVector()} 
              onChange={v => setDraft({ ...draft, moodVector: v })} 
              onCommit={v => {
                const updatedDraft = { ...draft, moodVector: v };
                setDraft(updatedDraft);
                onSave(updatedDraft);
              }}
              compact 
            />
          </DrawerField>

          <DrawerField label="Time Context">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
              {[["morning", "Morning\nRush"], ["deepwork", "Deep\nWork"], ["evening", "Wind-\ndown"]].map(([v, l]) => (
                <button key={v} onClick={() => setDraft({ ...draft, timeContext: v })}
                  style={{
                    padding: "14px 8px", whiteSpace: "pre-line",
                    background: draft.timeContext === v ? "var(--ink)" : "var(--bone)",
                    color: draft.timeContext === v ? "var(--bone)" : "var(--ink)",
                    border: "1px solid var(--ink)", cursor: "pointer",
                    fontFamily: "'Inter', sans-serif", fontSize: 12, fontWeight: 500,
                    lineHeight: 1.3,
                  }}>{l}</button>
              ))}
            </div>
          </DrawerField>

          <DrawerField label="Environmental Signal"
            note="Try: gym, commute, desk, home, market.">
            <input value={draft.env || ''} onChange={e => setDraft({ ...draft, env: e.target.value })}
              placeholder="e.g. at the gym, on the train…"
              style={{
                width: "100%", padding: "12px 14px", marginBottom: 16,
                background: "transparent", border: "1px solid var(--ink)",
                color: "var(--ink)", fontSize: 13,
                fontFamily: "'Inter', sans-serif", outline: "none",
              }} />
          </DrawerField>

          <DrawerField label="Region Focus" note="Prioritize global or local lenses.">
            <select
              value={draft.region || "Global"}
              onChange={e => setDraft({ ...draft, region: e.target.value })}
              style={{
                width: "100%", padding: "12px 14px",
                background: "transparent", border: "1px solid var(--ink)",
                color: "var(--ink)", fontSize: 13,
                fontFamily: "'Inter', sans-serif", outline: "none", cursor: "pointer",
                WebkitAppearance: "none", appearance: "none"
              }}
            >
              <option value="Global">Global (no region bias)</option>
              <option value="India">India</option>
              <option value="US">United States</option>
              <option value="UK">United Kingdom</option>
            </select>
          </DrawerField>
        </div>

        <footer style={{
          padding: "18px 26px", borderTop: "1px solid var(--ink)",
          display: "flex", flexDirection: "column", gap: 14,
        }}>
          <div style={{
            fontFamily: "'Inter', sans-serif", fontSize: 11, fontWeight: 500,
            letterSpacing: "0.1em", textTransform: "uppercase",
            color: "var(--ink)", opacity: 0.6, textAlign: "center",
          }}>
            Generated in {latency}s · {Math.round(confidence * 100)}% confidence
          </div>
          <button onClick={() => { onSave(draft); onClose(); }}
            style={{
              padding: "14px 18px", background: "var(--ink)", color: "var(--bone)",
              border: "1px solid var(--ink)", cursor: "pointer",
              fontFamily: "'Inter', sans-serif", fontSize: 12, fontWeight: 600,
              letterSpacing: "0.22em", textTransform: "uppercase",
              transition: "background 140ms, color 140ms",
            }}
            onMouseEnter={e => { e.currentTarget.style.background = "var(--accent)"; }}
            onMouseLeave={e => { e.currentTarget.style.background = "var(--ink)"; }}
          >
            Save & Update Feed
          </button>
        </footer>
      </aside>
    </>
  );
}

function DrawerField({ label, note, children }) {
  return (
    <div>
      <div style={{
        fontFamily: "'Inter', sans-serif", fontSize: 11, fontWeight: 600,
        letterSpacing: "0.22em", textTransform: "uppercase",
        color: "var(--ink)", marginBottom: 6,
      }}>{label}</div>
      {note && <div style={{
        fontFamily: "'Inter', sans-serif", fontSize: 11, color: "var(--ink)",
        opacity: 0.6, marginBottom: 12, lineHeight: 1.5,
      }}>{note}</div>}
      {children}
    </div>
  );
}
