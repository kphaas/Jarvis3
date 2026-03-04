import { useState, useEffect, useCallback, useRef } from "react";

// ── CONFIG ────────────────────────────────────────────────────────────────────
const BRAIN    = "http://100.64.166.22:8182";
const GATEWAY  = "http://100.112.63.25:8282";
const ENDPOINT = "http://100.87.223.31:3000";
const REFRESH_MS = 15000;

// ── DESIGN TOKENS ─────────────────────────────────────────────────────────────
const C = {
  bg:       "#050a0e",
  surface:  "#080f14",
  panel:    "#0a1520",
  border:   "#0e2233",
  borderHi: "#1a3a55",
  green:    "#00e5a0",
  greenDim: "#00e5a022",
  amber:    "#f5a623",
  amberDim: "#f5a62322",
  red:      "#ff3b5c",
  redDim:   "#ff3b5c22",
  blue:     "#0af",
  blueDim:  "#00aaff18",
  text:     "#c8d8e8",
  muted:    "#4a6070",
  dim:      "#243040",
};

const statusMeta = (s) => {
  const m = {
    STABLE:   [C.green, "STABLE"],   RUNNING:  [C.green, "RUN"],
    LIVE:     [C.green, "LIVE"],     ACTIVE:   [C.green, "ACTIVE"],
    PASS:     [C.green, "PASS"],     ONLINE:   [C.green, "ONLINE"],
    WARN:     [C.amber, "WARN"],     WARNING:  [C.amber, "WARN"],
    TODO:     [C.amber, "TODO"],     IDLE:     [C.amber, "IDLE"],
    ERROR:    [C.red,   "ERR"],      FAIL:     [C.red,   "FAIL"],
    INACTIVE: [C.muted, "IDLE"],     CRITICAL: [C.red,   "CRIT"],
    INFO:     [C.blue,  "INFO"],     DEGRADED: [C.amber, "DEGRADED"],
  };
  return m[s?.toUpperCase()] || [C.muted, s || "—"];
};

// ── GLOBAL STYLES ─────────────────────────────────────────────────────────────
const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&family=Orbitron:wght@400;700;900&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body, #root { height: 100%; }
  body {
    background: ${C.bg};
    color: ${C.text};
    font-family: 'Rajdhani', sans-serif;
    font-size: 15px;
    overflow-x: hidden;
  }
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: ${C.surface}; }
  ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 2px; }
  ::-webkit-scrollbar-thumb:hover { background: ${C.borderHi}; }
  .mono { font-family: 'Share Tech Mono', monospace; }
  .scan-line {
    pointer-events: none;
    position: fixed; inset: 0; z-index: 9999;
    background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.04) 2px, rgba(0,0,0,0.04) 4px);
  }
  .glow-green { text-shadow: 0 0 8px ${C.green}88; }
  .glow-red   { text-shadow: 0 0 8px ${C.red}88; }
  .glow-amber { text-shadow: 0 0 8px ${C.amber}88; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  @keyframes blink { 0%,100%{opacity:1} 49%{opacity:1} 50%{opacity:0} }
  @keyframes slideIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }
  @keyframes scan { from{transform:translateY(-100%)} to{transform:translateY(100vh)} }
  .fade-in { animation: slideIn 0.25s ease; }
`;

// ── PRIMITIVE COMPONENTS ──────────────────────────────────────────────────────
function Pill({ status, size = "sm" }) {
  const [color, label] = statusMeta(status);
  const pad = size === "sm" ? "1px 7px" : "3px 10px";
  return (
    <span style={{
      display: "inline-block", padding: pad, borderRadius: 2,
      fontSize: 10, fontWeight: 700, letterSpacing: 1.5,
      fontFamily: "'Share Tech Mono', monospace",
      color, background: color + "18", border: `1px solid ${color}44`,
    }}>{label}</span>
  );
}

function Bar({ pct, warn = 75, crit = 90, height = 5 }) {
  const color = pct >= crit ? C.red : pct >= warn ? C.amber : C.green;
  return (
    <div style={{ position: "relative", height, background: C.dim, borderRadius: 1 }}>
      <div style={{
        width: `${Math.min(pct, 100)}%`, height: "100%",
        background: color, borderRadius: 1,
        boxShadow: `0 0 6px ${color}66`,
        transition: "width 0.8s cubic-bezier(0.4,0,0.2,1)",
      }} />
    </div>
  );
}

function Card({ children, style = {}, className = "" }) {
  return (
    <div className={className} style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 4, padding: "16px 18px",
      ...style,
    }}>{children}</div>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontFamily: "'Share Tech Mono', monospace",
      fontSize: 10, letterSpacing: 3, color: C.muted,
      textTransform: "uppercase", marginBottom: 12,
      display: "flex", alignItems: "center", gap: 8,
    }}>
      <span style={{ flex: 1, height: 1, background: C.border }} />
      {children}
      <span style={{ flex: 1, height: 1, background: C.border }} />
    </div>
  );
}

function ActionBtn({ children, onClick, variant = "default", disabled = false, loading = false }) {
  const colors = {
    default: [C.blue, C.blueDim],
    danger:  [C.red, C.redDim],
    success: [C.green, C.greenDim],
    warning: [C.amber, C.amberDim],
  };
  const [color, bg] = colors[variant] || colors.default;
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        padding: "6px 14px", borderRadius: 2, cursor: disabled ? "not-allowed" : "pointer",
        border: `1px solid ${color}66`, background: loading ? bg : "transparent",
        color, fontFamily: "'Rajdhani', sans-serif", fontWeight: 600,
        fontSize: 12, letterSpacing: 1, opacity: disabled ? 0.4 : 1,
        transition: "all 0.15s", whiteSpace: "nowrap",
      }}
      onMouseEnter={e => { if (!disabled) e.target.style.background = bg; }}
      onMouseLeave={e => { if (!disabled) e.target.style.background = "transparent"; }}
    >
      {loading ? "..." : children}
    </button>
  );
}

// ── API LAYER ─────────────────────────────────────────────────────────────────
async function apiFetch(url, opts = {}) {
  try {
    const r = await fetch(url, { ...opts, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return [await r.json(), null];
  } catch (e) {
    return [null, e.message];
  }
}

// ── LIVE DATA HOOK ────────────────────────────────────────────────────────────
function useJarvisData() {
  const [data, setData] = useState(null);
  const [errors, setErrors] = useState({});
  const [lastRefresh, setLastRefresh] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetch_all = useCallback(async () => {
    setRefreshing(true);
    const errs = {};
    const results = {};

    // Health
    const [health, hErr] = await apiFetch(`${BRAIN}/v1/health/full`);
    if (health) results.health = health; else errs.health = hErr;

    // Costs
    const [costs, cErr] = await apiFetch(`${BRAIN}/v1/costs`);
    if (costs) results.costs = costs; else errs.costs = cErr;

    // Code write log
    const [codeLog, clErr] = await apiFetch(`${BRAIN}/v1/code/log`);
    if (codeLog) results.codeLog = codeLog; else errs.codeLog = clErr;

    // Agents
    const [agents, aErr] = await apiFetch(`${BRAIN}/v1/agents`);
    if (agents) results.agents = agents; else errs.agents = aErr;

    // Metrics per node
    const [brainMetrics, bmErr] = await apiFetch(`${BRAIN}/v1/metrics`);
    if (brainMetrics) results.brainMetrics = brainMetrics; else errs.brainMetrics = bmErr;

    const [gwMetrics, gmErr] = await apiFetch(`${GATEWAY}/v1/metrics`);
    if (gwMetrics) results.gwMetrics = gwMetrics; else errs.gwMetrics = gmErr;

    const [epMetrics, emErr] = await apiFetch(`${ENDPOINT}/v1/metrics`);
    if (epMetrics) results.epMetrics = epMetrics; else errs.epMetrics = emErr;


    setData(prev => ({ ...prev, ...results }));
    setErrors(errs);
    setLastRefresh(new Date());
    setRefreshing(false);
  }, []);

  useEffect(() => {
    fetch_all();
    const id = setInterval(fetch_all, REFRESH_MS);
    return () => clearInterval(id);
  }, [fetch_all]);

  return { data, errors, lastRefresh, refreshing, refresh: fetch_all };
}

// ── SUMMARY TAB ───────────────────────────────────────────────────────────────
function SummaryTab({ data, errors, onAction }) {
  const health = data?.health || {};
  const costs = data?.costs || {};
  const agents = data?.agents || [];
  const codeLog = data?.codeLog || [];

  const nodes = [
    { name: "BRAIN", key: "brain", host: "100.64.166.22", port: 8182, metrics: data?.brainMetrics },
    { name: "GATEWAY", key: "gw", host: "100.112.63.25", port: 8282, metrics: data?.gwMetrics },
    { name: "ENDPOINT", key: "ep", host: "100.87.223.31", port: 3000, metrics: data?.epMetrics },
  ];

  const dailyPct  = costs.budget?.daily ? (costs.budget.daily.spent_usd / costs.budget.daily.limit_usd  * 100) : 0;
  const weeklyPct = costs.budget?.weekly ? (costs.budget.weekly.spent_usd / costs.budget.weekly.limit_usd * 100) : 0;
  const monthPct  = costs.budget?.monthly? (costs.budget.monthly.spent_usd/ costs.budget.monthly.limit_usd* 100) : 0;

  const activeAgents = agents.filter(a => a.status === "ACTIVE").length;
  const recentErrors = (data?.errors || []).filter(e => e.level === "ERROR").length;
  const openPRs = (data?.prs || []).length;
  const nodesOnline = nodes.filter(n => n.metrics && !errors[`${n.name.toLowerCase()}Metrics`]).length;

  return (
    <div className="fade-in" style={{ display: "grid", gap: 16 }}>

      {/* KPI strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
        {[
          { label: "NODES ONLINE",   value: `${nodesOnline}/3`,        color: nodesOnline===3?C.green:C.amber },
          { label: "TODAY SPEND",    value: `$${(costs.daily?.spent||0).toFixed(2)}`, color: dailyPct>=90?C.red:dailyPct>=75?C.amber:C.green },
          { label: "ACTIVE AGENTS",  value: activeAgents,               color: C.blue },
          { label: "OPEN PRs",       value: openPRs,                    color: openPRs>0?C.amber:C.green },
        ].map(k => (
          <Card key={k.label} style={{ textAlign: "center", padding: "20px 12px" }}>
            <div style={{ fontFamily: "'Orbitron', monospace", fontSize: 28, fontWeight: 900,
                          color: k.color, textShadow: `0 0 20px ${k.color}66` }}>{k.value}</div>
            <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted, marginTop: 6,
                          fontFamily: "'Share Tech Mono', monospace" }}>{k.label}</div>
          </Card>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Node status */}
        <Card>
          <SectionLabel>NODE STATUS</SectionLabel>
          <div style={{ display: "grid", gap: 10 }}>
            {nodes.map(node => {
              const m = node.metrics;
              const ok = m && !errors[`${node.key||node.name.toLowerCase()}Metrics`];
              return (
                <div key={node.name} style={{
                  display: "grid", gridTemplateColumns: "80px 1fr auto",
                  alignItems: "center", gap: 12, padding: "10px 14px",
                  background: C.surface, border: `1px solid ${C.border}`, borderRadius: 3,
                }}>
                  <div>
                    <div style={{ fontFamily: "'Orbitron', monospace", fontSize: 11,
                                  color: ok ? C.green : C.red, fontWeight: 700 }}>{node.name}</div>
                    <div style={{ fontSize: 10, color: C.muted, fontFamily: "'Share Tech Mono', monospace" }}>
                      :{node.port}
                    </div>
                  </div>
                  {ok ? (
                    <div style={{ display: "grid", gap: 4 }}>
                      {[["CPU", m.cpu_pct, 80, 95], ["RAM", m.ram_pct, 75, 90], ["DSK", m.disk_pct, 80, 95]].map(([lbl, val, w, c]) => (
                        <div key={lbl} style={{ display: "grid", gridTemplateColumns: "28px 1fr 32px", gap: 6, alignItems: "center" }}>
                          <span style={{ fontSize: 9, color: C.muted, fontFamily: "'Share Tech Mono', monospace" }}>{lbl}</span>
                          <Bar pct={val || 0} warn={w} crit={c} height={4} />
                          <span style={{ fontSize: 9, color: C.muted, textAlign: "right", fontFamily: "'Share Tech Mono', monospace" }}>{(val||0).toFixed(0)}%</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: 11, color: C.red, fontFamily: "'Share Tech Mono', monospace" }}>
                      {errors[`${node.name.toLowerCase()}Metrics`] || "UNREACHABLE"}
                    </div>
                  )}
                  <Pill status={ok ? "ONLINE" : "ERROR"} />
                </div>
              );
            })}
          </div>
        </Card>

        {/* Budget overview */}
        <Card>
          <SectionLabel>BUDGET STATUS</SectionLabel>
          <div style={{ display: "grid", gap: 14 }}>
            {[
              ["DAILY",   costs.budget?.daily,   dailyPct],
              ["WEEKLY",  costs.budget?.weekly,  weeklyPct],
              ["MONTHLY", costs.budget?.monthly, monthPct],
            ].map(([lbl, b, pct]) => (
              <div key={lbl}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 11, letterSpacing: 2, color: C.muted,
                                 fontFamily: "'Share Tech Mono', monospace" }}>{lbl}</span>
                  <span style={{ fontFamily: "'Orbitron', monospace", fontSize: 12,
                                 color: pct>=90?C.red:pct>=75?C.amber:C.green }}>
                    ${(b?.spent_usd||0).toFixed(4)} / ${(b?.limit_usd||0).toFixed(2)}
                  </span>
                </div>
                <Bar pct={pct} height={6} />
                <div style={{ fontSize: 10, color: C.muted, marginTop: 4, textAlign: "right",
                              fontFamily: "'Share Tech Mono', monospace" }}>
                  {pct.toFixed(1)}% utilized
                  {pct >= 75 && <span style={{ color: pct>=90?C.red:C.amber, marginLeft: 8 }}>
                    ⚠ {pct>=90?"CRITICAL":"WARNING"}
                  </span>}
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
            <ActionBtn onClick={() => onAction("updateBudget")} variant="warning">UPDATE LIMITS</ActionBtn>
          </div>
        </Card>
      </div>

      {/* Service matrix */}
      <Card>
        <SectionLabel>SERVICE MATRIX</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8 }}>
          {(health.services || FALLBACK_SERVICES).map(svc => (
            <div key={svc.name} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "8px 12px", background: C.surface,
              border: `1px solid ${C.border}`, borderRadius: 3,
            }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: C.text }}>{svc.name}</div>
                <div style={{ fontSize: 10, color: C.muted, fontFamily: "'Share Tech Mono', monospace" }}>{svc.detail}</div>
              </div>
              <Pill status={svc.status} />
            </div>
          ))}
        </div>
      </Card>

      {/* Recent code activity */}
      <Card>
        <SectionLabel>RECENT CODE WRITES</SectionLabel>
        <div style={{ display: "grid", gap: 6 }}>
          {(codeLog.slice(0,5) || []).map((entry, i) => (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "70px 1fr auto auto auto",
              gap: 12, alignItems: "center", padding: "8px 12px",
              background: C.surface, border: `1px solid ${C.border}`, borderRadius: 3,
              fontSize: 12,
            }}>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: C.muted }}>{entry.ts}</span>
              <span style={{ color: C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.intent}</span>
              <Pill status={entry.lint === "PASS" ? "PASS" : "FAIL"} />
              <Pill status={entry.security === "PASS" ? "PASS" : "FAIL"} />
              <Pill status={entry.success ? "STABLE" : "ERROR"} />
            </div>
          ))}
          {!codeLog.length && <div style={{ color: C.muted, fontSize: 12, textAlign: "center", padding: 20 }}>No data — check /v1/code/log endpoint</div>}
        </div>
      </Card>
    </div>
  );
}

// ── HEALTH TAB ────────────────────────────────────────────────────────────────
function HealthTab({ data, errors, onAction }) {
  const [restarting, setRestarting] = useState({});
  const nodes = [
    { key: "brain",    label: "BRAIN",    host: "100.64.166.22", port: 8182, metrics: data?.brainMetrics },
    { key: "gateway",  label: "GATEWAY",  host: "100.112.63.25", port: 8282, metrics: data?.gwMetrics },
    { key: "endpoint", label: "ENDPOINT", host: "100.87.223.31",  port: 3000, metrics: data?.epMetrics },
  ];

  const handleRestart = async (nodeKey) => {
    setRestarting(r => ({ ...r, [nodeKey]: true }));
    await apiFetch(`${BRAIN}/v1/admin/restart/${nodeKey}`, { method: "POST" });
    setTimeout(() => setRestarting(r => ({ ...r, [nodeKey]: false })), 3000);
  };

  return (
    <div className="fade-in" style={{ display: "grid", gap: 16 }}>
      {nodes.map(node => {
        const m = node.metrics;
        const ok = m && !errors[`${node.key}Metrics`];
        return (
          <Card key={node.key}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ fontFamily: "'Orbitron', monospace", fontSize: 16, fontWeight: 900,
                              color: ok ? C.green : C.red }}>{node.label}</div>
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, color: C.muted }}>
                  {node.host}:{node.port}
                </span>
                <Pill status={ok ? "ONLINE" : "ERROR"} />
              </div>
              <ActionBtn
                variant="warning"
                loading={restarting[node.key]}
                onClick={() => handleRestart(node.key)}
              >RESTART NODE</ActionBtn>
            </div>
            {ok ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14 }}>
                {[
                  { label: "CPU UTILIZATION", value: m.cpu_pct, unit: "%", warn: 80, crit: 95 },
                  { label: "RAM UTILIZATION", value: m.ram_pct, unit: "%", warn: 75, crit: 90 },
                  { label: "DISK UTILIZATION", value: m.disk_pct, unit: "%", warn: 80, crit: 95 },
                ].map(metric => (
                  <div key={metric.label} style={{
                    padding: "14px 16px", background: C.surface,
                    border: `1px solid ${C.border}`, borderRadius: 3,
                  }}>
                    <div style={{ fontSize: 9, letterSpacing: 2, color: C.muted,
                                  fontFamily: "'Share Tech Mono', monospace", marginBottom: 8 }}>{metric.label}</div>
                    <div style={{ fontFamily: "'Orbitron', monospace", fontSize: 24, fontWeight: 700,
                                  color: (metric.value||0)>=metric.crit?C.red:(metric.value||0)>=metric.warn?C.amber:C.green }}>
                      {(metric.value||0).toFixed(1)}<span style={{ fontSize: 12, color: C.muted }}>{metric.unit}</span>
                    </div>
                    <div style={{ marginTop: 10 }}>
                      <Bar pct={metric.value||0} warn={metric.warn} crit={metric.crit} height={5} />
                    </div>
                    {m[`${metric.label.split(" ")[0].toLowerCase()}_detail`] && (
                      <div style={{ fontSize: 10, color: C.muted, marginTop: 6,
                                    fontFamily: "'Share Tech Mono', monospace" }}>
                        {m[`${metric.label.split(" ")[0].toLowerCase()}_detail`]}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{
                padding: "24px", textAlign: "center", background: C.surface,
                border: `1px solid ${C.red}44`, borderRadius: 3,
                color: C.red, fontFamily: "'Share Tech Mono', monospace", fontSize: 12,
              }}>
                NODE UNREACHABLE — {errors[`${node.key}Metrics`] || "No response"}
                <div style={{ marginTop: 12 }}>
                  <ActionBtn variant="danger" onClick={() => handleRestart(node.key)} loading={restarting[node.key]}>
                    ATTEMPT RESTART
                  </ActionBtn>
                </div>
              </div>
            )}
            {ok && m.uptime && (
              <div style={{ marginTop: 12, fontSize: 11, color: C.muted,
                            fontFamily: "'Share Tech Mono', monospace" }}>
                UPTIME: {m.uptime} &nbsp;|&nbsp; LOAD: {m.load_avg || "—"} &nbsp;|&nbsp; PROCESSES: {m.process_count || "—"}
              </div>
            )}
          </Card>
        );
      })}

      {/* Services */}
      <Card>
        <SectionLabel>SERVICES & DAEMONS</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8 }}>
          {(data?.health?.services || FALLBACK_SERVICES).map(svc => (
            <div key={svc.name} style={{
              padding: "12px 14px", background: C.surface,
              border: `1px solid ${C.border}`, borderRadius: 3,
              display: "flex", justifyContent: "space-between", alignItems: "flex-start",
            }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: 3 }}>{svc.name}</div>
                <div style={{ fontSize: 10, color: C.muted, fontFamily: "'Share Tech Mono', monospace" }}>{svc.detail}</div>
              </div>
              <Pill status={svc.status} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ── COST TAB ──────────────────────────────────────────────────────────────────

function ElectricityCost({ data }) {
  const [ratePerKwh, setRatePerKwh] = useState(() => {
    try { return parseFloat(localStorage.getItem("jarvis_kwh_rate") || "0.12"); } catch { return 0.12; }
  });
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  const nodes = [
    { label: "BRAIN",    metrics: data?.brainMetrics },
    { label: "GATEWAY",  metrics: data?.gwMetrics },
    { label: "ENDPOINT", metrics: data?.epMetrics },
  ];

  const totalW = nodes.reduce((sum, n) => sum + (n.metrics?.power_w || 0), 0);
  const dailyKwh   = totalW * 24 / 1000;
  const monthlyKwh = dailyKwh * 30;
  const dailyCost   = dailyKwh * ratePerKwh;
  const monthlyCost = monthlyKwh * ratePerKwh;

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
      <SectionLabel>⚡ ELECTRICITY COST</SectionLabel>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr 1fr", gap:12, marginBottom:16 }}>
        {nodes.map(n => (
          <div key={n.label} style={{ padding:"12px 14px", background:C.surface, border:`1px solid ${C.border}`, borderRadius:3 }}>
            <div style={{ fontSize:9, letterSpacing:2, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginBottom:6 }}>{n.label}</div>
            <div style={{ fontFamily:"'Orbitron', monospace", fontSize:18, fontWeight:700, color:C.green }}>
              {n.metrics ? `${n.metrics.power_w}W` : "—"}
            </div>
            <div style={{ fontSize:10, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginTop:3 }}>
              {n.metrics ? `${(n.metrics.power_w * 24 / 1000).toFixed(3)} kWh/day` : "offline"}
            </div>
          </div>
        ))}
        <div style={{ padding:"12px 14px", background:C.panel, border:`1px solid ${C.borderHi}`, borderRadius:3 }}>
          <div style={{ fontSize:9, letterSpacing:2, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginBottom:6 }}>TOTAL DRAW</div>
          <div style={{ fontFamily:"'Orbitron', monospace", fontSize:18, fontWeight:700, color:C.amber }}>{totalW.toFixed(2)}W</div>
          <div style={{ fontSize:10, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginTop:3 }}>{dailyKwh.toFixed(3)} kWh/day</div>
        </div>
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr auto", gap:12, alignItems:"center", padding:"14px 16px", background:C.surface, border:`1px solid ${C.border}`, borderRadius:3 }}>
        <div>
          <div style={{ fontSize:9, letterSpacing:2, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginBottom:4 }}>DAILY ELEC COST</div>
          <div style={{ fontFamily:"'Orbitron', monospace", fontSize:22, fontWeight:700, color:C.green }}>${dailyCost.toFixed(4)}</div>
          <div style={{ fontSize:10, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginTop:2 }}>{dailyKwh.toFixed(4)} kWh × ${ratePerKwh}/kWh</div>
        </div>
        <div>
          <div style={{ fontSize:9, letterSpacing:2, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginBottom:4 }}>MONTHLY ELEC COST</div>
          <div style={{ fontFamily:"'Orbitron', monospace", fontSize:22, fontWeight:700, color:C.amber }}>${monthlyCost.toFixed(2)}</div>
          <div style={{ fontSize:10, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginTop:2 }}>{monthlyKwh.toFixed(2)} kWh × 30 days</div>
        </div>
        <div style={{ display:"flex", flexDirection:"column", gap:8, alignItems:"flex-end" }}>
          <div style={{ fontSize:9, letterSpacing:2, color:C.muted, fontFamily:"'Share Tech Mono', monospace" }}>RATE ($/kWh)</div>
          {editing ? (
            <div style={{ display:"flex", gap:8 }}>
              <input autoFocus type="number" step="0.01" placeholder={ratePerKwh} value={draft} onChange={e=>setDraft(e.target.value)}
                style={{ width:80, padding:"5px 8px", background:C.panel, border:`1px solid ${C.borderHi}`, borderRadius:3, color:C.text, fontFamily:"'Share Tech Mono', monospace", fontSize:13 }} />
              <ActionBtn variant="success" onClick={save}>SAVE</ActionBtn>
            </div>
          ) : (
            <div style={{ display:"flex", gap:8, alignItems:"center" }}>
              <span style={{ fontFamily:"'Orbitron', monospace", fontSize:16, color:C.text }}>${ratePerKwh}</span>
              <ActionBtn onClick={() => { setDraft(ratePerKwh.toString()); setEditing(true); }}>EDIT</ActionBtn>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function CostTab({ data, errors, onAction }) {
  const costs = data?.costs || {};
  const [editing, setEditing] = useState(false);
  const [budgetForm, setBudgetForm] = useState({ daily: "", weekly: "", monthly: "" });
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  const saveBudget = async () => {
    setSaving(true);
    const periods = ["daily","weekly","monthly"];
    for (const p of periods) {
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
    { key: "daily",   label: "DAILY",   b: costs.budget?.daily },
    { key: "weekly",  label: "WEEKLY",  b: costs.budget?.weekly },
    { key: "monthly", label: "MONTHLY", b: costs.budget?.monthly },
  ];

  return (
    <div className="fade-in" style={{ display: "grid", gap: 16 }}>
      <ElectricityCost data={data} />
      {/* Budget bars */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
        {periods.map(({ key, label, b }) => {
          const pct = b ? (b.spent_usd / b.limit_usd * 100) : 0;
          const color = pct >= 90 ? C.red : pct >= 75 ? C.amber : C.green;
          return (
            <Card key={key}>
              <div style={{ fontSize: 9, letterSpacing: 3, color: C.muted,
                            fontFamily: "'Share Tech Mono', monospace", marginBottom: 10 }}>{label} BUDGET</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                <span style={{ fontFamily: "'Orbitron', monospace", fontSize: 26, fontWeight: 900, color }}>
                  ${(b?.spent_usd||0).toFixed(4)}
                </span>
                <span style={{ fontSize: 12, color: C.muted }}>/ ${(b?.limit_usd||0).toFixed(2)}</span>
              </div>
              <div style={{ margin: "10px 0" }}><Bar pct={pct} height={6} /></div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10,
                            color: C.muted, fontFamily: "'Share Tech Mono', monospace" }}>
                <span>${((b?.limit_usd||0)-(b?.spent_usd||0)).toFixed(4)} remaining</span>
                <span style={{ color }}>{pct.toFixed(1)}%</span>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Budget editor */}
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <SectionLabel>UPDATE BUDGET LIMITS</SectionLabel>
          {saveMsg && <span style={{ fontSize: 11, color: C.green, fontFamily: "'Share Tech Mono', monospace" }}>{saveMsg}</span>}
        </div>
        {editing ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr) auto auto", gap: 10, alignItems: "flex-end" }}>
            {["daily","weekly","monthly"].map(p => (
              <div key={p}>
                <div style={{ fontSize: 10, color: C.muted, fontFamily: "'Share Tech Mono', monospace",
                              letterSpacing: 2, marginBottom: 5 }}>{p.toUpperCase()} LIMIT ($)</div>
                <input
                  type="number" step="0.01"
                  placeholder={(costs[p]?.limit||0).toFixed(2)}
                  value={budgetForm[p]}
                  onChange={e => setBudgetForm(f => ({ ...f, [p]: e.target.value }))}
                  style={{
                    width: "100%", padding: "7px 10px", background: C.surface,
                    border: `1px solid ${C.borderHi}`, borderRadius: 3,
                    color: C.text, fontFamily: "'Share Tech Mono', monospace", fontSize: 13,
                  }}
                />
              </div>
            ))}
            <ActionBtn variant="success" onClick={saveBudget} loading={saving}>SAVE</ActionBtn>
            <ActionBtn onClick={() => setEditing(false)}>CANCEL</ActionBtn>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <ActionBtn variant="warning" onClick={() => setEditing(true)}>EDIT LIMITS</ActionBtn>
            <span style={{ fontSize: 11, color: C.muted, fontFamily: "'Share Tech Mono', monospace" }}>
              Current: Daily ${(costs.daily?.limit||0).toFixed(2)} | Weekly ${(costs.weekly?.limit||0).toFixed(2)} | Monthly ${(costs.monthly?.limit||0).toFixed(2)}
            </span>
          </div>
        )}
      </Card>

      {/* Spend by provider */}
      <Card>
        <SectionLabel>SPEND BY PROVIDER</SectionLabel>
        <div style={{ display: "grid", gap: 8 }}>
          {(costs.by_provider || []).map(row => {
            const maxSpend = Math.max(...(costs.by_provider||[]).map(r=>r.cost_usd||0), 1);
            return (
              <div key={row.provider} style={{
                display: "grid", gridTemplateColumns: "160px 1fr 60px 80px",
                gap: 14, alignItems: "center", padding: "10px 14px",
                background: C.surface, border: `1px solid ${C.border}`, borderRadius: 3,
              }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{row.provider}</span>
                <Bar pct={(row.cost_usd / maxSpend) * 100} warn={999} crit={999} height={5} />
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
                              color: C.muted, textAlign: "right" }}>{row.calls} calls</span>
                <span style={{ fontFamily: "'Orbitron', monospace", fontSize: 13,
                              color: row.total === 0 ? C.green : C.text, textAlign: "right" }}>
                  ${(row.cost_usd||0).toFixed(4)}
                </span>
              </div>
            );
          })}
          {false && <div></div>}
        </div>
      </Card>

      {/* Daily history */}
      <Card>
        <SectionLabel>DAILY SPEND — LAST 7 DAYS</SectionLabel>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", height: 120 }}>
          {(Object.entries((costs.by_day||[]).reduce((acc,r)=>{acc[r.day]=(acc[r.day]||0)+r.cost_usd;return acc;},{})).map(([day,cost_usd])=>({day,cost_usd}))).map((d, i) => {
            const max = Math.max(...(costs.history||[]).map(x=>x.cost||0), 0.01);
            const h = ((d.cost / max) * 90);
            const color = d.cost_usd >= (costs.budget?.daily?.limit_usd||2) * 0.9 ? C.red
                        : d.cost_usd >= (costs.budget?.daily?.limit_usd||2) * 0.75 ? C.amber : C.green;
            return (
              <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 5 }}>
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: C.muted }}>
                  ${(d.cost_usd||0).toFixed(4)}
                </span>
                <div style={{
                  width: "100%", height: h, background: color,
                  borderRadius: "2px 2px 0 0", boxShadow: `0 0 8px ${color}55`,
                  opacity: 0.85,
                }} />
                <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: C.muted }}>{d.day?.slice(5,10)}</span>
              </div>
            );
          })}
          {!costs.history?.length && <div style={{ color: C.muted, textAlign: "center", width: "100%", fontSize: 12 }}>No history data</div>}
        </div>
      </Card>
    </div>
  );
}

// ── CODE REVIEW TAB ───────────────────────────────────────────────────────────
function CodeReviewTab({ data, errors, onAction }) {
  const [prs, setPRs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [acting, setActing] = useState({});
  const [msg, setMsg] = useState("");
  const [codeIntent, setCodeIntent] = useState("");
  const [codeFile, setCodeFile] = useState("");
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    // Fetch real PRs from GitHub via Brain
    apiFetch(`${BRAIN}/v1/github/prs`).then(([d]) => { if (d) setPRs(d); });
  }, []);

  const handleApprove = async (pr) => {
    setActing(a => ({ ...a, [pr.id]: "approving" }));
    const [res, err] = await apiFetch(`${BRAIN}/v1/github/prs/${pr.id}/merge`, { method: "POST" });
    if (!err) {
      setMsg(`PR #${pr.id} merged ✓`);
      setPRs(p => p.filter(x => x.id !== pr.id));
    } else {
      setMsg(`Error: ${err}`);
    }
    setActing(a => ({ ...a, [pr.id]: null }));
    setTimeout(() => setMsg(""), 4000);
  };

  const handleReject = async (pr) => {
    setActing(a => ({ ...a, [pr.id]: "rejecting" }));
    const [res, err] = await apiFetch(`${BRAIN}/v1/github/prs/${pr.id}/close`, { method: "POST" });
    if (!err) {
      setMsg(`PR #${pr.id} closed ✗`);
      setPRs(p => p.filter(x => x.id !== pr.id));
    } else {
      setMsg(`Error: ${err}`);
    }
    setActing(a => ({ ...a, [pr.id]: null }));
    setTimeout(() => setMsg(""), 4000);
  };

  const triggerCodeWrite = async () => {
    if (!codeIntent.trim()) return;
    setTriggering(true);
    const token = ""; // pulled from keychain server-side
    const [res, err] = await apiFetch(`${BRAIN}/v1/code/write`, {
      method: "POST",
      body: JSON.stringify({ intent: codeIntent, target_file: codeFile || undefined }),
    });
    setTriggering(false);
    if (!err) {
      setMsg(`Code write triggered → branch ${res?.branch || "unknown"}`);
      setCodeIntent(""); setCodeFile("");
    } else {
      setMsg(`Error: ${err}`);
    }
    setTimeout(() => setMsg(""), 6000);
  };

  return (
    <div className="fade-in" style={{ display: "grid", gap: 16 }}>
      {/* Trigger code write */}
      <Card>
        <SectionLabel>TRIGGER CODE WRITE</SectionLabel>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 10, alignItems: "flex-end" }}>
          <div>
            <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted,
                          fontFamily: "'Share Tech Mono', monospace", marginBottom: 5 }}>INTENT</div>
            <input
              placeholder="e.g. Add health check to metrics endpoint"
              value={codeIntent}
              onChange={e => setCodeIntent(e.target.value)}
              style={{
                width: "100%", padding: "8px 12px", background: C.surface,
                border: `1px solid ${C.borderHi}`, borderRadius: 3,
                color: C.text, fontFamily: "'Rajdhani', sans-serif", fontSize: 13,
              }}
            />
          </div>
          <div>
            <div style={{ fontSize: 10, letterSpacing: 2, color: C.muted,
                          fontFamily: "'Share Tech Mono', monospace", marginBottom: 5 }}>TARGET FILE (optional)</div>
            <input
              placeholder="e.g. /Users/jarvisbrain/jarvis/services/brain/brain/app.py"
              value={codeFile}
              onChange={e => setCodeFile(e.target.value)}
              style={{
                width: "100%", padding: "8px 12px", background: C.surface,
                border: `1px solid ${C.borderHi}`, borderRadius: 3,
                color: C.text, fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
              }}
            />
          </div>
          <ActionBtn variant="success" onClick={triggerCodeWrite} loading={triggering} disabled={!codeIntent.trim()}>
            ▶ EXECUTE
          </ActionBtn>
        </div>
        {msg && <div style={{ marginTop: 10, fontSize: 11, color: C.green,
                              fontFamily: "'Share Tech Mono', monospace"}}>{msg}</div>}
      </Card>

      {/* Open PRs */}
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <SectionLabel>OPEN PULL REQUESTS</SectionLabel>
          <span style={{ fontSize: 11, color: C.muted, fontFamily: "'Share Tech Mono', monospace" }}>
            {prs.length} open
          </span>
        </div>
        {prs.length === 0 ? (
          <div style={{ textAlign: "center", padding: 30, color: C.muted, fontSize: 12,
                        fontFamily: "'Share Tech Mono', monospace" }}>
            NO OPEN PRs — All clear
          </div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {prs.map(pr => (
              <div key={pr.id} style={{
                background: C.surface, border: `1px solid ${selected===pr.id ? C.blue : C.border}`,
                borderRadius: 3, overflow: "hidden",
              }}>
                <div
                  onClick={() => setSelected(selected === pr.id ? null : pr.id)}
                  style={{
                    display: "grid", gridTemplateColumns: "50px 1fr auto auto auto auto auto",
                    gap: 12, alignItems: "center", padding: "12px 14px", cursor: "pointer",
                  }}
                >
                  <span style={{ fontFamily: "'Orbitron', monospace", fontSize: 12, color: C.muted }}>#{pr.id}</span>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{pr.intent}</div>
                    <div style={{ fontSize: 10, color: C.muted, fontFamily: "'Share Tech Mono', monospace", marginTop: 2 }}>
                      {pr.branch}
                    </div>
                  </div>
                  <span style={{ fontSize: 10, color: C.green, fontFamily: "'Share Tech Mono', monospace" }}>+{pr.added}</span>
                  <span style={{ fontSize: 10, color: C.red, fontFamily: "'Share Tech Mono', monospace" }}>-{pr.removed}</span>
                  <Pill status={pr.lint ? "PASS" : "FAIL"} />
                  <Pill status={pr.security ? "PASS" : "FAIL"} />
                  <span style={{ fontSize: 10, color: C.muted, fontFamily: "'Share Tech Mono', monospace" }}>{pr.ts}</span>
                </div>
                {selected === pr.id && (
                  <div>
                    <pre style={{
                      padding: "14px 18px", margin: 0, fontSize: 11, lineHeight: 1.7,
                      fontFamily: "'Share Tech Mono', monospace",
                      background: "#030810", borderTop: `1px solid ${C.border}`,
                      color: C.text, overflowX: "auto", whiteSpace: "pre-wrap",
                      maxHeight: 300, overflowY: "auto",
                    }}>
                      {(pr.diff || "").split("\n").map((line, i) => (
                        <span key={i} style={{
                          display: "block",
                          color: line.startsWith("+") ? C.green : line.startsWith("-") ? C.red : C.muted,
                        }}>{line}</span>
                      ))}
                    </pre>
                    <div style={{ display: "flex", gap: 10, padding: "10px 14px",
                                  borderTop: `1px solid ${C.border}` }}>
                      <ActionBtn variant="success" loading={acting[pr.id]==="approving"}
                                 onClick={() => handleApprove(pr)}>✓ APPROVE & MERGE</ActionBtn>
                      <ActionBtn variant="danger" loading={acting[pr.id]==="rejecting"}
                                 onClick={() => handleReject(pr)}>✗ REJECT & CLOSE</ActionBtn>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Code write audit log */}
      <Card>
        <SectionLabel>CODE WRITE AUDIT LOG</SectionLabel>
        <div style={{ display: "grid", gap: 6 }}>
          <div style={{
            display: "grid",
            gridTemplateColumns: "70px 1fr 160px 80px 70px 70px 70px",
            gap: 10, padding: "5px 12px",
            fontSize: 9, letterSpacing: 1.5, color: C.muted,
            fontFamily: "'Share Tech Mono', monospace",
          }}>
            <span>TIME</span><span>INTENT</span><span>FILE</span>
            <span>BRANCH</span><span>LINT</span><span>SEC</span><span>RESULT</span>
          </div>
          {(data?.codeLog || []).map((entry, i) => (
            <div key={i} style={{
              display: "grid",
              gridTemplateColumns: "70px 1fr 160px 80px 70px 70px 70px",
              gap: 10, alignItems: "center", padding: "9px 12px",
              background: C.surface, border: `1px solid ${C.border}`, borderRadius: 3, fontSize: 12,
            }}>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: C.muted }}>{entry.ts}</span>
              <span style={{ color: C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.intent}</span>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: C.muted,
                             overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.file}</span>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: C.muted,
                             overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.branch}</span>
              <Pill status={entry.lint === "PASS" ? "PASS" : "FAIL"} />
              <Pill status={entry.security === "PASS" ? "PASS" : "FAIL"} />
              <Pill status={entry.success ? "STABLE" : "ERROR"} />
            </div>
          ))}
          {!data?.codeLog?.length && (
            <div style={{ color: C.muted, textAlign: "center", padding: 20, fontSize: 12 }}>
              No audit log data — check /v1/code/log
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

// ── ERRORS TAB ────────────────────────────────────────────────────────────────
function ErrorsTab({ data, errors }) {
  const allErrors = data?.errors || [];
  const [filter, setFilter] = useState("ALL");

  const filtered = filter === "ALL" ? allErrors : allErrors.filter(e => e.level === filter);

  return (
    <div className="fade-in" style={{ display: "grid", gap: 16 }}>
      {/* Filter bar */}
      <div style={{ display: "flex", gap: 8 }}>
        {["ALL","ERROR","WARN","INFO"].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: "5px 14px", borderRadius: 2, cursor: "pointer", fontSize: 11,
            fontFamily: "'Share Tech Mono', monospace", letterSpacing: 1.5, fontWeight: 700,
            background: filter === f ? (f==="ERROR"?C.redDim:f==="WARN"?C.amberDim:f==="INFO"?C.blueDim:C.borderHi) : "transparent",
            color: filter === f ? (f==="ERROR"?C.red:f==="WARN"?C.amber:f==="INFO"?C.blue:C.text) : C.muted,
            border: `1px solid ${filter===f?(f==="ERROR"?C.red:f==="WARN"?C.amber:f==="INFO"?C.blue:C.borderHi):C.border}`,
          }}>{f}</button>
        ))}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: C.muted, fontFamily: "'Share Tech Mono', monospace",
                       alignSelf: "center" }}>{filtered.length} events</span>
      </div>

      {/* Error log */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        {filtered.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, color: C.green,
                        fontFamily: "'Share Tech Mono', monospace", fontSize: 12 }}>
            ✓ NO EVENTS MATCHING FILTER
          </div>
        ) : (
          <div style={{ display: "grid", gap: 0 }}>
            {filtered.map((entry, i) => {
              const [color] = statusMeta(entry.level);
              return (
                <div key={i} style={{
                  display: "grid", gridTemplateColumns: "80px 90px 100px 1fr",
                  gap: 14, alignItems: "center", padding: "11px 18px",
                  borderBottom: i < filtered.length - 1 ? `1px solid ${C.border}` : "none",
                  borderLeft: `3px solid ${color}`,
                  background: i % 2 === 0 ? C.surface : "transparent",
                }}>
                  <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: C.muted }}>{entry.ts}</span>
                  <Pill status={entry.level} />
                  <span style={{ fontSize: 11, fontWeight: 600, color: C.muted,
                                 fontFamily: "'Share Tech Mono', monospace" }}>{entry.node}</span>
                  <span style={{ fontSize: 12, color: C.text }}>{entry.msg}</span>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* API fetch errors */}
      {Object.keys(errors).length > 0 && (
        <Card style={{ borderColor: C.red + "44" }}>
          <SectionLabel>API CONNECTIVITY ERRORS</SectionLabel>
          {Object.entries(errors).map(([k, v]) => (
            <div key={k} style={{
              display: "flex", justifyContent: "space-between", padding: "8px 12px",
              background: C.redDim, borderRadius: 3, marginBottom: 6, fontSize: 12,
            }}>
              <span style={{ fontFamily: "'Share Tech Mono', monospace", color: C.red }}>{k}</span>
              <span style={{ color: C.muted }}>{v}</span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

// ── SECURITY TAB ──────────────────────────────────────────────────────────────
function SecurityTab({ data }) {
  const sec = data?.security || {};
  const checks = sec.checks || FALLBACK_SECURITY;
  const passed = checks.filter(c => c.status === "PASS").length;
  const score = Math.round((passed / checks.length) * 100) || sec.score || 0;

  return (
    <div className="fade-in" style={{ display: "grid", gap: 16 }}>
      {/* Score */}
      <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 16 }}>
        <Card style={{ textAlign: "center", display: "flex", flexDirection: "column",
                       alignItems: "center", justifyContent: "center", padding: 28 }}>
          <div style={{ fontSize: 9, letterSpacing: 3, color: C.muted,
                        fontFamily: "'Share Tech Mono', monospace", marginBottom: 12 }}>SECURITY SCORE</div>
          <div style={{
            width: 90, height: 90, borderRadius: "50%",
            border: `4px solid ${score>=90?C.green:score>=70?C.amber:C.red}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: `0 0 30px ${score>=90?C.green:score>=70?C.amber:C.red}44`,
          }}>
            <span style={{
              fontFamily: "'Orbitron', monospace", fontSize: 28, fontWeight: 900,
              color: score>=90?C.green:score>=70?C.amber:C.red,
            }}>{score}</span>
          </div>
          <div style={{ marginTop: 12, fontSize: 11, color: C.muted,
                        fontFamily: "'Share Tech Mono', monospace" }}>{passed}/{checks.length} PASS</div>
        </Card>

        <Card>
          <SectionLabel>COMPLIANCE SUMMARY</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {[
              { label: "Branch Protection",    ok: true },
              { label: "Secrets Encrypted",    ok: true },
              { label: "Write Path Enforced",  ok: true },
              { label: "Bandit Scanning",      ok: true },
              { label: "HTTPS Enforced",       ok: false },
              { label: "Token Rotation",       ok: false },
              { label: "Rate Limiting",        ok: true },
              { label: "Keychain Secrets",     ok: true },
            ].map(item => (
              <div key={item.label} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "8px 12px", background: C.surface,
                border: `1px solid ${item.ok ? C.green + "22" : C.amber + "22"}`, borderRadius: 3,
              }}>
                <span style={{ fontSize: 14, color: item.ok ? C.green : C.amber }}>
                  {item.ok ? "✓" : "○"}
                </span>
                <span style={{ fontSize: 12, color: item.ok ? C.text : C.muted }}>{item.label}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Detail checks */}
      <Card>
        <SectionLabel>SECURITY CHECKS</SectionLabel>
        <div style={{ display: "grid", gap: 8 }}>
          {checks.map((check, i) => {
            const [color] = statusMeta(check.status);
            return (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "60px 1fr 200px",
                gap: 14, alignItems: "center", padding: "11px 14px",
                background: C.surface, border: `1px solid ${color}22`, borderRadius: 3,
              }}>
                <Pill status={check.status} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{check.item}</div>
                  <div style={{ fontSize: 10, color: C.muted, fontFamily: "'Share Tech Mono', monospace", marginTop: 2 }}>
                    {check.detail}
                  </div>
                </div>
                {check.status === "TODO" && (
                  <span style={{ fontSize: 10, color: C.amber, fontFamily: "'Share Tech Mono', monospace" }}>
                    → Phase Final Hardening
                  </span>
                )}
                {check.status === "WARN" && (
                  <span style={{ fontSize: 10, color: C.amber, fontFamily: "'Share Tech Mono', monospace" }}>
                    ⚠ Review recommended
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Recommended actions */}
      <Card style={{ borderColor: C.amber + "44" }}>
        <SectionLabel>RECOMMENDED ACTIONS</SectionLabel>
        <div style={{ display: "grid", gap: 8 }}>
          {[
            { priority: "HIGH",   action: "Enable HTTPS on Brain (port 8182) — currently HTTP", phase: "Final Hardening" },
            { priority: "HIGH",   action: "Implement token rotation for JARVIS gateway token", phase: "Final Hardening" },
            { priority: "MEDIUM", action: "Rotate .secrets file — review last rotation date", phase: "Operational" },
            { priority: "MEDIUM", action: "Enable secret scanning on GitHub repo", phase: "Final Hardening" },
            { priority: "LOW",    action: "Add backup strategy for Postgres DB (jarvis-postgres)", phase: "Final Hardening" },
          ].map((rec, i) => {
            const color = rec.priority === "HIGH" ? C.red : rec.priority === "MEDIUM" ? C.amber : C.muted;
            return (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "70px 1fr 130px",
                gap: 12, alignItems: "center", padding: "10px 14px",
                background: C.surface, border: `1px solid ${color}22`, borderRadius: 3,
              }}>
                <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.5, color,
                               fontFamily: "'Share Tech Mono', monospace" }}>{rec.priority}</span>
                <span style={{ fontSize: 12, color: C.text }}>{rec.action}</span>
                <span style={{ fontSize: 10, color: C.muted, fontFamily: "'Share Tech Mono', monospace" }}>{rec.phase}</span>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

// ── FALLBACK DATA ─────────────────────────────────────────────────────────────
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

// ── ROOT APP ──────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState("summary");
  const { data, errors, lastRefresh, refreshing, refresh } = useJarvisData();

  const TABS = [
    { id: "summary",  label: "OVERVIEW",     icon: "⬡" },
    { id: "health",   label: "HEALTH",       icon: "◈" },
    { id: "cost",     label: "COST",         icon: "◇" },
    { id: "code",     label: "CODE REVIEW",  icon: "▷" },
    { id: "errors",   label: "ERRORS",       icon: "◉" },
    { id: "security", label: "SECURITY",     icon: "◆" },
  ];

  const errorCount = (data?.errors || []).filter(e => e.level === "ERROR").length;
  const openPRs = (data?.prs || []).length;

  return (
    <>
      <style>{GLOBAL_CSS}</style>
      <div className="scan-line" />

      <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
        {/* Header */}
        <header style={{
          display: "flex", alignItems: "center", gap: 24,
          padding: "0 28px", height: 52,
          background: C.surface,
          borderBottom: `1px solid ${C.border}`,
          position: "sticky", top: 0, zIndex: 100,
        }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 8, height: 8, borderRadius: "50%", background: C.green,
              boxShadow: `0 0 8px ${C.green}`, animation: "pulse 2s infinite",
            }} />
            <span style={{
              fontFamily: "'Orbitron', monospace", fontSize: 16, fontWeight: 900,
              letterSpacing: 4, color: C.green, textShadow: `0 0 16px ${C.green}66`,
            }}>JARVIS</span>
            <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
                           letterSpacing: 2, color: C.muted, marginTop: 2 }}>v3.0 · OPS</span>
          </div>

          {/* Tabs */}
          <nav style={{ display: "flex", gap: 2, flex: 1 }}>
            {TABS.map(t => {
              const badge = t.id === "errors" && errorCount > 0 ? errorCount
                          : t.id === "code" && openPRs > 0 ? openPRs : null;
              return (
                <button key={t.id} onClick={() => setTab(t.id)} style={{
                  padding: "0 16px", height: 52, border: "none", cursor: "pointer",
                  background: tab === t.id ? C.panel : "transparent",
                  borderBottom: tab === t.id ? `2px solid ${C.green}` : "2px solid transparent",
                  color: tab === t.id ? C.green : C.muted,
                  fontFamily: "'Rajdhani', sans-serif", fontSize: 12, fontWeight: 700,
                  letterSpacing: 2, transition: "all 0.15s", position: "relative",
                }}>
                  <span style={{ marginRight: 6, opacity: 0.7 }}>{t.icon}</span>
                  {t.label}
                  {badge && (
                    <span style={{
                      position: "absolute", top: 8, right: 6,
                      width: 16, height: 16, borderRadius: "50%",
                      background: t.id === "errors" ? C.red : C.amber,
                      color: "#000", fontSize: 9, fontWeight: 900,
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>{badge}</span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Status bar */}
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: C.muted }}>
              {lastRefresh ? `SYNC ${lastRefresh.toLocaleTimeString()}` : "CONNECTING..."}
            </div>
            <button onClick={refresh} disabled={refreshing} style={{
              padding: "4px 12px", borderRadius: 2, border: `1px solid ${C.border}`,
              background: "transparent", color: refreshing ? C.muted : C.green,
              cursor: "pointer", fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
              letterSpacing: 1, transition: "all 0.15s",
            }}>
              {refreshing ? "..." : "↺ REFRESH"}
            </button>
          </div>
        </header>

        {/* Main */}
        <main style={{ flex: 1, padding: "20px 28px", maxWidth: 1400, width: "100%", margin: "0 auto" }}>
          {Object.keys(errors).length > 0 && (
            <div style={{
              marginBottom: 14, padding: "8px 14px",
              background: C.redDim, border: `1px solid ${C.red}44`, borderRadius: 3,
              display: "flex", alignItems: "center", gap: 12, fontSize: 11,
              fontFamily: "'Share Tech Mono', monospace", color: C.red,
            }}>
              ⚠ {Object.keys(errors).length} API endpoint(s) unreachable —
              <span style={{ color: C.muted }}>
                {Object.keys(errors).join(", ")}
              </span>
              <span style={{ color: C.muted }}>· Dashboard showing partial data</span>
            </div>
          )}

          {tab === "summary"  && <SummaryTab    data={data} errors={errors} onAction={() => {}} />}
          {tab === "health"   && <HealthTab     data={data} errors={errors} onAction={() => {}} />}
          {tab === "cost"     && <CostTab       data={data} errors={errors} onAction={() => {}} />}
          {tab === "code"     && <CodeReviewTab data={data} errors={errors} onAction={() => {}} />}
          {tab === "errors"   && <ErrorsTab     data={data} errors={errors} />}
          {tab === "security" && <SecurityTab   data={data} />}
        </main>

        {/* Footer */}
        <footer style={{
          padding: "8px 28px", borderTop: `1px solid ${C.border}`,
          display: "flex", justifyContent: "space-between", alignItems: "center",
          background: C.surface,
        }}>
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: C.muted, letterSpacing: 2 }}>
            JARVIS PRIVATE AI INFRASTRUCTURE · TAILSCALE VPN · BRANCH PROTECTION ACTIVE
          </span>
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: C.muted, letterSpacing: 1 }}>
            BRAIN 100.64.166.22:8182 · GATEWAY 100.112.63.25:8282 · ENDPOINT 100.87.223.31:3000
          </span>
        </footer>
      </div>
    </>
  );
}

