import { useState, useEffect, useCallback, useRef } from "react";

// ── CONFIG ─────────────────────────────────────────────────────────────────────
const BRAIN    = "http://100.64.166.22:8182";
const GATEWAY  = "http://100.112.63.25:8282";
const ENDPOINT = "http://100.87.223.31:4001";
const REFRESH_S = 30;

// ── DESIGN TOKENS ──────────────────────────────────────────────────────────────
const C = {
  bg:        "#0d0d0d",
  surface:   "#141414",
  panel:     "#1a1a1a",
  border:    "#252525",
  borderHi:  "#3a3a3a",
  accent:    "#c6f135",
  accentDim: "#c6f13514",
  green:     "#22c55e",
  greenDim:  "#22c55e18",
  amber:     "#f5a623",
  amberDim:  "#f5a62318",
  red:       "#ef4444",
  redDim:    "#ef444418",
  blue:      "#38bdf8",
  blueDim:   "#38bdf818",
  text:      "#e2e2e2",
  textDim:   "#aaaaaa",
  muted:     "#555555",
  dim:       "#2a2a2a",
};

const PROVIDER_COLORS = {
  endpoint_llama: "#22c55e",
  qwen:           "#22c55e",
  scrape:         "#38bdf8",
  perplexity:     "#f5a623",
  claude:         "#c6f135",
};

const PROVIDER_LABELS = {
  endpoint_llama: "Llama 3.1",
  qwen:           "Qwen 2.5",
  scrape:         "Web Scrape",
  perplexity:     "Perplexity",
  claude:         "Claude",
};

// ── GLOBAL CSS ─────────────────────────────────────────────────────────────────
const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,400&family=Syne:wght@400;500;600;700;800&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body, #root { height: 100%; }
  body {
    background: #0d0d0d;
    color: #e2e2e2;
    font-family: 'Syne', sans-serif;
    font-size: 14px;
    overflow-x: hidden;
  }
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: #141414; }
  ::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 2px; }
  ::-webkit-scrollbar-thumb:hover { background: #3a3a3a; }
  .mono { font-family: 'DM Mono', monospace; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  @keyframes fadeUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:none} }
  @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
  .fade-up { animation: fadeUp 0.3s ease; }
  input, textarea { outline: none; }
  button { outline: none; }
  input[type=range] { -webkit-appearance: none; appearance: none; height: 4px; border-radius: 2px; background: #2a2a2a; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%; background: #c6f135; cursor: pointer; }
`;

// ── PRIMITIVE COMPONENTS ───────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const configs = {
    ONLINE:   { bg: "#22c55e", fg: "#000", label: "ONLINE" },
    RUNNING:  { bg: "#22c55e", fg: "#000", label: "RUNNING" },
    LIVE:     { bg: "#22c55e", fg: "#000", label: "LIVE" },
    ACTIVE:   { bg: "#22c55e", fg: "#000", label: "ACTIVE" },
    PASS:     { bg: "#22c55e", fg: "#000", label: "PASS" },
    STABLE:   { bg: "#22c55e", fg: "#000", label: "STABLE" },
    WARN:     { bg: "#f5a623", fg: "#000", label: "WARN" },
    WARNING:  { bg: "#f5a623", fg: "#000", label: "WARN" },
    TODO:     { bg: "#f5a623", fg: "#000", label: "TODO" },
    DEGRADED: { bg: "#f5a623", fg: "#000", label: "DEGRADED" },
    IDLE:     { bg: "#f5a623", fg: "#000", label: "IDLE" },
    ERROR:    { bg: "#ef4444", fg: "#fff", label: "ERROR" },
    FAIL:     { bg: "#ef4444", fg: "#fff", label: "FAIL" },
    CRITICAL: { bg: "#ef4444", fg: "#fff", label: "CRITICAL" },
    OFFLINE:  { bg: "#ef4444", fg: "#fff", label: "OFFLINE" },
    OPEN:     { bg: "#ef4444", fg: "#fff", label: "TRIPPED" },
    CLOSED:   { bg: "#22c55e", fg: "#000", label: "HEALTHY" },
    INACTIVE: { bg: "#333",    fg: "#888", label: "IDLE" },
    INFO:     { bg: "#38bdf8", fg: "#000", label: "INFO" },
  };
  const cfg = configs[status?.toUpperCase()] || { bg: "#333", fg: "#aaa", label: status || "—" };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      padding: "3px 10px", borderRadius: 20,
      background: cfg.bg, color: cfg.fg,
      fontSize: 10, fontWeight: 700, letterSpacing: 1,
      fontFamily: "'DM Mono', monospace", whiteSpace: "nowrap",
    }}>{cfg.label}</span>
  );
}

function Bar({ pct, warn = 75, crit = 90, height = 5, forceColor }) {
  const color = forceColor || (pct >= crit ? C.red : pct >= warn ? C.amber : C.green);
  return (
    <div style={{ position: "relative", height, background: C.dim, borderRadius: 4, overflow: "hidden" }}>
      <div style={{
        width: `${Math.min(pct || 0, 100)}%`, height: "100%",
        background: color, borderRadius: 4,
        transition: "width 0.8s cubic-bezier(0.4,0,0.2,1)",
      }} />
    </div>
  );
}

function Card({ children, style = {}, status }) {
  const borderColor = status === "error" ? C.red + "55"
                    : status === "warn"  ? C.amber + "55"
                    : status === "ok"    ? C.green + "33"
                    : C.border;
  return (
    <div style={{
      background: C.panel,
      border: `1px solid ${borderColor}`,
      borderRadius: 14, padding: "18px 20px",
      ...style,
    }}>{children}</div>
  );
}

function Accordion({ title, icon, defaultOpen = false, badgeText, badgeColor, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden", marginBottom: 8 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 12,
          padding: "14px 18px",
          background: open ? C.surface : C.panel,
          border: "none", cursor: "pointer",
          transition: "background 0.2s",
        }}
      >
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{
          flex: 1, textAlign: "left",
          fontFamily: "'Syne', sans-serif", fontWeight: 600, fontSize: 14, color: C.text,
        }}>{title}</span>
        {badgeText && (
          <span style={{
            padding: "2px 9px", borderRadius: 20,
            background: badgeColor || C.accent,
            color: "#000", fontSize: 10, fontWeight: 700,
            fontFamily: "'DM Mono', monospace",
          }}>{badgeText}</span>
        )}
        <span style={{
          color: C.muted, fontSize: 11,
          display: "inline-block",
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform 0.25s",
        }}>▼</span>
      </button>
      <div style={{
        maxHeight: open ? "3000px" : "0",
        overflow: "hidden",
        transition: open ? "max-height 0.5s ease-in" : "max-height 0.25s ease-out",
      }}>
        <div style={{ padding: "18px", borderTop: `1px solid ${C.border}` }}>
          {children}
        </div>
      </div>
    </div>
  );
}

function ActionBtn({ children, onClick, variant = "default", disabled = false, loading = false, size = "md" }) {
  const colors = {
    default: [C.accent, C.accentDim],
    danger:  [C.red,    C.redDim],
    success: [C.green,  C.greenDim],
    warning: [C.amber,  C.amberDim],
    ghost:   [C.muted,  C.dim],
  };
  const [color, bg] = colors[variant] || colors.default;
  const pad = size === "sm" ? "4px 10px" : "7px 16px";
  const fs  = size === "sm" ? 11 : 12;
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        padding: pad, borderRadius: 8,
        cursor: disabled || loading ? "not-allowed" : "pointer",
        border: `1px solid ${color}55`, background: "transparent",
        color, fontFamily: "'Syne', sans-serif", fontWeight: 600,
        fontSize: fs, letterSpacing: 0.5,
        opacity: disabled ? 0.4 : 1,
        transition: "all 0.15s", whiteSpace: "nowrap",
      }}
      onMouseEnter={e => { if (!disabled && !loading) e.currentTarget.style.background = bg; }}
      onMouseLeave={e => { if (!disabled && !loading) e.currentTarget.style.background = "transparent"; }}
    >
      {loading ? "···" : children}
    </button>
  );
}

function StatCard({ label, value, sub, color, icon }) {
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 14, padding: "20px",
    }}>
      <div style={{
        fontSize: 10, letterSpacing: 2, color: C.muted,
        fontFamily: "'DM Mono', monospace", textTransform: "uppercase",
        display: "flex", alignItems: "center", gap: 6, marginBottom: 10,
      }}>
        {icon && <span>{icon}</span>}{label}
      </div>
      <div style={{
        fontFamily: "'DM Mono', monospace", fontSize: 32,
        fontWeight: 500, color: color || C.accent, lineHeight: 1,
      }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontFamily: "'DM Mono', monospace", fontSize: 10,
      letterSpacing: 2.5, color: C.muted, textTransform: "uppercase",
      marginBottom: 14, display: "flex", alignItems: "center", gap: 10,
    }}>
      <span style={{ flex: 1, height: 1, background: C.border }} />
      {children}
      <span style={{ flex: 1, height: 1, background: C.border }} />
    </div>
  );
}

function MonoInput({ value, onChange, placeholder, type = "text", style = {} }) {
  return (
    <input
      type={type}
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: "100%", padding: "8px 12px",
        background: C.surface, border: `1px solid ${C.borderHi}`,
        borderRadius: 8, color: C.text,
        fontFamily: "'DM Mono', monospace", fontSize: 12,
        ...style,
      }}
    />
  );
}

// ── API LAYER ──────────────────────────────────────────────────────────────────
async function apiFetch(url, opts = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 6000);
  try {
    const r = await fetch(url, {
      ...opts,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    });
    clearTimeout(timer);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return [await r.json(), null];
  } catch (e) {
    clearTimeout(timer);
    return [null, e.name === "AbortError" ? "timeout" : e.message];
  }
}

// ── LIVE DATA HOOK ─────────────────────────────────────────────────────────────
function useJarvisData() {
  const [data, setData]               = useState(null);
  const [errors, setErrors]           = useState({});
  const [lastRefresh, setLastRefresh] = useState(null);
  const [refreshing, setRefreshing]   = useState(false);
  const [countdown, setCountdown]     = useState(REFRESH_S);
  const countRef = useRef(REFRESH_S);

  const fetch_all = useCallback(async () => {
    setRefreshing(true);
    const errs = {}, results = {};

    const fetches = [
      [`${BRAIN}/v1/health/full`,              "health"],
      [`${BRAIN}/v1/costs`,                    "costs"],
      [`${BRAIN}/v1/code/log`,                 "codeLog"],
      [`${BRAIN}/v1/agents`,                   "agents"],
      [`${BRAIN}/v1/metrics`,                  "brainMetrics"],
      [`${GATEWAY}/v1/metrics`,                "gwMetrics"],
      [`${ENDPOINT}/v1/metrics`,               "epMetrics"],
      [`${ENDPOINT}/v1/local/health`,          "ollamaHealth"],
      [`${BRAIN}/v1/router/stats`,             "routingStats"],
      [`${BRAIN}/v1/router/decisions?limit=15`,"routingDecisions"],
      [`${BRAIN}/v1/briefing`,                "briefing"],
      [`${BRAIN}/v1/overnight/runs`,           "overnightRuns"],
      [`${BRAIN}/v1/overnight/instructions`,   "overnightInstructions"],
      [`${BRAIN}/v1/overnight/docs`,           "overnightDocs"],
      [`${BRAIN}/v1/unraid/health`,            "unraidHealth"],
    ];

    await Promise.all(fetches.map(async ([url, key]) => {
      const [val, err] = await apiFetch(url);
      if (val !== null) results[key] = val;
      else errs[key] = err;
    }));

    setData(prev => ({ ...prev, ...results }));
    setErrors(errs);
    setLastRefresh(new Date());
    setRefreshing(false);
  }, []);

  useEffect(() => {
    fetch_all();
    const tick = setInterval(() => {
      countRef.current -= 1;
      setCountdown(countRef.current);
      if (countRef.current <= 0) {
        countRef.current = REFRESH_S;
        setCountdown(REFRESH_S);
        fetch_all();
      }
    }, 1000);
    return () => clearInterval(tick);
  }, [fetch_all]);

  const refresh = useCallback(() => {
    countRef.current = REFRESH_S;
    setCountdown(REFRESH_S);
    fetch_all();
  }, [fetch_all]);

  return { data, errors, lastRefresh, refreshing, refresh, countdown };
}
function OvernightTab({ data }) {
  const runs = data?.overnightRuns || [];
  const instructions = data?.overnightInstructions || [];
  const docs = data?.overnightDocs || [];
  const briefing = data?.briefing || {};
  const summaries = briefing.summaries || [];
  const budget = briefing.budget_yesterday || {};

  const [newInstruction, setNewInstruction] = useState("");
  const [replaceMode, setReplaceMode] = useState(null);
  const [docFile, setDocFile] = useState(null);
  const [docType, setDocType] = useState("architecture");
  const [uploadStatus, setUploadStatus] = useState("");
  const [instrStatus, setInstrStatus] = useState("");
  const [hearStatus, setHearStatus] = useState("");

  const passCount = runs.filter(r => r.status === "pass").length;
  const failCount = runs.filter(r => r.status === "fail").length;

  const submitInstruction = async () => {
    if (!newInstruction.trim()) return;
    if (replaceMode === null) { setInstrStatus("Please choose Replace or Keep"); return; }
    try {
      await fetch(`${BRAIN}/v1/overnight/instructions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instructions: newInstruction, replace_previous: replaceMode })
      });
      setNewInstruction("");
      setReplaceMode(null);
      setInstrStatus("✅ Saved");
      setTimeout(() => setInstrStatus(""), 3000);
    } catch (e) {
      setInstrStatus("❌ Failed to save");
    }
  };

  const deleteInstruction = async (id) => {
    await fetch(`${BRAIN}/v1/overnight/instructions/${id}`, { method: "DELETE" });
    setInstrStatus("Deleted");
    setTimeout(() => setInstrStatus(""), 2000);
  };

  const uploadDoc = async () => {
    if (!docFile) { setUploadStatus("No file selected"); return; }
    const reader = new FileReader();
    reader.onload = async (e) => {
      const content = e.target.result;
      try {
        await fetch(`${BRAIN}/v1/overnight/docs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename: docFile.name, content, doc_type: docType })
        });
        setUploadStatus("✅ Uploaded: " + docFile.name);
        setDocFile(null);
        setTimeout(() => setUploadStatus(""), 4000);
      } catch (err) {
        setUploadStatus("❌ Upload failed");
      }
    };
    reader.readAsText(docFile);
  };

  const deleteDoc = async (id) => {
    await fetch(`${BRAIN}/v1/overnight/docs/${id}`, { method: "DELETE" });
    setUploadStatus("Doc deleted");
    setTimeout(() => setUploadStatus(""), 2000);
  };

  const hearBriefing = async () => {
    setHearStatus("⏳ Fetching...");
    try {
      const token = localStorage.getItem("jarvis_token") || "";
      const res = await fetch(`${BRAIN}/v1/briefing`, { headers: { Authorization: `Bearer ${token}` } });
      const briefData = await res.json();
      const text = briefData.summary || briefData.text || JSON.stringify(briefData).slice(0, 500);
      const ttsRes = await fetch("http://100.87.223.31:4002/v1/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, user_id: "ken" })
      });
      if (!ttsRes.ok) throw new Error("TTS failed");
      const blob = await ttsRes.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play();
      setHearStatus("🔊 Playing...");
      audio.onended = () => setHearStatus("");
    } catch (err) {
      setHearStatus("❌ " + err.message);
      setTimeout(() => setHearStatus(""), 4000);
    }
  };

  return (
    <div className="fade-up" style={{ display: "grid", gap: 16 }}>
      <Card>
        <SectionLabel>Overnight Agent — Last Run Stats</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 16 }}>
          <div style={{ padding: "12px 16px", background: C.surface, borderRadius: 10, border: `1px solid ${C.border}` }}>
            <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", letterSpacing: 2, marginBottom: 8 }}>YESTERDAY SPEND</div>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 24, color: C.green }}>${parseFloat(budget.total_spend||0).toFixed(4)}</div>
            <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 4 }}>{budget.total_calls||0} API calls</div>
          </div>
          <div style={{ padding: "12px 16px", background: C.surface, borderRadius: 10, border: `1px solid ${C.border}` }}>
            <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", letterSpacing: 2, marginBottom: 8 }}>TASKS PASSED</div>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 24, color: C.green }}>✅ {passCount}</div>
          </div>
          <div style={{ padding: "12px 16px", background: C.surface, borderRadius: 10, border: `1px solid ${C.border}` }}>
            <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", letterSpacing: 2, marginBottom: 8 }}>TASKS FAILED</div>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 24, color: C.red }}>❌ {failCount}</div>
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
          <button onClick={hearBriefing} style={{ padding: "8px 18px", background: C.accent, color: "#000", border: "none", borderRadius: 8, fontFamily: "'DM Mono', monospace", fontSize: 11, cursor: "pointer", fontWeight: 700 }}>
            🔊 Hear Morning Briefing
          </button>
          {hearStatus && <span style={{ marginLeft: 12, fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace", alignSelf: "center" }}>{hearStatus}</span>}
        </div>
      </Card>

      <Card>
        <SectionLabel>Task Run Log</SectionLabel>
        <div style={{ display: "grid", gap: 8, maxHeight: 320, overflowY: "auto" }}>
          {runs.length === 0 && <div style={{ fontSize: 12, color: C.muted, fontFamily: "'DM Mono', monospace" }}>No runs recorded yet</div>}
          {runs.map((r, i) => (
            <div key={r.id||i} style={{ display: "grid", gridTemplateColumns: "60px 1fr 80px 70px", gap: 10, padding: "10px 14px", background: C.surface, border: `1px solid ${r.status === "pass" ? "#00ff8833" : "#ff444433"}`, borderRadius: 8, alignItems: "center" }}>
              <div style={{ fontSize: 18, textAlign: "center" }}>{r.status === "pass" ? "✅" : "❌"}</div>
              <div>
                <div style={{ fontSize: 12, color: C.text, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>{r.task_name}</div>
                {r.summary && <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 3 }}>{r.summary}</div>}
              </div>
              <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{r.run_date}</div>
              <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{r.duration_seconds ? `${r.duration_seconds}s` : "—"}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <SectionLabel>Tonight's Instructions</SectionLabel>
        <div style={{ marginBottom: 12 }}>
          <textarea
            value={newInstruction}
            onChange={e => setNewInstruction(e.target.value)}
            placeholder="What should JARVIS work on tonight? Be specific."
            style={{ width: "100%", minHeight: 80, background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text, fontFamily: "'DM Mono', monospace", fontSize: 12, padding: 10, resize: "vertical", boxSizing: "border-box" }}
          />
          <div style={{ display: "flex", gap: 10, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>Mode:</span>
            <button onClick={() => setReplaceMode(true)} style={{ padding: "6px 14px", background: replaceMode === true ? C.accent : C.surface, color: replaceMode === true ? "#000" : C.text, border: `1px solid ${C.border}`, borderRadius: 6, fontFamily: "'DM Mono', monospace", fontSize: 11, cursor: "pointer" }}>Replace Previous</button>
            <button onClick={() => setReplaceMode(false)} style={{ padding: "6px 14px", background: replaceMode === false ? C.blue : C.surface, color: replaceMode === false ? "#fff" : C.text, border: `1px solid ${C.border}`, borderRadius: 6, fontFamily: "'DM Mono', monospace", fontSize: 11, cursor: "pointer" }}>Keep & Stack</button>
            <button onClick={submitInstruction} style={{ padding: "6px 18px", background: C.green, color: "#000", border: "none", borderRadius: 6, fontFamily: "'DM Mono', monospace", fontSize: 11, cursor: "pointer", fontWeight: 700, marginLeft: "auto" }}>Save Instruction</button>
            {instrStatus && <span style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{instrStatus}</span>}
          </div>
        </div>
        <div style={{ display: "grid", gap: 8, maxHeight: 200, overflowY: "auto" }}>
          {instructions.length === 0 && <div style={{ fontSize: 12, color: C.muted, fontFamily: "'DM Mono', monospace" }}>No instructions saved</div>}
          {instructions.map((instr, i) => (
            <div key={instr.id||i} style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", padding: "10px 14px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8 }}>
              <div>
                <div style={{ fontSize: 12, color: C.text, fontFamily: "'DM Mono', monospace", lineHeight: 1.5 }}>{instr.instructions}</div>
                <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 4 }}>{instr.replace_previous ? "REPLACE" : "STACK"} · {new Date(instr.created_at).toLocaleString()}</div>
              </div>
              <button onClick={() => deleteInstruction(instr.id)} style={{ marginLeft: 12, padding: "4px 10px", background: "transparent", color: C.red, border: `1px solid ${C.red}`, borderRadius: 6, fontFamily: "'DM Mono', monospace", fontSize: 10, cursor: "pointer" }}>DEL</button>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <SectionLabel>Reference Documents</SectionLabel>
        <div style={{ display: "flex", gap: 10, marginBottom: 12, alignItems: "center", flexWrap: "wrap" }}>
          <input type="file" accept=".md,.txt,.pdf,.json" onChange={e => setDocFile(e.target.files[0])} style={{ color: C.text, fontFamily: "'DM Mono', monospace", fontSize: 11, flex: 1 }} />
          <select value={docType} onChange={e => setDocType(e.target.value)} style={{ padding: "6px 10px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, color: C.text, fontFamily: "'DM Mono', monospace", fontSize: 11 }}>
            <option value="architecture">Architecture</option>
            <option value="handoff">Handoff</option>
            <option value="design">Design Doc</option>
            <option value="reference">Reference</option>
            <option value="other">Other</option>
          </select>
          <button onClick={uploadDoc} style={{ padding: "6px 18px", background: C.blue, color: "#fff", border: "none", borderRadius: 6, fontFamily: "'DM Mono', monospace", fontSize: 11, cursor: "pointer", fontWeight: 700 }}>Upload</button>
          {uploadStatus && <span style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{uploadStatus}</span>}
        </div>
        <div style={{ display: "grid", gap: 8, maxHeight: 240, overflowY: "auto" }}>
          {docs.length === 0 && <div style={{ fontSize: 12, color: C.muted, fontFamily: "'DM Mono', monospace" }}>No documents uploaded yet</div>}
          {docs.map((doc, i) => (
            <div key={doc.id||i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8 }}>
              <div>
                <div style={{ fontSize: 12, color: C.text, fontFamily: "'DM Mono', monospace", fontWeight: 700 }}>{doc.filename}</div>
                <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 3 }}>{doc.doc_type.toUpperCase()} · {new Date(doc.uploaded_at).toLocaleString()}</div>
              </div>
              <button onClick={() => deleteDoc(doc.id)} style={{ padding: "4px 10px", background: "transparent", color: C.red, border: `1px solid ${C.red}`, borderRadius: 6, fontFamily: "'DM Mono', monospace", fontSize: 10, cursor: "pointer" }}>DEL</button>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ── SUMMARY TAB ────────────────────────────────────────────────────────────────
function SummaryTab({ data, errors }) {
  const costs        = data?.costs || {};
  const agents       = data?.agents || [];
  const codeLog      = data?.codeLog || [];
  const ollamaHealth = data?.ollamaHealth || {};
  const health       = data?.health || {};

  const daily     = costs.budget?.daily;
  const dailyPct  = daily  ? (daily.spent_usd  / daily.limit_usd  * 100) : 0;
  const weeklyPct = costs.budget?.weekly  ? (costs.budget.weekly.spent_usd  / costs.budget.weekly.limit_usd  * 100) : 0;
  const monthPct  = costs.budget?.monthly ? (costs.budget.monthly.spent_usd / costs.budget.monthly.limit_usd * 100) : 0;

  const nodes = [
    { name: "BRAIN",    metrics: data?.brainMetrics, err: errors.brainMetrics },
    { name: "GATEWAY",  metrics: data?.gwMetrics,    err: errors.gwMetrics },
    { name: "ENDPOINT", metrics: data?.epMetrics,    err: errors.epMetrics },
  ];
  const nodesOnline = nodes.filter(n => n.metrics && !n.err).length;
  const activeAgents = agents.filter(a => a.status === "ACTIVE").length;
  const briefing = data?.briefing || {};
  const briefingSummaries = briefing.summaries || [];
  const budgetYesterday = briefing.budget_yesterday || {};
  const routingYesterday = briefing.routing_yesterday || {};

  return (
    <div className="fade-up" style={{ display: "grid", gap: 16 }}>
      {/* KPI strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
        <StatCard label="Nodes Online"  value={`${nodesOnline}/3`}    color={nodesOnline===3?C.green:C.red} icon="🖥️" />
        <StatCard label="Today Spend"   value={`$${(daily?.spent_usd||0).toFixed(4)}`} color={dailyPct>=90?C.red:dailyPct>=75?C.amber:C.green} icon="💰" sub={`of $${(daily?.limit_usd||0).toFixed(2)} limit`} />
        <StatCard label="Active Agents" value={activeAgents}           color={C.blue}   icon="🤖" />
        <StatCard label="Models Loaded" value={ollamaHealth?.model_count ?? "—"} color={C.accent} icon="⚡" sub="on Endpoint" />
      </div>
      {briefingSummaries.length > 0 && (
        <Card>
          <SectionLabel>Morning Briefing</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 14 }}>
            <div style={{ padding: "10px 14px", background: C.surface, borderRadius: 8, border: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", letterSpacing: 2, marginBottom: 6 }}>YESTERDAY SPEND</div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 20, color: C.green }}>${parseFloat(budgetYesterday.total_spend||0).toFixed(4)}</div>
              <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 4 }}>{budgetYesterday.total_calls||0} calls</div>
            </div>
            <div style={{ padding: "10px 14px", background: C.surface, borderRadius: 8, border: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", letterSpacing: 2, marginBottom: 6 }}>TOP PROVIDER</div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 14, color: C.accent }}>{routingYesterday.provider_chosen||"—"}</div>
              <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 4 }}>{routingYesterday.cnt||0} of {routingYesterday.total_decisions||0} decisions</div>
            </div>
            <div style={{ padding: "10px 14px", background: C.surface, borderRadius: 8, border: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", letterSpacing: 2, marginBottom: 6 }}>SUMMARIES</div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 20, color: C.blue }}>{briefingSummaries.length}</div>
              <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 4 }}>last 24 hours</div>
            </div>
          </div>
          <div style={{ display: "grid", gap: 8, maxHeight: 200, overflowY: "auto" }}>
            {briefingSummaries.slice(0,5).map((s,i) => (
              <div key={s.id||i} style={{ padding: "10px 14px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8 }}>
                <div style={{ fontSize: 11, color: C.text, fontFamily: "'DM Mono', monospace", lineHeight: 1.5 }}>{s.summary}</div>
                <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 4 }}>{new Date(s.processed_at).toLocaleTimeString()}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Node status */}
        <Card>
          <SectionLabel>Node Status</SectionLabel>
          <div style={{ display: "grid", gap: 10 }}>
            {nodes.map(node => {
              const m = node.metrics;
              const ok = m && !node.err;
              return (
                <div key={node.name} style={{
                  display: "grid", gridTemplateColumns: "90px 1fr auto",
                  alignItems: "center", gap: 12, padding: "12px 14px",
                  background: C.surface, border: `1px solid ${ok ? C.green + "22" : C.red + "33"}`,
                  borderRadius: 10,
                }}>
                  <div>
                    <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, fontWeight: 500, color: ok ? C.green : C.red }}>{node.name}</div>
                  </div>
                  {ok ? (
                    <div style={{ display: "grid", gap: 5 }}>
                      {[["CPU", m.cpu_pct, 80, 95], ["RAM", m.ram_pct, 75, 90], ["DSK", m.disk_pct, 80, 95]].map(([lbl, val, w, c]) => (
                        <div key={lbl} style={{ display: "grid", gridTemplateColumns: "28px 1fr 32px", gap: 6, alignItems: "center" }}>
                          <span style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{lbl}</span>
                          <Bar pct={val || 0} warn={w} crit={c} height={4} />
                          <span style={{ fontSize: 9, color: C.muted, textAlign: "right", fontFamily: "'DM Mono', monospace" }}>{(val||0).toFixed(0)}%</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: 11, color: C.red, fontFamily: "'DM Mono', monospace" }}>UNREACHABLE</div>
                  )}
                  <StatusBadge status={ok ? "ONLINE" : "OFFLINE"} />
                </div>
              );
            })}
          </div>
        </Card>

        {/* Budget overview */}
        <Card>
          <SectionLabel>Budget Status</SectionLabel>
          <div style={{ display: "grid", gap: 16 }}>
            {[
              ["Daily",   costs.budget?.daily,   dailyPct],
              ["Weekly",  costs.budget?.weekly,  weeklyPct],
              ["Monthly", costs.budget?.monthly, monthPct],
            ].map(([lbl, b, pct]) => (
              <div key={lbl}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                  <span style={{ fontSize: 12, fontFamily: "'DM Mono', monospace", color: C.muted }}>{lbl}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, color: pct>=90?C.red:pct>=75?C.amber:C.green }}>
                    ${(b?.spent_usd||0).toFixed(4)} / ${(b?.limit_usd||0).toFixed(2)}
                  </span>
                </div>
                <Bar pct={pct} height={6} />
                <div style={{ fontSize: 10, color: pct>=90?C.red:pct>=75?C.amber:C.muted, marginTop: 4, textAlign: "right", fontFamily: "'DM Mono', monospace" }}>
                  {pct.toFixed(1)}%{pct>=75 ? (pct>=90 ? " · CRITICAL" : " · WARNING") : ""}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Ollama + service matrix */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 16 }}>
        <Card>
          <SectionLabel>Local Inference</SectionLabel>
          <div style={{ display: "grid", gap: 10 }}>
            <div style={{ padding: "14px", background: C.surface, borderRadius: 10, border: `1px solid ${ollamaHealth?.ollama_running ? C.green + "33" : C.red + "33"}` }}>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: C.muted, marginBottom: 6 }}>OLLAMA STATUS</div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 22, color: ollamaHealth?.ollama_running ? C.green : C.red }}>
                  {ollamaHealth?.ollama_running ? "ONLINE" : "OFFLINE"}
                </span>
                <StatusBadge status={ollamaHealth?.ollama_running ? "RUNNING" : "OFFLINE"} />
              </div>
              <div style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 6 }}>
                {ollamaHealth?.models?.join(", ") || "no models detected"}
              </div>
              <div style={{ fontSize: 11, color: C.green, marginTop: 4, fontFamily: "'DM Mono', monospace" }}>$0.00 / call</div>
            </div>
          </div>
        </Card>

        <Card>
          <SectionLabel>Service Matrix</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 8 }}>
            {(health.services || FALLBACK_SERVICES).map(svc => (
              <div key={svc.name} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "10px 12px", background: C.surface,
                border: `1px solid ${C.border}`, borderRadius: 8,
              }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: C.text }}>{svc.name}</div>
                  <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{svc.detail}</div>
                </div>
                <StatusBadge status={svc.status} />
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Unraid Storage */}
      <Card>
        <SectionLabel>Unraid Storage</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div style={{ padding: "14px", background: C.surface, borderRadius: 10, border: `1px solid ${(data?.unraidHealth?.status === "HEALTHY" ? C.green : data?.unraidHealth?.status === "WARNING" ? C.amber : C.red) + "33"}` }}>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: C.muted, marginBottom: 6 }}>ARRAY STATUS</div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 22, color: data?.unraidHealth?.status === "HEALTHY" ? C.green : data?.unraidHealth?.status === "WARNING" ? C.amber : C.red }}>
                {data?.unraidHealth?.array_state || "—"}
              </span>
              <StatusBadge status={data?.unraidHealth?.status || "UNKNOWN"} />
            </div>
            <div style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 6 }}>
              {data?.unraidHealth?.capacity ? `${data.unraidHealth.capacity.used_tb}TB / ${data.unraidHealth.capacity.total_tb}TB (${data.unraidHealth.capacity.used_pct}%)` : "—"}
            </div>
          </div>
          <div style={{ padding: "14px", background: C.surface, borderRadius: 10, border: `1px solid ${C.border}` }}>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: C.muted, marginBottom: 6 }}>DISK HEALTH</div>
            <div style={{ display: "grid", gap: 4, maxHeight: 120, overflowY: "auto" }}>
              {(data?.unraidHealth?.disks || []).filter(d => d.size_gb > 100).map((d, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, fontFamily: "'DM Mono', monospace", color: C.textDim }}>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 140 }}>{d.name}</span>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    {d.temp_c && <span style={{ color: d.temp_c > 45 ? C.red : d.temp_c > 38 ? C.amber : C.green }}>{d.temp_c}°C</span>}
                    <StatusBadge status={d.smart === "OK" ? "PASS" : d.smart === "UNKNOWN" ? "WARN" : "FAIL"} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* Recent code writes */}
      <Card>
        <SectionLabel>Recent Code Writes</SectionLabel>
        <div style={{ display: "grid", gap: 6 }}>
          {codeLog.slice(0, 5).map((entry, i) => (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "90px 1fr auto auto auto",
              gap: 12, alignItems: "center", padding: "10px 14px",
              background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 12,
            }}>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: C.muted }}>{entry.ts}</span>
              <span style={{ color: C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.intent}</span>
              <StatusBadge status={entry.lint === "PASS" ? "PASS" : "FAIL"} />
              <StatusBadge status={entry.security === "PASS" ? "PASS" : "FAIL"} />
              <StatusBadge status={entry.success ? "STABLE" : "ERROR"} />
            </div>
          ))}
          {!codeLog.length && (
            <div style={{ color: C.muted, textAlign: "center", padding: 24, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>
              No recent code writes
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

// ── HEALTH TAB ─────────────────────────────────────────────────────────────────
function HealthTab({ data, errors }) {
  const [restarting, setRestarting] = useState({});

  const nodes = [
    { key: "brain",    label: "BRAIN",    host: "100.64.166.22", port: 8182, metrics: data?.brainMetrics, err: errors.brainMetrics },
    { key: "gateway",  label: "GATEWAY",  host: "100.112.63.25", port: 8282, metrics: data?.gwMetrics,    err: errors.gwMetrics },
    { key: "endpoint", label: "ENDPOINT", host: "100.87.223.31",  port: 4001, metrics: data?.epMetrics,    err: errors.epMetrics },
  ];

  const handleRestart = async nodeKey => {
    setRestarting(r => ({ ...r, [nodeKey]: true }));
    await apiFetch(`${BRAIN}/v1/admin/restart/${nodeKey}`, { method: "POST" });
    setTimeout(() => setRestarting(r => ({ ...r, [nodeKey]: false })), 3000);
  };

  return (
    <div className="fade-up" style={{ display: "grid", gap: 16 }}>
      {nodes.map(node => {
        const m  = node.metrics;
        const ok = m && !node.err;
        return (
          <Card key={node.key} status={ok ? "ok" : "error"}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 18, fontWeight: 500, color: ok ? C.green : C.red }}>{node.label}</span>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: C.muted }}>{node.host}:{node.port}</span>
                <StatusBadge status={ok ? "ONLINE" : "OFFLINE"} />
              </div>
              <ActionBtn variant="warning" loading={restarting[node.key]} onClick={() => handleRestart(node.key)}>
                Restart Node
              </ActionBtn>
            </div>
            {ok ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
                {[
                  ["CPU",  m.cpu_pct,  "%", 80, 95],
                  ["RAM",  m.ram_pct,  "%", 75, 90],
                  ["DISK", m.disk_pct, "%", 80, 95],
                ].map(([lbl, val, unit, w, c]) => {
                  const v = val || 0;
                  const color = v >= c ? C.red : v >= w ? C.amber : C.green;
                  return (
                    <div key={lbl} style={{ padding: "16px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10 }}>
                      <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 10 }}>{lbl} UTILIZATION</div>
                      <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 28, fontWeight: 400, color }}>
                        {v.toFixed(1)}<span style={{ fontSize: 14, color: C.muted }}>{unit}</span>
                      </div>
                      <div style={{ marginTop: 12 }}><Bar pct={v} warn={w} crit={c} height={6} /></div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{ padding: "24px", textAlign: "center", background: C.redDim, border: `1px solid ${C.red}44`, borderRadius: 10 }}>
                <div style={{ color: C.red, fontFamily: "'DM Mono', monospace", fontSize: 13, marginBottom: 12 }}>
                  NODE UNREACHABLE — {node.err || "No response"}
                </div>
                <ActionBtn variant="danger" onClick={() => handleRestart(node.key)} loading={restarting[node.key]}>
                  Attempt Restart
                </ActionBtn>
              </div>
            )}
            {ok && m?.uptime && (
              <div style={{ marginTop: 12, fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>
                UPTIME: {m.uptime} · LOAD: {m.load_avg || "—"} · PROCESSES: {m.process_count || "—"}
              </div>
            )}
          </Card>
        );
      })}

      <Card>
        <SectionLabel>Services & Daemons</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 8 }}>
          {(data?.health?.services || FALLBACK_SERVICES).map(svc => (
            <div key={svc.name} style={{
              padding: "12px 14px", background: C.surface,
              border: `1px solid ${C.border}`, borderRadius: 10,
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: 2 }}>{svc.name}</div>
                <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{svc.detail}</div>
              </div>
              <StatusBadge status={svc.status} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ── COST TAB ───────────────────────────────────────────────────────────────────
function ElectricityCost({ data }) {
  const [ratePerKwh, setRatePerKwh] = useState(() => {
    try { return parseFloat(localStorage.getItem("jarvis_kwh_rate") || "0.12"); } catch { return 0.12; }
  });
  const [editing, setEditing] = useState(false);
  const [draft, setDraft]     = useState("");

  const nodes = [
    { label: "BRAIN",    metrics: data?.brainMetrics },
    { label: "GATEWAY",  metrics: data?.gwMetrics },
    { label: "ENDPOINT", metrics: data?.epMetrics },
  ];
  const totalW      = nodes.reduce((s, n) => s + (n.metrics?.power_w || 0), 0);
  const dailyKwh    = totalW * 24 / 1000;
  const dailyCost   = dailyKwh * ratePerKwh;
  const monthlyCost = dailyKwh * 30 * ratePerKwh;

  const save = () => {
    const v = parseFloat(draft);
    if (!isNaN(v) && v > 0) {
      setRatePerKwh(v);
      try { localStorage.setItem("jarvis_kwh_rate", v.toString()); } catch {}
    }
    setEditing(false);
  };

  return (
    <Card>
      <SectionLabel>⚡ Electricity Cost</SectionLabel>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 16 }}>
        {nodes.map(n => (
          <div key={n.label} style={{ padding: "14px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10 }}>
            <div style={{ fontSize: 9, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 6 }}>{n.label}</div>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 20, color: C.green }}>{n.metrics ? `${n.metrics.power_w}W` : "—"}</div>
            <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 3 }}>
              {n.metrics ? `${(n.metrics.power_w * 24 / 1000).toFixed(3)} kWh/day` : "offline"}
            </div>
          </div>
        ))}
        <div style={{ padding: "14px", background: C.surface, border: `1px solid ${C.borderHi}`, borderRadius: 10 }}>
          <div style={{ fontSize: 9, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 6 }}>TOTAL DRAW</div>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 20, color: C.amber }}>{totalW.toFixed(1)}W</div>
          <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 3 }}>{dailyKwh.toFixed(3)} kWh/day</div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 12, alignItems: "center", padding: "14px 16px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10 }}>
        <div>
          <div style={{ fontSize: 9, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 4 }}>DAILY ELEC COST</div>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 24, color: C.green }}>${dailyCost.toFixed(4)}</div>
          <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 2 }}>{dailyKwh.toFixed(4)} kWh × ${ratePerKwh}/kWh</div>
        </div>
        <div>
          <div style={{ fontSize: 9, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 4 }}>MONTHLY ELEC COST</div>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 24, color: C.amber }}>${monthlyCost.toFixed(2)}</div>
          <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 2 }}>30-day estimate</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
          <div style={{ fontSize: 9, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace" }}>RATE ($/kWh)</div>
          {editing ? (
            <div style={{ display: "flex", gap: 8 }}>
              <MonoInput type="number" value={draft} onChange={setDraft} placeholder={String(ratePerKwh)} style={{ width: 80 }} />
              <ActionBtn variant="success" onClick={save}>Save</ActionBtn>
            </div>
          ) : (
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 16, color: C.text }}>${ratePerKwh}</span>
              <ActionBtn onClick={() => { setDraft(String(ratePerKwh)); setEditing(true); }}>Edit</ActionBtn>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function CostTab({ data, errors }) {
  const costs = data?.costs || {};
  const creditData2 = costs.credit || {};
  const [editing, setEditing]     = useState(false);
  const [budgetForm, setBudgetForm] = useState({ daily: "", weekly: "", monthly: "" });
  const [saving, setSaving]       = useState(false);
  const [saveMsg, setSaveMsg]     = useState("");

  const saveBudget = async () => {
    setSaving(true);
    for (const p of ["daily","weekly","monthly"]) {
      if (budgetForm[p]) {
        await apiFetch(`${BRAIN}/v1/costs/budget?period=${p}&limit_usd=${budgetForm[p]}`, { method: "POST" });
      }
    }
    setSaving(false);
    setSaveMsg("Budget updated ✓");
    setEditing(false);
    setTimeout(() => setSaveMsg(""), 3000);
  };

  const periods = [
    { key: "daily",   label: "Daily",   b: costs.budget?.daily },
    { key: "weekly",  label: "Weekly",  b: costs.budget?.weekly },
    { key: "monthly", label: "Monthly", b: costs.budget?.monthly },
  ];

  return (
    <div className="fade-up" style={{ display: "grid", gap: 16 }}>
      <ElectricityCost data={data} />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
        {periods.map(({ key, label, b }) => {
          const pct   = b ? (b.spent_usd / b.limit_usd * 100) : 0;
          const color = pct >= 90 ? C.red : pct >= 75 ? C.amber : C.green;
          return (
            <Card key={key} status={pct>=90?"error":pct>=75?"warn":"ok"}>
              <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 10 }}>{label.toUpperCase()} BUDGET</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 28, color }}>${(b?.spent_usd||0).toFixed(4)}</span>
                <span style={{ fontSize: 13, color: C.muted }}>/ ${(b?.limit_usd||0).toFixed(2)}</span>
              </div>
              <div style={{ margin: "12px 0" }}><Bar pct={pct} height={6} /></div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace" }}>
                <span>${((b?.limit_usd||0)-(b?.spent_usd||0)).toFixed(4)} left</span>
                <span style={{ color }}>{pct.toFixed(1)}%</span>
              </div>
            </Card>
          );
        })}
      </div>

      <Card status={creditData2?.low_balance ? "error" : creditData2?.pct_used >= 75 ? "warn" : "ok"}>
        <SectionLabel>Anthropic API Credit Balance</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", letterSpacing: 2, marginBottom: 6 }}>STARTING BALANCE</div>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 22, color: C.text }}>${(creditData2?.balance_usd||0).toFixed(2)}</div>
          </div>
          <div>
            <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", letterSpacing: 2, marginBottom: 6 }}>TOTAL SPENT</div>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 22, color: C.amber }}>${(creditData2?.spent_usd||0).toFixed(4)}</div>
          </div>
          <div>
            <div style={{ fontSize: 9, color: C.muted, fontFamily: "'DM Mono', monospace", letterSpacing: 2, marginBottom: 6 }}>REMAINING</div>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 22, color: creditData2?.low_balance ? C.red : C.green }}>${(creditData2?.remaining_usd||0).toFixed(2)}</div>
          </div>
        </div>
        <div style={{ marginBottom: 10 }}><Bar pct={creditData2?.pct_used||0} height={6} /></div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace" }}>
          <span>{(creditData2?.pct_used||0).toFixed(2)}% used · warns at $5.00 · critical at $2.00</span>
          <span style={{ color: C.muted }}>update: <code style={{ color: C.accent }}>POST /v1/costs/credit?balance_usd=XX</code></span>
        </div>
      </Card>

      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <SectionLabel>Update Budget Limits</SectionLabel>
          {saveMsg && <span style={{ fontSize: 11, color: C.green, fontFamily: "'DM Mono', monospace" }}>{saveMsg}</span>}
        </div>
        {editing ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr) auto auto", gap: 10, alignItems: "flex-end" }}>
            {["daily","weekly","monthly"].map(p => (
              <div key={p}>
                <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", letterSpacing: 2, marginBottom: 5 }}>{p.toUpperCase()} ($)</div>
                <MonoInput type="number" value={budgetForm[p]} onChange={v => setBudgetForm(f => ({...f,[p]:v}))} placeholder={(costs.budget?.[p]?.limit_usd||0).toFixed(2)} />
              </div>
            ))}
            <ActionBtn variant="success" onClick={saveBudget} loading={saving}>Save</ActionBtn>
            <ActionBtn variant="ghost" onClick={() => setEditing(false)}>Cancel</ActionBtn>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <ActionBtn variant="warning" onClick={() => setEditing(true)}>Edit Limits</ActionBtn>
            <span style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>
              Daily ${(costs.budget?.daily?.limit_usd||0).toFixed(2)} · Weekly ${(costs.budget?.weekly?.limit_usd||0).toFixed(2)} · Monthly ${(costs.budget?.monthly?.limit_usd||0).toFixed(2)}
            </span>
          </div>
        )}
      </Card>

      <Card>
        <SectionLabel>Spend by Provider</SectionLabel>
        <div style={{ display: "grid", gap: 8 }}>
          {(costs.by_provider || []).map(row => {
            const maxSpend = Math.max(...(costs.by_provider||[]).map(r=>r.cost_usd||0), 0.0001);
            return (
              <div key={row.provider} style={{
                display: "grid", gridTemplateColumns: "160px 1fr 60px 90px",
                gap: 14, alignItems: "center", padding: "10px 14px",
                background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8,
              }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{row.provider}</span>
                <Bar pct={(row.cost_usd / maxSpend) * 100} warn={999} crit={999} height={5} forceColor={PROVIDER_COLORS[row.provider] || C.muted} />
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: C.muted, textAlign: "right" }}>{row.calls} calls</span>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, color: row.cost_usd === 0 ? C.green : C.text, textAlign: "right" }}>
                  ${(row.cost_usd||0).toFixed(4)}
                </span>
              </div>
            );
          })}
          {!costs.by_provider?.length && (
            <div style={{ color: C.muted, textAlign: "center", padding: 20, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>No spend data yet</div>
          )}
        </div>
      </Card>
    </div>
  );
}

// ── CODE REVIEW TAB ────────────────────────────────────────────────────────────
function CodeReviewTab({ data }) {
  const [prs, setPRs]             = useState([]);
  const [selected, setSelected]   = useState(null);
  const [acting, setActing]       = useState({});
  const [msg, setMsg]             = useState("");
  const [codeIntent, setCodeIntent] = useState("");
  const [codeFile, setCodeFile]   = useState("");
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    apiFetch(`${BRAIN}/v1/github/prs`).then(([d]) => { if (d) setPRs(d); });
  }, []);

  const handleApprove = async pr => {
    setActing(a => ({...a,[pr.id]:"approving"}));
    const [, err] = await apiFetch(`${BRAIN}/v1/github/prs/${pr.id}/merge`, { method: "POST" });
    if (!err) { setMsg(`PR #${pr.id} merged ✓`); setPRs(p => p.filter(x=>x.id!==pr.id)); }
    else setMsg(`Error: ${err}`);
    setActing(a => ({...a,[pr.id]:null}));
    setTimeout(() => setMsg(""), 4000);
  };

  const handleReject = async pr => {
    setActing(a => ({...a,[pr.id]:"rejecting"}));
    const [, err] = await apiFetch(`${BRAIN}/v1/github/prs/${pr.id}/close`, { method: "POST" });
    if (!err) { setMsg(`PR #${pr.id} closed`); setPRs(p => p.filter(x=>x.id!==pr.id)); }
    else setMsg(`Error: ${err}`);
    setActing(a => ({...a,[pr.id]:null}));
    setTimeout(() => setMsg(""), 4000);
  };

  const triggerWrite = async () => {
    if (!codeIntent.trim()) return;
    setTriggering(true);
    const [res, err] = await apiFetch(`${BRAIN}/v1/code/write`, {
      method: "POST",
      body: JSON.stringify({ intent: codeIntent, target_file: codeFile || undefined }),
    });
    setTriggering(false);
    if (!err) { setMsg(`Code write triggered → branch ${res?.branch || "unknown"}`); setCodeIntent(""); setCodeFile(""); }
    else setMsg(`Error: ${err}`);
    setTimeout(() => setMsg(""), 6000);
  };

  return (
    <div className="fade-up" style={{ display: "grid", gap: 16 }}>
      <Card>
        <SectionLabel>Trigger Code Write</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 10, alignItems: "flex-end" }}>
          <div>
            <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 5 }}>INTENT</div>
            <MonoInput value={codeIntent} onChange={setCodeIntent} placeholder="e.g. Add health check to metrics endpoint" />
          </div>
          <div>
            <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 5 }}>TARGET FILE (optional)</div>
            <MonoInput value={codeFile} onChange={setCodeFile} placeholder="/Users/jarvisbrain/jarvis/..." />
          </div>
          <ActionBtn variant="success" onClick={triggerWrite} loading={triggering} disabled={!codeIntent.trim()}>
            ▶ Execute
          </ActionBtn>
        </div>
        {msg && <div style={{ marginTop: 10, fontSize: 11, color: C.green, fontFamily: "'DM Mono', monospace" }}>{msg}</div>}
      </Card>

      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <SectionLabel>Open Pull Requests</SectionLabel>
          <span style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{prs.length} open</span>
        </div>
        {prs.length === 0 ? (
          <div style={{ textAlign: "center", padding: 30, color: C.green, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>✓ NO OPEN PRs — All clear</div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {prs.map(pr => (
              <div key={pr.id} style={{ background: C.surface, border: `1px solid ${selected===pr.id?C.accent:C.border}`, borderRadius: 10, overflow: "hidden" }}>
                <div onClick={() => setSelected(selected===pr.id?null:pr.id)} style={{ display: "grid", gridTemplateColumns: "50px 1fr auto auto auto auto auto", gap: 12, alignItems: "center", padding: "12px 14px", cursor: "pointer" }}>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: C.muted }}>#{pr.id}</span>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{pr.intent}</div>
                    <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 2 }}>{pr.branch}</div>
                  </div>
                  <span style={{ fontSize: 10, color: C.green, fontFamily: "'DM Mono', monospace" }}>+{pr.added}</span>
                  <span style={{ fontSize: 10, color: C.red,   fontFamily: "'DM Mono', monospace" }}>-{pr.removed}</span>
                  <StatusBadge status={pr.lint ? "PASS" : "FAIL"} />
                  <StatusBadge status={pr.security ? "PASS" : "FAIL"} />
                  <span style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{pr.ts}</span>
                </div>
                {selected === pr.id && (
                  <div>
                    <pre style={{ padding: "14px 18px", margin: 0, fontSize: 11, lineHeight: 1.7, fontFamily: "'DM Mono', monospace", background: "#050505", borderTop: `1px solid ${C.border}`, color: C.text, overflowX: "auto", whiteSpace: "pre-wrap", maxHeight: 280, overflowY: "auto" }}>
                      {(pr.diff || "").split("\n").map((line, i) => (
                        <span key={i} style={{ display: "block", color: line.startsWith("+") ? C.green : line.startsWith("-") ? C.red : C.muted }}>{line}</span>
                      ))}
                    </pre>
                    <div style={{ display: "flex", gap: 10, padding: "10px 14px", borderTop: `1px solid ${C.border}` }}>
                      <ActionBtn variant="success" loading={acting[pr.id]==="approving"} onClick={() => handleApprove(pr)}>✓ Approve & Merge</ActionBtn>
                      <ActionBtn variant="danger"  loading={acting[pr.id]==="rejecting"} onClick={() => handleReject(pr)}>✗ Reject & Close</ActionBtn>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <SectionLabel>Code Write Audit Log</SectionLabel>
        <div style={{ display: "grid", gap: 6 }}>
          {(data?.codeLog || []).map((entry, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "90px 1fr 160px 80px 70px 70px 70px", gap: 10, alignItems: "center", padding: "9px 12px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 12 }}>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: C.muted }}>{entry.ts}</span>
              <span style={{ color: C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.intent}</span>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: C.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.file}</span>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 9,  color: C.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.branch}</span>
              <StatusBadge status={entry.lint     === "PASS" ? "PASS" : "FAIL"} />
              <StatusBadge status={entry.security === "PASS" ? "PASS" : "FAIL"} />
              <StatusBadge status={entry.success  ? "STABLE" : "ERROR"} />
            </div>
          ))}
          {!data?.codeLog?.length && (
            <div style={{ color: C.muted, textAlign: "center", padding: 20, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>No audit log data</div>
          )}
        </div>
      </Card>
    </div>
  );
}

// ── ERRORS TAB ─────────────────────────────────────────────────────────────────
function ErrorsTab({ data, errors }) {
  const allErrors = data?.errors || [];
  const [filter, setFilter] = useState("ALL");
  const filtered = filter === "ALL" ? allErrors : allErrors.filter(e => e.level === filter);

  const filterColor = f => f==="ERROR"?C.red:f==="WARN"?C.amber:f==="INFO"?C.blue:C.accent;

  return (
    <div className="fade-up" style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", gap: 8 }}>
        {["ALL","ERROR","WARN","INFO"].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: "6px 16px", borderRadius: 8, cursor: "pointer", fontSize: 11,
            fontFamily: "'DM Mono', monospace", letterSpacing: 1,
            background: filter === f ? filterColor(f) + "22" : "transparent",
            color: filter === f ? filterColor(f) : C.muted,
            border: `1px solid ${filter===f ? filterColor(f) : C.border}`,
            transition: "all 0.15s",
          }}>{f}</button>
        ))}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace", alignSelf: "center" }}>{filtered.length} events</span>
      </div>

      <Card style={{ padding: 0, overflow: "hidden" }}>
        {filtered.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, color: C.green, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>✓ NO EVENTS</div>
        ) : (
          filtered.map((entry, i) => {
            const color = entry.level==="ERROR"?C.red:entry.level==="WARN"?C.amber:C.blue;
            return (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "90px 90px 100px 1fr", gap: 14, alignItems: "center", padding: "11px 18px", borderBottom: i<filtered.length-1?`1px solid ${C.border}`:"none", borderLeft: `3px solid ${color}`, background: i%2===0?C.surface:"transparent" }}>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: C.muted }}>{entry.ts}</span>
                <StatusBadge status={entry.level} />
                <span style={{ fontSize: 11, fontWeight: 600, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{entry.node}</span>
                <span style={{ fontSize: 12, color: C.text }}>{entry.msg}</span>
              </div>
            );
          })
        )}
      </Card>

      {Object.keys(errors).length > 0 && (
        <Card status="error">
          <SectionLabel>API Connectivity Errors</SectionLabel>
          {Object.entries(errors).map(([k, v]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "8px 12px", background: C.redDim, borderRadius: 8, marginBottom: 6, fontSize: 12 }}>
              <span style={{ fontFamily: "'DM Mono', monospace", color: C.red }}>{k}</span>
              <span style={{ color: C.muted }}>{v}</span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

// ── SECURITY TAB ───────────────────────────────────────────────────────────────
function SecurityTab({ data }) {
  const checks = FALLBACK_SECURITY;
  const passed = checks.filter(c => c.status === "PASS").length;
  const score  = Math.round((passed / checks.length) * 100);

  const nodes = [
    { label: "Brain",    ip: "100.64.166.22", port: 8182, ok: !!data?.brainMetrics },
    { label: "Gateway",  ip: "100.112.63.25", port: 8282, ok: !!data?.gwMetrics },
    { label: "Endpoint", ip: "100.87.223.31",  port: 4001, ok: !!data?.epMetrics },
  ];

  const knownKeys = [
    { name: "ANTHROPIC_API_KEY",   service: "Anthropic Claude",  status: "Active", note: "Rotate every 90 days" },
    { name: "PERPLEXITY_API_KEY",  service: "Perplexity AI",     status: "Active", note: "Rotate every 90 days" },
    { name: "SENDGRID_API_KEY",    service: "SendGrid Email",     status: "Active", note: "Mail Send only scope" },
    { name: "NEWS_API_KEY",        service: "NewsAPI",            status: "Active", note: "Check expiry on dashboard" },
    { name: "POSTGRES_PASSWORD",   service: "Postgres DB",        status: "Active", note: "Local only, not cloud" },
    { name: "JARVIS_GATEWAY_TOKEN",service: "Gateway Auth",       status: "Active", note: "Rotate in Phase hardening" },
  ];

  const ports = [
    { port: 8182,  service: "Brain API",     node: "Brain",    status: "OPEN" },
    { port: 8282,  service: "Gateway API",   node: "Gateway",  status: "OPEN" },
    { port: 4001,  service: "Endpoint API",  node: "Endpoint", status: "OPEN" },
    { port: 5432,  service: "Postgres",      node: "Brain",    status: "OPEN" },
    { port: 11434, service: "Ollama",        node: "Endpoint", status: "OPEN" },
    { port: 22,    service: "SSH",           node: "All",      status: "OPEN" },
  ];

  const scoreColor = score >= 90 ? C.green : score >= 70 ? C.amber : C.red;

  return (
    <div className="fade-up" style={{ display: "grid", gap: 16 }}>
      {/* Score header */}
      <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 16 }}>
        <Card style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 28 }}>
          <div style={{ fontSize: 9, letterSpacing: 3, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 16 }}>SECURITY SCORE</div>
          <div style={{ width: 90, height: 90, borderRadius: "50%", border: `4px solid ${scoreColor}`, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: `0 0 30px ${scoreColor}33` }}>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 30, color: scoreColor }}>{score}</span>
          </div>
          <div style={{ marginTop: 12, fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{passed}/{checks.length} PASS</div>
        </Card>
        <Card>
          <SectionLabel>Compliance Summary</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {[
              ["Branch Protection",   true],  ["Secrets Encrypted",  true],
              ["Write Path Enforced", true],  ["Bandit Scanning",    true],
              ["Rate Limiting",       true],  ["Keychain Secrets",   true],
              ["HTTPS Enforced",      false], ["Token Rotation",     false],
            ].map(([label, ok]) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", background: C.surface, border: `1px solid ${ok?C.green+"22":C.amber+"22"}`, borderRadius: 8 }}>
                <span style={{ fontSize: 14, color: ok ? C.green : C.amber }}>{ok ? "✓" : "○"}</span>
                <span style={{ fontSize: 12, color: ok ? C.text : C.muted }}>{label}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Accordion title="Network — Tailscale VPN Health" icon="🌐" defaultOpen={true}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
          {nodes.map(n => (
            <div key={n.label} style={{ padding: "16px", background: C.surface, border: `1px solid ${n.ok?C.green+"33":C.red+"33"}`, borderRadius: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <span style={{ fontFamily: "'DM Mono', monospace", fontWeight: 500, fontSize: 13, color: C.text }}>{n.label}</span>
                <StatusBadge status={n.ok ? "ONLINE" : "OFFLINE"} />
              </div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: C.muted }}>Tailscale IP: {n.ip}</div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: C.muted, marginTop: 4 }}>API Port: {n.port}</div>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: C.muted, marginTop: 4 }}>VPN: {n.ok ? "✓ Connected" : "✗ Unreachable"}</div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, padding: "10px 14px", background: C.surface, borderRadius: 8, fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>
          Full network latency monitoring available in Phase 7
        </div>
      </Accordion>

      <Accordion title="Files — Path Access Control" icon="📁">
        <SectionLabel>Allowed Read Paths</SectionLabel>
        <div style={{ display: "grid", gap: 8 }}>
          {[
            "/Users/jarvisbrain/jarvis/services/brain/brain/",
            "/Users/jarvisbrain/jarvis/services/gateway/app/",
            "/Users/jarvisbrain/jarvis/services/endpoint/app/",
          ].map(p => (
            <div key={p} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", background: C.surface, border: `1px solid ${C.green}22`, borderRadius: 8 }}>
              <span style={{ color: C.green }}>✓</span>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: C.text }}>{p}</span>
              <span style={{ marginLeft: "auto" }}><StatusBadge status="ACTIVE" /></span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, padding: "10px 14px", background: C.amberDim, border: `1px solid ${C.amber}33`, borderRadius: 8, fontSize: 11, color: C.amber, fontFamily: "'DM Mono', monospace" }}>
          ⚠ Blocked path attempts and file read audit log available in Phase 7
        </div>
      </Accordion>

      <Accordion title="Security Keys — API Key Registry" icon="🔑">
        <div style={{ display: "grid", gap: 8 }}>
          {knownKeys.map(k => (
            <div key={k.name} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 12, alignItems: "center", padding: "10px 14px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8 }}>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: C.accent }}>{k.name}</span>
              <span style={{ fontSize: 12, color: C.text }}>{k.service}</span>
              <span style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{k.note}</span>
              <StatusBadge status="ACTIVE" />
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, padding: "10px 14px", background: C.surface, borderRadius: 8, fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>
          Key values are never displayed. Stored in ~/jarvis/.secrets (chmod 600). Rotation reminders coming in Phase 7.
        </div>
      </Accordion>

      <Accordion title="Log Detection — Anomaly & Auth Monitoring" icon="🔍">
        <div style={{ padding: "20px", textAlign: "center", background: C.surface, borderRadius: 10 }}>
          <div style={{ fontSize: 32, marginBottom: 10 }}>🔍</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.text, marginBottom: 8 }}>Log Detection Engine</div>
          <div style={{ fontSize: 12, color: C.muted, fontFamily: "'DM Mono', monospace", lineHeight: 1.8 }}>
            Failed auth attempts · Anomaly patterns · Suspicious query detection<br />
            Full log detection monitoring ships in Phase 7 (Identity & Access)
          </div>
        </div>
      </Accordion>

      <Accordion title="Firewall — Port & Connection Status" icon="🛡️">
        <div style={{ display: "grid", gap: 8 }}>
          {ports.map(p => (
            <div key={p.port} style={{ display: "grid", gridTemplateColumns: "80px 1fr 120px auto", gap: 12, alignItems: "center", padding: "10px 14px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8 }}>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 14, color: C.accent }}>:{p.port}</span>
              <span style={{ fontSize: 12, color: C.text }}>{p.service}</span>
              <span style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{p.node}</span>
              <StatusBadge status="ACTIVE" />
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, padding: "10px 14px", background: C.surface, borderRadius: 8, fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>
          Port filtering and blocked IP tracking available in Phase 7
        </div>
      </Accordion>

      <Accordion title="Unauthorized Access — Failed Session Tracking" icon="🚫" badgeText="Phase 7" badgeColor={C.amber}>
        <div style={{ padding: "20px", textAlign: "center", background: C.surface, borderRadius: 10 }}>
          <div style={{ fontSize: 32, marginBottom: 10 }}>🚫</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.text, marginBottom: 8 }}>Unauthorized Access Detection</div>
          <div style={{ fontSize: 12, color: C.muted, fontFamily: "'DM Mono', monospace", lineHeight: 1.8 }}>
            Failed sessions · Unknown identity attempts · Lockout events<br />
            Biometric authentication and identity framework ships in Phase 7
          </div>
        </div>
      </Accordion>

      <Accordion title="Prompt Injection — Query Flagging by User" icon="⚡" badgeText="Phase 7" badgeColor={C.amber}>
        <div style={{ padding: "20px", textAlign: "center", background: C.surface, borderRadius: 10 }}>
          <div style={{ fontSize: 32, marginBottom: 10 }}>⚡</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.text, marginBottom: 8 }}>Prompt Injection Detection</div>
          <div style={{ fontSize: 12, color: C.muted, fontFamily: "'DM Mono', monospace", lineHeight: 1.8 }}>
            Tracks injection attempts per user identity · child_query_log table ready<br />
            Full flagging UI with per-user breakdown ships in Phase 7
          </div>
        </div>
      </Accordion>

      <Card>
        <SectionLabel>Security Checks</SectionLabel>
        <div style={{ display: "grid", gap: 8 }}>
          {checks.map((check, i) => {
            const color = check.status==="PASS"?C.green:check.status==="TODO"?C.amber:check.status==="WARN"?C.amber:C.red;
            return (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "80px 1fr 200px", gap: 14, alignItems: "center", padding: "11px 14px", background: C.surface, border: `1px solid ${color}22`, borderRadius: 8 }}>
                <StatusBadge status={check.status} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{check.item}</div>
                  <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginTop: 2 }}>{check.detail}</div>
                </div>
                {check.status !== "PASS" && (
                  <span style={{ fontSize: 10, color: C.amber, fontFamily: "'DM Mono', monospace" }}>→ Phase Final Hardening</span>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

// ── ROUTING TAB ────────────────────────────────────────────────────────────────
function RoutingTab({ data }) {
  const stats     = data?.routingStats || {};
  const decisions = data?.routingDecisions || [];
  const providers = stats.provider_health || [];

  const [simIntent,     setSimIntent]     = useState("");
  const [simComplexity, setSimComplexity] = useState(3);
  const [simResult,     setSimResult]     = useState(null);
  const [simulating,    setSimulating]    = useState(false);

  const [replayId,     setReplayId]     = useState("");
  const [replayResult, setReplayResult] = useState(null);
  const [replaying,    setReplaying]    = useState(false);

  const [weightInputs, setWeightInputs] = useState({});
  const [savingWeight, setSavingWeight] = useState({});
  const [resettingCircuit, setResettingCircuit] = useState({});
  const [recalculating, setRecalculating] = useState(false);
  const [ctrlMsg, setCtrlMsg] = useState("");

  const simulate = async () => {
    if (!simIntent.trim()) return;
    setSimulating(true);
    const [res] = await apiFetch(`${BRAIN}/v1/router/simulate`, {
      method: "POST",
      body: JSON.stringify({ intent: simIntent, complexity: simComplexity }),
    });
    setSimResult(res);
    setSimulating(false);
  };

  const replay = async () => {
    if (!replayId.trim()) return;
    setReplaying(true);
    const [res] = await apiFetch(`${BRAIN}/v1/router/replay/${replayId}`, { method: "POST" });
    setReplayResult(res);
    setReplaying(false);
  };

  const saveWeight = async provider => {
    const w = parseFloat(weightInputs[provider]);
    if (isNaN(w)) return;
    setSavingWeight(s => ({...s,[provider]:true}));
    await apiFetch(`${BRAIN}/v1/router/weights`, {
      method: "POST",
      body: JSON.stringify({ provider, weight: w, locked: false }),
    });
    setSavingWeight(s => ({...s,[provider]:false}));
    setCtrlMsg(`Weight updated: ${provider} → ${w}`);
    setTimeout(() => setCtrlMsg(""), 3000);
  };

  const resetCircuit = async provider => {
    setResettingCircuit(s => ({...s,[provider]:true}));
    await apiFetch(`${BRAIN}/v1/router/circuit/reset`, {
      method: "POST",
      body: JSON.stringify({ provider }),
    });
    setResettingCircuit(s => ({...s,[provider]:false}));
    setCtrlMsg(`Circuit reset: ${provider}`);
    setTimeout(() => setCtrlMsg(""), 3000);
  };

  const recalculate = async () => {
    setRecalculating(true);
    const [res] = await apiFetch(`${BRAIN}/v1/router/recalculate`, { method: "POST" });
    setRecalculating(false);
    setCtrlMsg(res?.ok ? "Weights recalculated ✓" : "Recalculate failed");
    setTimeout(() => setCtrlMsg(""), 3000);
  };

  const localVsCloud = stats.local_vs_cloud || [];
  const localTotal   = localVsCloud.find(x => x.tier === "local")?.total || 0;
  const cloudTotal   = localVsCloud.find(x => x.tier === "cloud")?.total || 0;
  const totalAll     = localTotal + cloudTotal || 1;

  return (
    <div className="fade-up" style={{ display: "grid", gap: 8 }}>

      <Accordion title="Overview — Live Routing Feed" icon="📡" defaultOpen={true}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16 }}>
          {/* Decisions feed */}
          <div>
            <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 10 }}>LAST {decisions.length} DECISIONS</div>
            <div style={{ display: "grid", gap: 6 }}>
              {decisions.map((d, i) => (
                <div key={d.id || i} style={{ display: "grid", gridTemplateColumns: "40px 50px 1fr auto auto", gap: 10, alignItems: "center", padding: "9px 12px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 12 }}>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: C.muted }}>#{d.id}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, padding: "2px 6px", background: C.dim, borderRadius: 4, color: C.textDim, textAlign: "center" }}>c={d.complexity}</span>
                  <span style={{ color: C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.intent}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: PROVIDER_COLORS[d.provider_chosen] || C.muted, whiteSpace: "nowrap" }}>
                    {PROVIDER_LABELS[d.provider_chosen] || d.provider_chosen}
                  </span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10, color: C.muted }}>{d.latency_ms}ms</span>
                </div>
              ))}
              {!decisions.length && (
                <div style={{ color: C.muted, textAlign: "center", padding: 20, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>No decisions logged yet</div>
              )}
            </div>
          </div>

          {/* Weights chart */}
          <div>
            <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 10 }}>PROVIDER WEIGHTS</div>
            <div style={{ display: "grid", gap: 10 }}>
              {providers.map(p => (
                <div key={p.provider}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 11, color: PROVIDER_COLORS[p.provider] || C.text, fontFamily: "'DM Mono', monospace" }}>{PROVIDER_LABELS[p.provider] || p.provider}</span>
                    <span style={{ fontSize: 11, color: C.accent, fontFamily: "'DM Mono', monospace" }}>{p.weight?.toFixed(2)}</span>
                  </div>
                  <Bar pct={(p.weight / 2) * 100} warn={999} crit={999} height={6} forceColor={PROVIDER_COLORS[p.provider] || C.accent} />
                  {p.locked && <div style={{ fontSize: 9, color: C.amber, fontFamily: "'DM Mono', monospace", marginTop: 2 }}>🔒 locked</div>}
                </div>
              ))}
            </div>
            <div style={{ marginTop: 16, padding: "10px 12px", background: C.surface, borderRadius: 8 }}>
              <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 6 }}>LOCAL vs CLOUD</div>
              <div style={{ display: "flex", gap: 12 }}>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, color: C.green }}>{Math.round(localTotal/totalAll*100)}% local</span>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, color: C.amber }}>{Math.round(cloudTotal/totalAll*100)}% cloud</span>
              </div>
              <Bar pct={Math.round(localTotal/totalAll*100)} warn={999} crit={999} height={8} forceColor={C.green} />
            </div>
          </div>
        </div>
      </Accordion>

      <Accordion title="Health Cards — Provider Status" icon="💚">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
          {providers.map(p => {
            const color = p.circuit_open ? C.red : p.failure_count > 2 ? C.amber : C.green;
            return (
              <div key={p.provider} style={{ padding: "16px", background: C.surface, border: `1px solid ${color}33`, borderRadius: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, fontWeight: 500, color: PROVIDER_COLORS[p.provider] || C.text }}>
                    {PROVIDER_LABELS[p.provider] || p.provider}
                  </span>
                  <StatusBadge status={p.circuit_open ? "OPEN" : "CLOSED"} />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 11, fontFamily: "'DM Mono', monospace" }}>
                  <div>
                    <div style={{ color: C.muted, marginBottom: 2 }}>WEIGHT</div>
                    <div style={{ color: C.accent, fontSize: 18 }}>{p.weight?.toFixed(2)}</div>
                  </div>
                  <div>
                    <div style={{ color: C.muted, marginBottom: 2 }}>FAILURES</div>
                    <div style={{ color: p.failure_count > 0 ? C.red : C.green, fontSize: 18 }}>{p.failure_count || 0}</div>
                  </div>
                  <div>
                    <div style={{ color: C.muted, marginBottom: 2 }}>SUCCESSES</div>
                    <div style={{ color: C.green, fontSize: 14 }}>{p.success_count || 0}</div>
                  </div>
                  <div>
                    <div style={{ color: C.muted, marginBottom: 2 }}>CB THRESH</div>
                    <div style={{ color: C.textDim, fontSize: 14 }}>{p.circuit_threshold}/{p.circuit_window_minutes}m</div>
                  </div>
                </div>
                {p.locked && <div style={{ marginTop: 10, fontSize: 10, color: C.amber, fontFamily: "'DM Mono', monospace" }}>🔒 Weight locked</div>}
              </div>
            );
          })}
          {!providers.length && (
            <div style={{ gridColumn: "1/-1", color: C.muted, textAlign: "center", padding: 24, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>No provider health data</div>
          )}
        </div>
      </Accordion>

      <Accordion title="Stats — Latency, Complexity & Usage" icon="📊">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* By provider */}
          <div>
            <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 10 }}>BY PROVIDER</div>
            <div style={{ display: "grid", gap: 8 }}>
              {(stats.by_provider || []).map(p => (
                <div key={p.provider_chosen} style={{ padding: "10px 12px", background: C.surface, borderRadius: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 12, color: PROVIDER_COLORS[p.provider_chosen] || C.text, fontFamily: "'DM Mono', monospace" }}>
                      {PROVIDER_LABELS[p.provider_chosen] || p.provider_chosen}
                    </span>
                    <span style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{p.total} req · {p.avg_ms}ms avg</span>
                  </div>
                  <Bar pct={(p.total / Math.max(...(stats.by_provider||[]).map(x=>x.total), 1)) * 100} warn={999} crit={999} height={5} forceColor={PROVIDER_COLORS[p.provider_chosen] || C.accent} />
                </div>
              ))}
              {!stats.by_provider?.length && <div style={{ color: C.muted, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>No data yet</div>}
            </div>
          </div>

          {/* By complexity */}
          <div>
            <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 10 }}>BY COMPLEXITY</div>
            <div style={{ display: "grid", gap: 8 }}>
              {(stats.by_complexity || []).map(c => (
                <div key={c.complexity} style={{ padding: "10px 12px", background: C.surface, borderRadius: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, color: C.accent }}>Complexity {c.complexity}</span>
                    <span style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>{c.total} req · {c.avg_latency_ms}ms avg</span>
                  </div>
                  <Bar pct={(c.total / Math.max(...(stats.by_complexity||[]).map(x=>x.total), 1)) * 100} warn={999} crit={999} height={5} forceColor={C.blue} />
                </div>
              ))}
              {!stats.by_complexity?.length && <div style={{ color: C.muted, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>No data yet</div>}
            </div>
          </div>
        </div>

        {/* Circuit breaker log */}
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 10 }}>CIRCUIT BREAKER EVENTS (24h)</div>
          {(stats.circuit_log || []).length === 0 ? (
            <div style={{ padding: "14px", background: C.greenDim, border: `1px solid ${C.green}33`, borderRadius: 8, color: C.green, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>✓ No circuit breaker events in the last 24 hours</div>
          ) : (
            <div style={{ display: "grid", gap: 6 }}>
              {(stats.circuit_log || []).map((e, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 120px 80px 80px", gap: 10, padding: "8px 12px", background: C.surface, border: `1px solid ${C.red}33`, borderRadius: 8, fontSize: 11 }}>
                  <span style={{ fontFamily: "'DM Mono', monospace", color: C.red }}>{e.provider} — {e.event}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", color: C.muted }}>{e.triggered_by}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", color: C.muted }}>{e.failure_count} failures</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", color: C.muted }}>{e.created_at?.slice(11,16)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </Accordion>

      <Accordion title="Debug — Simulator & Decision Replay" icon="🔬">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* Simulator */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: C.text, marginBottom: 12 }}>Dry-Run Simulator</div>
            <div style={{ display: "grid", gap: 10 }}>
              <div>
                <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 5 }}>INTENT</div>
                <MonoInput value={simIntent} onChange={setSimIntent} placeholder="what is the weather in Atlanta" />
              </div>
              <div>
                <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 5 }}>COMPLEXITY (1–5)</div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <input type="range" min="1" max="5" value={simComplexity} onChange={e => setSimComplexity(Number(e.target.value))} style={{ flex: 1, accentColor: C.accent }} />
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 16, color: C.accent, minWidth: 20 }}>{simComplexity}</span>
                </div>
              </div>
              <ActionBtn variant="default" onClick={simulate} loading={simulating} disabled={!simIntent.trim()}>
                ▶ Simulate
              </ActionBtn>
            </div>
            {simResult && (
              <div style={{ marginTop: 14, padding: "14px", background: C.surface, borderRadius: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                  <span style={{ fontSize: 11, color: C.muted, fontFamily: "'DM Mono', monospace" }}>WOULD CHOOSE:</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 16, color: PROVIDER_COLORS[simResult.would_choose] || C.accent }}>
                    {PROVIDER_LABELS[simResult.would_choose] || simResult.would_choose}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 6 }}>REASONING:</div>
                {(simResult.reasoning || []).map((r, i) => (
                  <div key={i} style={{ padding: "5px 10px", background: C.panel, borderRadius: 6, marginBottom: 4, fontSize: 11, fontFamily: "'DM Mono', monospace", color: C.textDim }}>→ {r}</div>
                ))}
              </div>
            )}
          </div>

          {/* Replay */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: C.text, marginBottom: 12 }}>Decision Replay</div>
            <div style={{ display: "grid", gap: 10 }}>
              <div>
                <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 5 }}>DECISION ID</div>
                <MonoInput value={replayId} onChange={setReplayId} placeholder="1" type="number" />
              </div>
              <ActionBtn variant="default" onClick={replay} loading={replaying} disabled={!replayId.trim()}>
                ↺ Replay
              </ActionBtn>
            </div>
            {replayResult && (
              <div style={{ marginTop: 14, padding: "14px", background: C.surface, borderRadius: 10 }}>
                <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 8 }}>ORIGINAL:</div>
                <div style={{ fontSize: 12, color: C.textDim, fontFamily: "'DM Mono', monospace", marginBottom: 8 }}>
                  {replayResult.original_decision?.intent?.slice(0, 60)}...
                  <br />→ {PROVIDER_LABELS[replayResult.original_decision?.provider_chosen] || replayResult.original_decision?.provider_chosen}
                </div>
                <div style={{ fontSize: 10, color: C.muted, fontFamily: "'DM Mono', monospace", marginBottom: 6 }}>WITH CURRENT WEIGHTS:</div>
                <div style={{ fontSize: 12, fontFamily: "'DM Mono', monospace", color: PROVIDER_COLORS[replayResult.replayed_with_current_weights?.would_choose] || C.accent }}>
                  → {PROVIDER_LABELS[replayResult.replayed_with_current_weights?.would_choose] || replayResult.replayed_with_current_weights?.would_choose}
                </div>
                <div style={{ marginTop: 8, padding: "6px 10px", background: replayResult.decision_changed ? C.amberDim : C.greenDim, borderRadius: 6, fontSize: 11, fontFamily: "'DM Mono', monospace", color: replayResult.decision_changed ? C.amber : C.green }}>
                  {replayResult.decision_changed ? "⚠ Decision would change with current weights" : "✓ Same decision today"}
                </div>
              </div>
            )}
          </div>
        </div>
      </Accordion>

      <Accordion title="Controls — Weights, Circuit Breakers & Recalculation" icon="🎛️">
        {ctrlMsg && (
          <div style={{ marginBottom: 14, padding: "8px 14px", background: C.greenDim, border: `1px solid ${C.green}33`, borderRadius: 8, fontSize: 11, color: C.green, fontFamily: "'DM Mono', monospace" }}>
            ✓ {ctrlMsg}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: C.text }}>Weight Overrides</div>
          <ActionBtn variant="default" onClick={recalculate} loading={recalculating}>↺ Recalculate All Weights</ActionBtn>
        </div>

        <div style={{ display: "grid", gap: 10 }}>
          {providers.map(p => (
            <div key={p.provider} style={{ display: "grid", gridTemplateColumns: "160px 1fr auto auto auto", gap: 12, alignItems: "center", padding: "12px 14px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10 }}>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: PROVIDER_COLORS[p.provider] || C.text }}>
                {PROVIDER_LABELS[p.provider] || p.provider}
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: C.muted }}>current: {p.weight?.toFixed(2)}</span>
                <MonoInput
                  type="number"
                  value={weightInputs[p.provider] ?? ""}
                  onChange={v => setWeightInputs(w => ({...w,[p.provider]:v}))}
                  placeholder={p.weight?.toFixed(2)}
                  style={{ width: 80 }}
                />
              </div>
              <ActionBtn size="sm" variant="default" onClick={() => saveWeight(p.provider)} loading={savingWeight[p.provider]} disabled={!weightInputs[p.provider]}>
                Set
              </ActionBtn>
              <ActionBtn size="sm" variant={p.circuit_open ? "danger" : "ghost"} onClick={() => resetCircuit(p.provider)} loading={resettingCircuit[p.provider]}>
                {p.circuit_open ? "Reset CB" : "CB OK"}
              </ActionBtn>
              <StatusBadge status={p.circuit_open ? "OPEN" : "CLOSED"} />
            </div>
          ))}
          {!providers.length && (
            <div style={{ color: C.muted, textAlign: "center", padding: 20, fontFamily: "'DM Mono', monospace", fontSize: 12 }}>No providers loaded</div>
          )}
        </div>
      </Accordion>
    </div>
  );
}

// ── USER TAB ───────────────────────────────────────────────────────────────────
function UserTab() {
  return (
    <div className="fade-up" style={{ display: "grid", gap: 16 }}>
      <Card>
        <div style={{ textAlign: "center", padding: "40px 20px" }}>
          <div style={{ fontSize: 64, marginBottom: 16 }}>👤</div>
          <div style={{ fontFamily: "'Syne', sans-serif", fontSize: 22, fontWeight: 700, color: C.text, marginBottom: 8 }}>Identity & Access</div>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, color: C.muted, lineHeight: 1.8, marginBottom: 24 }}>
            Phase 7 — User identity, profiles, and access control<br />
            Facial recognition · Voice auth · Password fallback<br />
            Per-user content filtering · Parental controls
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, maxWidth: 600, margin: "0 auto" }}>
            {[
              { icon: "🧑", name: "Ken", role: "Admin", phase: "Phase 7" },
              { icon: "👧", name: "Ryleigh", role: "Child (8)", phase: "Phase 7" },
              { icon: "👧", name: "Sloane",  role: "Child (5)", phase: "Phase 7" },
              { icon: "👤", name: "Guest",   role: "Limited",   phase: "Phase 7" },
            ].map(u => (
              <div key={u.name} style={{ padding: "16px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, textAlign: "center" }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>{u.icon}</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{u.name}</div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{u.role}</div>
                <div style={{ marginTop: 8 }}><StatusBadge status="TODO" /></div>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
}

// ── FALLBACK DATA ──────────────────────────────────────────────────────────────
const FALLBACK_SERVICES = [
  { name: "Ollama (Llama)",    status: "RUNNING", detail: "llama3.1:8b" },
  { name: "Ollama (Qwen)",     status: "RUNNING", detail: "qwen2.5-coder:7b" },
  { name: "Claude API",        status: "LIVE",    detail: "haiku-4-5-20251001" },
  { name: "Perplexity API",    status: "LIVE",    detail: "sonar" },
  { name: "Postgres",          status: "RUNNING", detail: "jarvis-postgres :5432" },
  { name: "Cost Tracker",      status: "LIVE",    detail: "all cloud calls logged" },
  { name: "Budget Alerts",     status: "LIVE",    detail: "75% warn / 90% critical" },
  { name: "Code Writer",       status: "LIVE",    detail: "POST /v1/code/write" },
  { name: "Branch Protection", status: "ACTIVE",  detail: "main locked — PRs required" },
  { name: "Adaptive Router",   status: "LIVE",    detail: "weight engine + circuit breakers" },
];

const FALLBACK_SECURITY = [
  { item: "Branch protection (main)",       status: "PASS", detail: "PRs required, bypass for kphaas" },
  { item: "Secrets in .gitignore",          status: "PASS", detail: ".secrets, *.key, *.pem excluded" },
  { item: "ALLOWED_WRITE_PATHS enforced",   status: "PASS", detail: "No writes outside approved dirs" },
  { item: "Bandit scan on all generations", status: "PASS", detail: "High severity auto-blocks" },
  { item: "Rate limiting active",           status: "PASS", detail: "10 writes/hr sliding window" },
  { item: "Keychain + .secrets fallback",   status: "WARN", detail: "chmod 600 — rotate periodically" },
  { item: "HTTPS on endpoints",             status: "TODO", detail: "Phase Final Hardening" },
  { item: "Token rotation policy",          status: "TODO", detail: "Phase Final Hardening" },
];

// ── ROOT APP ───────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState("summary");
  const { data, errors, lastRefresh, refreshing, refresh, countdown } = useJarvisData();

  const TABS = [
    { id: "summary",  label: "Overview",  icon: "📊" },
    { id: "health",   label: "Health",    icon: "🖥️" },
    { id: "cost",     label: "Cost",      icon: "💰" },
    { id: "code",     label: "Code",      icon: "💻" },
    { id: "errors",   label: "Errors",    icon: "⚠️" },
    { id: "security", label: "Security",  icon: "🔒" },
    { id: "routing",  label: "Routing",   icon: "🔀" },
    { id: "user",     label: "User",      icon: "👤" },
    { id: "overnight", label: "Overnight", icon: "🌙" },
  ];

  const nodes = [
    { label: "Brain",    ok: !!data?.brainMetrics && !errors.brainMetrics },
    { label: "Gateway",  ok: !!data?.gwMetrics    && !errors.gwMetrics },
    { label: "Endpoint", ok: !!data?.epMetrics    && !errors.epMetrics },
  ];

  const daily      = data?.costs?.budget?.daily;
  const errorCount = Object.keys(errors).length;
  const hasAlerts  = errorCount > 0;
  const creditData  = data?.costs?.credit || {};
  const lowCredit   = creditData.low_balance === true;

  const tabBadge = id => {
    if (id === "errors"  && errorCount > 0) return errorCount;
    return null;
  };

  return (
    <>
      <style>{GLOBAL_CSS}</style>
      <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: C.bg }}>

        {/* Alert bar */}
        {(hasAlerts || lowCredit) && (
          <div style={{
            background: C.redDim, borderBottom: `1px solid ${C.red}44`,
            padding: "5px 24px", fontSize: 11, color: C.red,
            fontFamily: "'DM Mono', monospace",
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <span>⚠</span>
            {lowCredit && <span style={{ color: "#ff4444", fontWeight: 700 }}>ANTHROPIC CREDIT LOW: ${creditData.remaining_usd?.toFixed(2)} remaining — top up at console.anthropic.com</span>}
            <span>{errorCount} endpoint(s) unreachable: {Object.keys(errors).slice(0,4).join(", ")}{errorCount>4?" …":""}</span>
            <span style={{ marginLeft: "auto", color: C.muted }}>Check Errors tab for details</span>
          </div>
        )}

        {/* Header */}
        <header style={{
          display: "flex", alignItems: "center", gap: 16,
          padding: "0 24px", height: 60,
          background: C.surface, borderBottom: `1px solid ${C.border}`,
          position: "sticky", top: 0, zIndex: 100,
        }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.accent, boxShadow: `0 0 10px ${C.accent}`, animation: "pulse 2s infinite" }} />
            <span style={{ fontFamily: "'Syne', sans-serif", fontSize: 20, fontWeight: 800, color: C.accent, letterSpacing: 3 }}>JARVIS</span>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 9, color: C.muted }}>v3.0</span>
          </div>

          {/* Tabs */}
          <nav style={{ display: "flex", flex: 1, overflowX: "auto" }}>
            {TABS.map(t => {
              const badge   = tabBadge(t.id);
              const isActive = tab === t.id;
              return (
                <button key={t.id} onClick={() => setTab(t.id)} style={{
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2,
                  padding: "0 16px", height: 60, border: "none", cursor: "pointer",
                  background: "transparent",
                  borderBottom: isActive ? `2px solid ${C.accent}` : "2px solid transparent",
                  color: isActive ? C.accent : C.muted,
                  fontFamily: "'Syne', sans-serif", fontSize: 10, fontWeight: 600,
                  letterSpacing: 1, transition: "color 0.15s", position: "relative",
                  flexShrink: 0,
                }}>
                  <span style={{ fontSize: 15 }}>{t.icon}</span>
                  <span>{t.label.toUpperCase()}</span>
                  {badge && (
                    <span style={{ position: "absolute", top: 8, right: 8, width: 14, height: 14, borderRadius: "50%", background: C.red, color: "#fff", fontSize: 8, fontWeight: 900, display: "flex", alignItems: "center", justifyContent: "center" }}>
                      {badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right: node health + cost + countdown */}
          <div style={{ display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
            <div style={{ display: "flex", gap: 12 }}>
              {nodes.map(n => (
                <div key={n.label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <div style={{ width: 7, height: 7, borderRadius: "50%", background: n.ok ? C.green : C.red, boxShadow: `0 0 6px ${n.ok ? C.green : C.red}` }} />
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 9, color: C.muted }}>{n.label}</span>
                </div>
              ))}
            </div>

            {daily && (
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, borderLeft: `1px solid ${C.border}`, paddingLeft: 16 }}>
                <span style={{ color: C.muted }}>$</span>
                <span style={{ color: C.accent }}>{(daily.spent_usd || 0).toFixed(3)}</span>
                <span style={{ color: C.muted }}>/{(daily.limit_usd || 0).toFixed(2)}</span>
                <span style={{ color: C.muted, fontSize: 9, marginLeft: 4 }}>today</span>
              </div>
            )}

            <button onClick={refresh} disabled={refreshing} style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "5px 12px", borderRadius: 8,
              border: `1px solid ${C.border}`, background: "transparent",
              cursor: "pointer", color: C.textDim,
              fontFamily: "'DM Mono', monospace", fontSize: 10,
              transition: "all 0.15s",
            }}>
              <span style={{ color: refreshing ? C.muted : C.accent }}>↺</span>
              <span>{refreshing ? "···" : `${countdown}s`}</span>
            </button>
          </div>
        </header>

        {/* Main */}
        <main style={{ flex: 1, padding: "22px 28px", maxWidth: 1440, width: "100%", margin: "0 auto" }}>
          {tab === "summary"  && <SummaryTab    data={data} errors={errors} />}
          {tab === "health"   && <HealthTab     data={data} errors={errors} />}
          {tab === "cost"     && <CostTab       data={data} errors={errors} />}
          {tab === "code"     && <CodeReviewTab data={data} errors={errors} />}
          {tab === "errors"   && <ErrorsTab     data={data} errors={errors} />}
          {tab === "security" && <SecurityTab   data={data} />}
          {tab === "routing"  && <RoutingTab    data={data} errors={errors} />}
          {tab === "user"     && <UserTab />}
          {tab === "overnight" && <OvernightTab data={data} errors={errors} />}
        </main>

        {/* Footer */}
        <footer style={{ padding: "8px 24px", borderTop: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center", background: C.surface }}>
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 9, color: C.muted, letterSpacing: 1 }}>
            JARVIS PRIVATE AI INFRASTRUCTURE · TAILSCALE VPN · BRANCH PROTECTION ACTIVE
          </span>
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 9, color: C.muted }}>
            {lastRefresh ? `LAST SYNC ${lastRefresh.toLocaleTimeString()}` : "CONNECTING..."}
          </span>
        </footer>
      </div>
    </>
  );
}
