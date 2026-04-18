import React, { useState, useEffect } from 'react';
import { aggregateStats, loadLog } from './engine.jsx';

const { useState: dUS, useEffect: dUE } = React;

const Bar = ({ label, value, max }) => (
  <div style={{ marginBottom: 12 }}>
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontFamily: "'Inter', sans-serif", marginBottom: 4 }}>
      <span style={{ textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>{label}</span>
      <span style={{ opacity: 0.6 }}>{value}</span>
    </div>
    <div style={{ height: 4, background: "rgba(0,0,0,0.1)", width: "100%" }}>
      <div style={{ height: "100%", background: "var(--ink)", width: `${max ? (value / max) * 100 : 0}%`, transition: "width 0.5s ease" }} />
    </div>
  </div>
);

const fmtTime = (ts) => {
  const d = new Date(ts);
  const m = Math.floor((Date.now() - ts) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

export default function AnalyticsDrawer({ open, onClose }) {
  const [log, setLog] = dUS([]);

  dUE(() => {
    const refresh = () => setLog(loadLog());
    if (open) refresh();
    window.addEventListener("margin:log", refresh);
    return () => window.removeEventListener("margin:log", refresh);
  }, [open]);

  const stats = aggregateStats(log);
  const maxC = Math.max(1, ...Object.values(stats.byTopic));
  const maxT = Math.max(1, ...Object.values(stats.byType));

  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, background: "rgba(15,15,15,0.35)",
        opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none",
        transition: "opacity 240ms", zIndex: 40,
      }} />
      <aside style={{
        position: "fixed", top: 0, left: 0, bottom: 0,
        width: "min(380px, 92vw)", background: "var(--bone)",
        borderRight: "1px solid var(--ink)", color: "var(--ink)",
        transform: `translateX(${open ? "0" : "-100%"})`,
        transition: "transform 320ms cubic-bezier(.2,.7,.2,1)",
        zIndex: 50, display: "flex", flexDirection: "column",
        boxShadow: open ? "20px 0 40px rgba(0,0,0,0.15)" : "none",
      }}>
        <header style={{
          padding: "22px 26px", borderBottom: "1px solid var(--ink)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div>
            <div style={{
              fontFamily: "'Inter', sans-serif", fontSize: 10, fontWeight: 600,
              letterSpacing: "0.22em", textTransform: "uppercase", opacity: 0.55, marginBottom: 6,
            }}>The Ledger</div>
            <h2 style={{
              margin: 0, fontFamily: "'Playfair Display', serif",
              fontSize: 28, fontWeight: 500, letterSpacing: "-0.01em",
            }}>Behavior Log</h2>
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
          display: "flex", flexDirection: "column", gap: 32
        }}>
          <section style={{ border: "1px solid var(--ink)", padding: "16px", background: "transparent" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <h3 style={{ fontFamily: "'Inter', sans-serif", fontSize: 12, fontWeight: 600, textTransform: "uppercase", margin: 0 }}>Signals captured</h3>
            </div>
            <p style={{ fontFamily: "'Playfair Display', serif", fontSize: 36, margin: "0 0 4px", lineHeight: 1 }}>{stats.total}</p>
            <p style={{ fontFamily: "'Inter', sans-serif", fontSize: 11, margin: 0, opacity: 0.7 }}>across {Object.keys(stats.byTopic).length} categories</p>
          </section>

          <section>
            <h3 style={{ fontFamily: "'Inter', sans-serif", fontSize: 11, fontWeight: 600, textTransform: "uppercase", opacity: 0.6, marginBottom: 16 }}>By category</h3>
            <div>
              {Object.entries(stats.byTopic).sort((a,b) => b[1]-a[1]).map(([k, v]) => (
                <Bar key={k} label={k} value={v} max={maxC} />
              ))}
              {!Object.keys(stats.byTopic).length && <p style={{ fontSize: 12, opacity: 0.6, fontFamily: "'Inter', sans-serif" }}>No interactions yet.</p>}
            </div>
          </section>

          <section>
            <h3 style={{ fontFamily: "'Inter', sans-serif", fontSize: 11, fontWeight: 600, textTransform: "uppercase", opacity: 0.6, marginBottom: 16 }}>By interaction</h3>
            <div>
              {Object.entries(stats.byType).sort((a,b) => b[1]-a[1]).map(([k, v]) => (
                <Bar key={k} label={k} value={v} max={maxT} />
              ))}
            </div>
          </section>

          <section>
            <h3 style={{ fontFamily: "'Inter', sans-serif", fontSize: 11, fontWeight: 600, textTransform: "uppercase", opacity: 0.6, marginBottom: 16 }}>Recent activity</h3>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
              {log.slice(0, 20).map((i, idx) => (
                <li key={idx} style={{ 
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  borderBottom: "1px dotted rgba(0,0,0,0.2)", paddingBottom: 8
                }}>
                  <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 12 }}>
                    <span style={{ fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>{i.type}</span> · <span style={{ opacity: 0.8 }}>{i.topic}</span>
                  </span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, opacity: 0.5 }}>{fmtTime(i.ts)}</span>
                </li>
              ))}
              {!log.length && <p style={{ fontSize: 12, opacity: 0.6, fontFamily: "'Inter', sans-serif" }}>Interact with cards to start your log.</p>}
            </ul>
          </section>
        </div>
      </aside>
    </>
  );
}
