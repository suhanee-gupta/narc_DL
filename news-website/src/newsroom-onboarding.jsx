import React, { useState } from 'react';
export const BACKEND_ARCHETYPES = {
  cold_start: { name: "The New User", bio: "Start fresh and let the engine learn your preferences." },
  sports_fan: { name: "The Sports Fan", bio: "Prioritizes match updates, IPL, and athlete news." },
  sci_tech: { name: "The Technologist", bio: "Follows AI, startups, tech, and scientific breakthroughs." },
  finance_biz: { name: "The Market Watcher", bio: "Focuses on stocks, crypto, inflation, and business." },
  wellness: { name: "The Wellness Seeker", bio: "Interested in health, environment, and education." },
  world_watcher: { name: "The Global Citizen", bio: "Deep dives into geopolitics, world news, and elections." },
  foodie_lifestyle: { name: "The Culturist", bio: "Follows entertainment, movies, and lifestyle." }
};
export const MOOD_KEYS = ["happy", "sad", "angry", "anxious", "calm", "curious"];

export const META = {
  happy:   { emoji: "😊", hint: "Exploratory, general news" },
  sad:     { emoji: "😔", hint: "Uplifting, avoid tragedy" },
  angry:   { emoji: "😤", hint: "Tech & Finance, avoid politics" },
  anxious: { emoji: "😰", hint: "Calming reads, lifestyle/health" },
  calm:    { emoji: "😌", hint: "Deep dives, science, world" },
  curious: { emoji: "🤔", hint: "Tech, Geopolitics" },
};

export function defaultMoodVector() {
  return { happy: 0.5, sad: 0, angry: 0, anxious: 0, calm: 0.5, curious: 0.5 };
}

export function MoodSliders({ value, onChange, compact = false }) {
  const set = (k, v) => onChange({ ...value, [k]: v });

  return (
    <div style={{
      display: "grid", 
      gridTemplateColumns: compact ? "1fr" : "1fr 1fr", 
      gap: 16
    }}>
      {MOOD_KEYS.map(k => {
        const m = META[k];
        const pct = Math.round((value[k] || 0) * 100);
        return (
          <div key={k} style={{
            border: "1px solid var(--ink)",
            padding: "16px",
            background: "var(--bone)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, alignItems: "center" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <span style={{ fontSize: 16 }}>{m.emoji}</span>
                <span style={{ 
                  fontFamily: "'Inter', sans-serif", fontSize: 12, fontWeight: 600, 
                  textTransform: "uppercase", letterSpacing: "0.1em" 
                }}>{k}</span>
              </div>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>{pct}%</span>
            </div>
            
            <input 
              type="range" min="0" max="100" 
              value={pct} 
              onChange={e => set(k, e.target.value / 100)} 
              className="drawer-range"
              style={{ width: "100%", cursor: "ew-resize" }}
            />
            
            {!compact && (
              <div style={{ 
                marginTop: 10, fontFamily: "'Inter', sans-serif", fontSize: 11, 
                opacity: 0.65, lineHeight: 1.3 
              }}>
                {m.hint}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function NewsOnboarding({ onComplete }) {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState({
    profile: "cold_start",
    timeContext: "morning",
    env: "",
    region: "Global",
    moodVector: defaultMoodVector(),
  });

  const steps = ["welcome", "profile", "mood", "time"];
  const current = steps[step];

  const next = () => setStep(s => s + 1);
  const back = () => setStep(s => s - 1);
  const finish = () => onComplete(draft);

  const btnStyle = {
    padding: "14px 28px", background: "var(--ink)", color: "var(--bone)",
    border: "1px solid var(--ink)", cursor: "pointer",
    fontFamily: "'Inter', sans-serif", fontSize: 12, fontWeight: 600,
    letterSpacing: "0.22em", textTransform: "uppercase",
  };
  const ghostBtnStyle = {
    ...btnStyle, background: "transparent", color: "var(--ink)", border: "none",
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 100,
      background: "var(--bone)", color: "var(--ink)",
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      padding: 24, overflowY: "auto",
    }}>
      <div style={{ 
        width: "100%", maxWidth: 640, 
        padding: "40px 0",
        animation: "fadeIn 600ms ease"
      }}>
        
        {/* Progress Bar */}
        <div style={{ display: "flex", gap: 8, marginBottom: 40 }}>
          {steps.map((_, i) => (
            <div key={i} style={{
              flex: 1, height: 2,
              background: i <= step ? "var(--ink)" : "rgba(0,0,0,0.1)",
              transition: "background 300ms ease"
            }} />
          ))}
        </div>

        {current === "welcome" && (
          <div style={{ textAlign: "center", animation: "slideUp 500ms ease" }}>
            <h1 style={{
              fontFamily: "'Playfair Display', serif", fontSize: 48, fontWeight: 500,
              margin: "0 0 16px", letterSpacing: "-0.02em"
            }}>The Margin</h1>
            <p style={{
              fontFamily: "'Inter', sans-serif", fontSize: 15, opacity: 0.7,
              maxWidth: 400, margin: "0 auto 40px", lineHeight: 1.6
            }}>
              Your strictly personalized editorial feed. Let's calibrate your intelligence digest in three quick steps.
            </p>
            <button onClick={next} style={btnStyle}>Begin Calibration →</button>
          </div>
        )}

        {current === "profile" && (
          <div style={{ animation: "slideUp 500ms ease" }}>
            <h2 style={{
              fontFamily: "'Playfair Display', serif", fontSize: 32, fontWeight: 500, margin: "0 0 24px"
            }}>Identity & Interests</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 32 }}>
              {Object.entries(BACKEND_ARCHETYPES).map(([id, p]) => (
                <button key={id} onClick={() => setDraft({ ...draft, profile: id })}
                  style={{
                    textAlign: "left", padding: "18px 24px",
                    background: draft.profile === id ? "var(--ink)" : "transparent",
                    color: draft.profile === id ? "var(--bone)" : "var(--ink)",
                    border: "1px solid var(--ink)", cursor: "pointer",
                    transition: "all 150ms",
                  }}>
                  <div style={{ fontFamily: "'Inter', sans-serif", fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
                    {p.name}
                  </div>
                  <div style={{ fontFamily: "'Inter', sans-serif", fontSize: 13, opacity: 0.8, lineHeight: 1.4 }}>
                    {p.bio}
                  </div>
                </button>
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <button onClick={back} style={ghostBtnStyle}>← Back</button>
              <button onClick={next} style={btnStyle}>Continue</button>
            </div>
          </div>
        )}

        {current === "mood" && (
          <div style={{ animation: "slideUp 500ms ease" }}>
            <h2 style={{
              fontFamily: "'Playfair Display', serif", fontSize: 32, fontWeight: 500, margin: "0 0 8px"
            }}>Psychological Tone</h2>
            <p style={{
              fontFamily: "'Inter', sans-serif", fontSize: 14, opacity: 0.7, marginBottom: 24
            }}>
              Adjust these sliders to route the macro-categories. We heavily penalize topics that misalign with your current mental state.
            </p>
            <div className="mb-8" style={{ marginBottom: 32 }}>
              <MoodSliders 
                value={draft.moodVector} 
                onChange={(v) => setDraft({ ...draft, moodVector: v })} 
              />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <button onClick={back} style={ghostBtnStyle}>← Back</button>
              <button onClick={next} style={btnStyle}>Continue</button>
            </div>
          </div>
        )}

        {current === "time" && (
          <div style={{ animation: "slideUp 500ms ease" }}>
            <h2 style={{
              fontFamily: "'Playfair Display', serif", fontSize: 32, fontWeight: 500, margin: "0 0 24px"
            }}>Temporal Context</h2>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 32 }}>
              {[["morning", "Morning Rush"], ["deepwork", "Deep Work"], ["evening", "Wind-down"]].map(([v, l]) => (
                <button key={v} onClick={() => setDraft({ ...draft, timeContext: v })}
                  style={{
                    padding: "20px 14px",
                    background: draft.timeContext === v ? "var(--ink)" : "transparent",
                    color: draft.timeContext === v ? "var(--bone)" : "var(--ink)",
                    border: "1px solid var(--ink)", cursor: "pointer",
                    fontFamily: "'Inter', sans-serif", fontSize: 13, fontWeight: 600,
                  }}>
                  {l}
                </button>
              ))}
            </div>
            
            <h3 style={{
              fontFamily: "'Inter', sans-serif", fontSize: 11, fontWeight: 600,
              textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12
            }}>Region Focus</h3>
            <select
              value={draft.region}
              onChange={e => setDraft({ ...draft, region: e.target.value })}
              style={{
                width: "100%", padding: "16px", marginBottom: 24,
                background: "transparent", border: "1px solid var(--ink)",
                color: "var(--ink)", fontFamily: "'Inter', sans-serif", fontSize: 14,
                outline: "none", cursor: "pointer",
                WebkitAppearance: "none", appearance: "none"
              }}
            >
              <option value="Global">Global Perspective</option>
              <option value="North America">North America</option>
              <option value="Europe">Europe</option>
              <option value="Asia-Pacific">Asia-Pacific</option>
              <option value="Local Area">Local Area Focus</option>
            </select>

            <h3 style={{
              fontFamily: "'Inter', sans-serif", fontSize: 11, fontWeight: 600,
              textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12
            }}>Environmental Signal (Optional)</h3>
            <input 
              value={draft.env} onChange={e => setDraft({ ...draft, env: e.target.value })}
              placeholder="e.g. gym, commute, desk..."
              style={{
                width: "100%", padding: "16px", marginBottom: 32,
                background: "transparent", border: "1px solid var(--ink)",
                color: "var(--ink)", fontFamily: "'Inter', sans-serif", fontSize: 14,
                outline: "none"
              }}
            />

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <button onClick={back} style={ghostBtnStyle}>← Back</button>
              <button onClick={finish} style={{ ...btnStyle, background: "var(--accent)", borderColor: "var(--accent)" }}>
                Initialize Feed
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
