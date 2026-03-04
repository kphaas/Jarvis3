import { useState, useEffect, useCallback, useRef } from "react";

const BRAIN    = "http://100.64.166.22:8182";
const GATEWAY  = "http://100.112.63.25:8282";
const ENDPOINT = "http://100.87.223.31:3000";
const REFRESH_MS = 15000;

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
    STABLE:[C.green,"STABLE"],RUNNING:[C.green,"RUN"],LIVE:[C.green,"LIVE"],
    ACTIVE:[C.green,"ACTIVE"],PASS:[C.green,"PASS"],ONLINE:[C.green,"ONLINE"],
    WARN:[C.amber,"WARN"],WARNING:[C.amber,"WARN"],TODO:[C.amber,"TODO"],IDLE:[C.amber,"IDLE"],
    ERROR:[C.red,"ERR"],FAIL:[C.red,"FAIL"],INACTIVE:[C.muted,"IDLE"],CRITICAL:[C.red,"CRIT"],
    INFO:[C.blue,"INFO"],DEGRADED:[C.amber,"DEGRADED"],
  };
  return m[s?.toUpperCase()] || [C.muted, s || "—"];
};

const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&family=Orbitron:wght@400;700;900&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body, #root { height: 100%; }
  body { background: #050a0e; color: #c8d8e8; font-family: 'Rajdhani', sans-serif; font-size: 15px; overflow-x: hidden; }
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: #080f14; }
  ::-webkit-scrollbar-thumb { background: #0e2233; border-radius: 2px; }
  .mono { font-family: 'Share Tech Mono', monospace; }
  .scan-line { pointer-events: none; position: fixed; inset: 0; z-index: 9999; background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.04) 2px, rgba(0,0,0,0.04) 4px); }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  @keyframes slideIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }
  .fade-in { animation: slideIn 0.25s ease; }
`;

function Pill({ status }) {
  const [color, label] = statusMeta(status);
  return (
    <span style={{ display:"inline-block", padding:"1px 7px", borderRadius:2, fontSize:10, fontWeight:700, letterSpacing:1.5, fontFamily:"'Share Tech Mono', monospace", color, background:color+"18", border:`1px solid ${color}44` }}>{label}</span>
  );
}

function Bar({ pct, warn=75, crit=90, height=5 }) {
  const color = pct>=crit ? C.red : pct>=warn ? C.amber : C.green;
  return (
    <div style={{ position:"relative", height, background:C.dim, borderRadius:1 }}>
      <div style={{ width:`${Math.min(pct,100)}%`, height:"100%", background:color, borderRadius:1, boxShadow:`0 0 6px ${color}66`, transition:"width 0.8s cubic-bezier(0.4,0,0.2,1)" }} />
    </div>
  );
}

function Card({ children, style={} }) {
  return <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:4, padding:"16px 18px", ...style }}>{children}</div>;
}

function SectionLabel({ children }) {
  return (
    <div style={{ fontFamily:"'Share Tech Mono', monospace", fontSize:10, letterSpacing:3, color:C.muted, textTransform:"uppercase", marginBottom:12, display:"flex", alignItems:"center", gap:8 }}>
      <span style={{ flex:1, height:1, background:C.border }} />{children}<span style={{ flex:1, height:1, background:C.border }} />
    </div>
  );
}

function ActionBtn({ children, onClick, variant="default", disabled=false, loading=false }) {
  const colors = { default:[C.blue,C.blueDim], danger:[C.red,C.redDim], success:[C.green,C.greenDim], warning:[C.amber,C.amberDim] };
  const [color, bg] = colors[variant] || colors.default;
  return (
    <button onClick={onClick} disabled={disabled||loading} style={{ padding:"6px 14px", borderRadius:2, cursor:disabled?"not-allowed":"pointer", border:`1px solid ${color}66`, background:loading?bg:"transparent", color, fontFamily:"'Rajdhani', sans-serif", fontWeight:600, fontSize:12, letterSpacing:1, opacity:disabled?0.4:1, transition:"all 0.15s", whiteSpace:"nowrap" }}
      onMouseEnter={e=>{if(!disabled)e.target.style.background=bg;}}
      onMouseLeave={e=>{if(!disabled)e.target.style.background="transparent";}}>
      {loading?"...":children}
    </button>
  );
}

async function apiFetch(url, opts={}) {
  try {
    const r = await fetch(url, { ...opts, headers:{ "Content-Type":"application/json", ...(opts.headers||{}) } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return [await r.json(), null];
  } catch(e) { return [null, e.message]; }
}

function useJarvisData() {
  const [data, setData] = useState({});
  const [errors, setErrors] = useState({});
  const [lastRefresh, setLastRefresh] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetch_all = useCallback(async () => {
    setRefreshing(true);
    const errs = {}, results = {};
    const calls = [
      ["health",       `${BRAIN}/v1/health/full`],
      ["costs",        `${BRAIN}/v1/costs`],
      ["codeLog",      `${BRAIN}/v1/code/log`],
      ["agents",       `${BRAIN}/v1/agents`],
      ["brainMetrics", `${BRAIN}/v1/metrics`],
      ["gwMetrics",    `${GATEWAY}/v1/metrics`],
      ["epMetrics",    `${ENDPOINT}/v1/metrics`],
    ];
    await Promise.all(calls.map(async ([key, url]) => {
      const [d, e] = await apiFetch(url);
      if (d) results[key] = d; else errs[key] = e;
    }));
    setData(prev => ({ ...prev, ...results }));
    setErrors(errs);
    setLastRefresh(new Date());
    setRefreshing(false);
  }, []);

  useEffect(() => { fetch_all(); const id = setInterval(fetch_all, REFRESH_MS); return () => clearInterval(id); }, [fetch_all]);
  return { data, errors, lastRefresh, refreshing, refresh: fetch_all };
}

function SummaryTab({ data, errors }) {
  const costs = data?.costs || {};
  const agents = data?.agents || [];
  const nodes = [
    { key:"brain",    label:"BRAIN",    port:8182, metrics:data?.brainMetrics },
    { key:"gateway",  label:"GATEWAY",  port:8282, metrics:data?.gwMetrics },
    { key:"endpoint", label:"ENDPOINT", port:3000, metrics:data?.epMetrics },
  ];
  const nodesOnline = nodes.filter(n => n.metrics && !errors[`${n.key}Metrics`]).length;
  const dailyPct  = costs.budget?.daily  ? (costs.budget.daily.spent_usd  / costs.budget.daily.limit_usd  * 100) : 0;
  const openPRs   = (data?.prs || []).length;
  const activeAgents = agents.filter(a => a.status === "ACTIVE").length;

  return (
    <div className="fade-in" style={{ display:"grid", gap:16 }}>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12 }}>
        {[
          { label:"NODES ONLINE",  value:`${nodesOnline}/3`, color:nodesOnline===3?C.green:C.amber },
          { label:"TODAY SPEND",   value:`$${(costs.budget?.daily?.spent_usd||0).toFixed(4)}`, color:dailyPct>=90?C.red:dailyPct>=75?C.amber:C.green },
          { label:"ACTIVE AGENTS", value:activeAgents, color:C.blue },
          { label:"OPEN PRs",      value:openPRs, color:openPRs>0?C.amber:C.green },
        ].map(k => (
          <Card key={k.label} style={{ textAlign:"center", padding:"20px 12px" }}>
            <div style={{ fontFamily:"'Orbitron', monospace", fontSize:28, fontWeight:900, color:k.color, textShadow:`0 0 20px ${k.color}66` }}>{k.value}</div>
            <div style={{ fontSize:10, letterSpacing:2, color:C.muted, marginTop:6, fontFamily:"'Share Tech Mono', monospace" }}>{k.label}</div>
          </Card>
        ))}
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
        <Card>
          <SectionLabel>NODE STATUS</SectionLabel>
          <div style={{ display:"grid", gap:10 }}>
            {nodes.map(node => {
              const m = node.metrics;
              const ok = m && !errors[`${node.key}Metrics`];
              return (
                <div key={node.key} style={{ display:"grid", gridTemplateColumns:"80px 1fr auto", alignItems:"center", gap:12, padding:"10px 14px", background:C.surface, border:`1px solid ${C.border}`, borderRadius:3 }}>
                  <div>
                    <div style={{ fontFamily:"'Orbitron', monospace", fontSize:11, color:ok?C.green:C.red, fontWeight:700 }}>{node.label}</div>
                    <div style={{ fontSize:10, color:C.muted, fontFamily:"'Share Tech Mono', monospace" }}>:{node.port}</div>
                  </div>
                  {ok ? (
                    <div style={{ display:"grid", gap:4 }}>
                      {[["CPU",m.cpu_pct,80,95],["RAM",m.ram_pct,75,90],["DSK",m.disk_pct,80,95]].map(([lbl,val,w,c]) => (
                        <div key={lbl} style={{ display:"grid", gridTemplateColumns:"28px 1fr 32px", gap:6, alignItems:"center" }}>
                          <span style={{ fontSize:9, color:C.muted, fontFamily:"'Share Tech Mono', monospace" }}>{lbl}</span>
                          <Bar pct={val||0} warn={w} crit={c} height={4} />
                          <span style={{ fontSize:9, color:C.muted, textAlign:"right", fontFamily:"'Share Tech Mono', monospace" }}>{(val||0).toFixed(0)}%</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize:11, color:C.red, fontFamily:"'Share Tech Mono', monospace" }}>{errors[`${node.key}Metrics`] || "UNREACHABLE"}</div>
                  )}
                  <Pill status={ok?"ONLINE":"ERROR"} />
                </div>
              );
            })}
          </div>
        </Card>

        <Card>
          <SectionLabel>BUDGET STATUS</SectionLabel>
          <div style={{ display:"grid", gap:14 }}>
            {[["DAILY",costs.budget?.daily],["WEEKLY",costs.budget?.weekly],["MONTHLY",costs.budget?.monthly]].map(([lbl,b]) => {
              const pct = b ? (b.spent_usd / b.limit_usd * 100) : 0;
              const color = pct>=90?C.red:pct>=75?C.amber:C.green;
              return (
                <div key={lbl}>
                  <div style={{ display:"flex", justifyContent:"space-between", marginBottom:6 }}>
                    <span style={{ fontSize:11, letterSpacing:2, color:C.muted, fontFamily:"'Share Tech Mono', monospace" }}>{lbl}</span>
                    <span style={{ fontFamily:"'Orbitron', monospace", fontSize:12, color }}>${(b?.spent_usd||0).toFixed(4)} / ${(b?.limit_usd||0).toFixed(2)}</span>
                  </div>
                  <Bar pct={pct} height={6} />
                  <div style={{ fontSize:10, color:C.muted, marginTop:4, textAlign:"right", fontFamily:"'Share Tech Mono', monospace" }}>
                    {pct.toFixed(1)}% utilized {pct>=75 && <span style={{ color:pct>=90?C.red:C.amber, marginLeft:8 }}>⚠ {pct>=90?"CRITICAL":"WARNING"}</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <Card>
        <SectionLabel>RECENT CODE WRITES</SectionLabel>
        <div style={{ display:"grid", gap:6 }}>
          {(data?.codeLog||[]).slice(0,5).map((entry,i) => (
            <div key={i} style={{ display:"grid", gridTemplateColumns:"140px 1fr auto auto auto", gap:12, alignItems:"center", padding:"8px 12px", background:C.surface, border:`1px solid ${C.border}`, borderRadius:3, fontSize:12 }}>
              <span style={{ fontFamily:"'Share Tech Mono', monospace", fontSize:10, color:C.muted }}>{entry.ts?.slice(0,19)}</span>
              <span style={{ color:C.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{entry.intent}</span>
              <Pill status={entry.lint?"PASS":"FAIL"} />
              <Pill status={entry.security?"PASS":"FAIL"} />
              <Pill status={entry.success?"STABLE":"ERROR"} />
            </div>
          ))}
          {!data?.codeLog?.length && <div style={{ color:C.muted, fontSize:12, textAlign:"center", padding:20 }}>No code writes yet</div>}
        </div>
      </Card>
    </div>
  );
}

function HealthTab({ data, errors, refresh }) {
  const [restarting, setRestarting] = useState({});
  const nodes = [
    { key:"brain",    label:"BRAIN",    host:"100.64.166.22", port:8182, metrics:data?.brainMetrics },
    { key:"gateway",  label:"GATEWAY",  host:"100.112.63.25", port:8282, metrics:data?.gwMetrics },
    { key:"endpoint", label:"ENDPOINT", host:"100.87.223.31", port:3000, metrics:data?.epMetrics },
  ];

  const handleRestart = async (key) => {
    setRestarting(r => ({ ...r, [key]:true }));
    await apiFetch(`${BRAIN}/v1/admin/restart/${key}`, { method:"POST" });
    setTimeout(() => { setRestarting(r => ({ ...r, [key]:false })); refresh(); }, 4000);
  };

  return (
    <div className="fade-in" style={{ display:"grid", gap:16 }}>
      {nodes.map(node => {
        const m = node.metrics;
        const ok = m && !errors[`${node.key}Metrics`];
        return (
          <Card key={node.key}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
              <div style={{ display:"flex", alignItems:"center", gap:12 }}>
                <div style={{ fontFamily:"'Orbitron', monospace", fontSize:16, fontWeight:900, color:ok?C.green:C.red }}>{node.label}</div>
                <span style={{ fontFamily:"'Share Tech Mono', monospace", fontSize:11, color:C.muted }}>{node.host}:{node.port}</span>
                <Pill status={ok?"ONLINE":"ERROR"} />
              </div>
              <ActionBtn variant="warning" loading={restarting[node.key]} onClick={() => handleRestart(node.key)}>RESTART</ActionBtn>
            </div>
            {ok ? (
              <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:14 }}>
                {[["CPU UTILIZATION",m.cpu_pct,80,95],["RAM UTILIZATION",m.ram_pct,75,90],["DISK UTILIZATION",m.disk_pct,80,95]].map(([lbl,val,w,c]) => (
                  <div key={lbl} style={{ padding:"14px 16px", background:C.surface, border:`1px solid ${C.border}`, borderRadius:3 }}>
                    <div style={{ fontSize:9, letterSpacing:2, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginBottom:8 }}>{lbl}</div>
                    <div style={{ fontFamily:"'Orbitron', monospace", fontSize:24, fontWeight:700, color:(val||0)>=c?C.red:(val||0)>=w?C.amber:C.green }}>
                      {(val||0).toFixed(1)}<span style={{ fontSize:12, color:C.muted }}>%</span>
                    </div>
                    <div style={{ marginTop:10 }}><Bar pct={val||0} warn={w} crit={c} height={5} /></div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ padding:24, textAlign:"center", background:C.surface, border:`1px solid ${C.red}44`, borderRadius:3, color:C.red, fontFamily:"'Share Tech Mono', monospace", fontSize:12 }}>
                NODE UNREACHABLE — {errors[`${node.key}Metrics`] || "No response"}
              </div>
            )}
            {ok && <div style={{ marginTop:12, fontSize:11, color:C.muted, fontFamily:"'Share Tech Mono', monospace" }}>UPTIME: {m.uptime} · LOAD: {m.load_avg||"—"} · PROCESSES: {m.process_count||"—"} · RAM: {m.ram_used_gb}GB / {m.ram_total_gb}GB · DISK: {m.disk_used_gb}GB / {m.disk_total_gb}GB</div>}
          </Card>
        );
      })}
    </div>
  );
}

function CostTab({ data }) {
  const costs = data?.costs || {};
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ daily:"", weekly:"", monthly:"" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const save = async () => {
    setSaving(true);
    for (const p of ["daily","weekly","monthly"]) {
      if (form[p]) await apiFetch(`${BRAIN}/v1/costs/budget?period=${p}&limit_usd=${form[p]}`, { method:"POST" });
    }
    setSaving(false); setMsg("Saved ✓"); setEditing(false);
    setTimeout(() => setMsg(""), 3000);
  };

  return (
    <div className="fade-in" style={{ display:"grid", gap:16 }}>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12 }}>
        {[["DAILY",costs.budget?.daily],["WEEKLY",costs.budget?.weekly],["MONTHLY",costs.budget?.monthly]].map(([lbl,b]) => {
          const pct = b ? (b.spent_usd/b.limit_usd*100) : 0;
          const color = pct>=90?C.red:pct>=75?C.amber:C.green;
          return (
            <Card key={lbl}>
              <div style={{ fontSize:9, letterSpacing:3, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginBottom:10 }}>{lbl} BUDGET</div>
              <div style={{ display:"flex", alignItems:"baseline", gap:6 }}>
                <span style={{ fontFamily:"'Orbitron', monospace", fontSize:26, fontWeight:900, color }}>${(b?.spent_usd||0).toFixed(4)}</span>
                <span style={{ fontSize:12, color:C.muted }}>/ ${(b?.limit_usd||0).toFixed(2)}</span>
              </div>
              <div style={{ margin:"10px 0" }}><Bar pct={pct} height={6} /></div>
              <div style={{ display:"flex", justifyContent:"space-between", fontSize:10, color:C.muted, fontFamily:"'Share Tech Mono', monospace" }}>
                <span>${((b?.limit_usd||0)-(b?.spent_usd||0)).toFixed(4)} left</span>
                <span style={{ color }}>{pct.toFixed(1)}%</span>
              </div>
            </Card>
          );
        })}
      </div>

      <Card>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:14 }}>
          <SectionLabel>UPDATE LIMITS</SectionLabel>
          {msg && <span style={{ fontSize:11, color:C.green, fontFamily:"'Share Tech Mono', monospace" }}>{msg}</span>}
        </div>
        {editing ? (
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr auto auto", gap:10, alignItems:"flex-end" }}>
            {["daily","weekly","monthly"].map(p => (
              <div key={p}>
                <div style={{ fontSize:10, color:C.muted, fontFamily:"'Share Tech Mono', monospace", letterSpacing:2, marginBottom:5 }}>{p.toUpperCase()} ($)</div>
                <input type="number" step="0.01" placeholder={(costs.budget?.[p]?.limit_usd||0).toFixed(2)} value={form[p]}
                  onChange={e => setForm(f => ({ ...f, [p]:e.target.value }))}
                  style={{ width:"100%", padding:"7px 10px", background:C.surface, border:`1px solid ${C.borderHi}`, borderRadius:3, color:C.text, fontFamily:"'Share Tech Mono', monospace", fontSize:13 }} />
              </div>
            ))}
            <ActionBtn variant="success" onClick={save} loading={saving}>SAVE</ActionBtn>
            <ActionBtn onClick={() => setEditing(false)}>CANCEL</ActionBtn>
          </div>
        ) : (
          <ActionBtn variant="warning" onClick={() => setEditing(true)}>EDIT LIMITS</ActionBtn>
        )}
      </Card>

      <Card>
        <SectionLabel>SPEND BY PROVIDER</SectionLabel>
        <div style={{ display:"grid", gap:8 }}>
          {(costs.by_provider||[]).map(row => {
            const max = Math.max(...(costs.by_provider||[]).map(r=>r.cost_usd||0), 0.001);
            return (
              <div key={row.provider} style={{ display:"grid", gridTemplateColumns:"140px 1fr 80px 90px", gap:14, alignItems:"center", padding:"10px 14px", background:C.surface, border:`1px solid ${C.border}`, borderRadius:3 }}>
                <span style={{ fontSize:13, fontWeight:600, color:C.text }}>{row.provider}</span>
                <Bar pct={(row.cost_usd/max)*100} warn={999} crit={999} height={5} />
                <span style={{ fontFamily:"'Share Tech Mono', monospace", fontSize:11, color:C.muted, textAlign:"right" }}>{row.calls} calls</span>
                <span style={{ fontFamily:"'Orbitron', monospace", fontSize:13, color:row.cost_usd===0?C.green:C.text, textAlign:"right" }}>${(row.cost_usd||0).toFixed(4)}</span>
              </div>
            );
          })}
          {!costs.by_provider?.length && <div style={{ color:C.muted, textAlign:"center", padding:20, fontSize:12 }}>No provider data yet</div>}
        </div>
      </Card>
    </div>
  );
}

function CodeReviewTab({ data }) {
  const [prs, setPRs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [acting, setActing] = useState({});
  const [msg, setMsg] = useState("");
  const [intent, setIntent] = useState("");
  const [file, setFile] = useState("");
  const [triggering, setTriggering] = useState(false);

  useEffect(() => { apiFetch(`${BRAIN}/v1/github/prs`).then(([d]) => { if(d) setPRs(d); }); }, []);

  const approve = async (pr) => {
    setActing(a => ({ ...a, [pr.id]:"approving" }));
    const [,err] = await apiFetch(`${BRAIN}/v1/github/prs/${pr.id}/merge`, { method:"POST" });
    if (!err) { setMsg(`PR #${pr.id} merged ✓`); setPRs(p => p.filter(x => x.id !== pr.id)); }
    else setMsg(`Error: ${err}`);
    setActing(a => ({ ...a, [pr.id]:null }));
    setTimeout(() => setMsg(""), 4000);
  };

  const reject = async (pr) => {
    setActing(a => ({ ...a, [pr.id]:"rejecting" }));
    const [,err] = await apiFetch(`${BRAIN}/v1/github/prs/${pr.id}/close`, { method:"POST" });
    if (!err) { setMsg(`PR #${pr.id} closed ✗`); setPRs(p => p.filter(x => x.id !== pr.id)); }
    else setMsg(`Error: ${err}`);
    setActing(a => ({ ...a, [pr.id]:null }));
    setTimeout(() => setMsg(""), 4000);
  };

  const trigger = async () => {
    if (!intent.trim()) return;
    setTriggering(true);
    const [res, err] = await apiFetch(`${BRAIN}/v1/code/write`, { method:"POST", body:JSON.stringify({ intent, target_file:file||undefined }) });
    setTriggering(false);
    if (!err) { setMsg(`Triggered → branch ${res?.branch||"unknown"}`); setIntent(""); setFile(""); }
    else setMsg(`Error: ${err}`);
    setTimeout(() => setMsg(""), 6000);
  };

  return (
    <div className="fade-in" style={{ display:"grid", gap:16 }}>
      <Card>
        <SectionLabel>TRIGGER CODE WRITE</SectionLabel>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr auto", gap:10, alignItems:"flex-end" }}>
          <div>
            <div style={{ fontSize:10, letterSpacing:2, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginBottom:5 }}>INTENT</div>
            <input placeholder="e.g. Add health check to metrics endpoint" value={intent} onChange={e=>setIntent(e.target.value)}
              style={{ width:"100%", padding:"8px 12px", background:C.surface, border:`1px solid ${C.borderHi}`, borderRadius:3, color:C.text, fontFamily:"'Rajdhani', sans-serif", fontSize:13 }} />
          </div>
          <div>
            <div style={{ fontSize:10, letterSpacing:2, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginBottom:5 }}>TARGET FILE (optional)</div>
            <input placeholder="/Users/jarvisbrain/jarvis/services/brain/brain/app.py" value={file} onChange={e=>setFile(e.target.value)}
              style={{ width:"100%", padding:"8px 12px", background:C.surface, border:`1px solid ${C.borderHi}`, borderRadius:3, color:C.text, fontFamily:"'Share Tech Mono', monospace", fontSize:11 }} />
          </div>
          <ActionBtn variant="success" onClick={trigger} loading={triggering} disabled={!intent.trim()}>▶ EXECUTE</ActionBtn>
        </div>
        {msg && <div style={{ marginTop:10, fontSize:11, color:C.green, fontFamily:"'Share Tech Mono', monospace" }}>{msg}</div>}
      </Card>

      <Card>
        <SectionLabel>OPEN PULL REQUESTS</SectionLabel>
        {prs.length===0 ? (
          <div style={{ textAlign:"center", padding:30, color:C.muted, fontSize:12, fontFamily:"'Share Tech Mono', monospace" }}>NO OPEN PRs — All clear</div>
        ) : (
          <div style={{ display:"grid", gap:10 }}>
            {prs.map(pr => (
              <div key={pr.id} style={{ background:C.surface, border:`1px solid ${selected===pr.id?C.blue:C.border}`, borderRadius:3, overflow:"hidden" }}>
                <div onClick={() => setSelected(selected===pr.id?null:pr.id)} style={{ display:"grid", gridTemplateColumns:"50px 1fr auto auto auto auto", gap:12, alignItems:"center", padding:"12px 14px", cursor:"pointer" }}>
                  <span style={{ fontFamily:"'Orbitron', monospace", fontSize:12, color:C.muted }}>#{pr.id}</span>
                  <div>
                    <div style={{ fontSize:13, fontWeight:600, color:C.text }}>{pr.intent}</div>
                    <div style={{ fontSize:10, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginTop:2 }}>{pr.branch}</div>
                  </div>
                  <span style={{ fontSize:10, color:C.green, fontFamily:"'Share Tech Mono', monospace" }}>+{pr.added}</span>
                  <span style={{ fontSize:10, color:C.red, fontFamily:"'Share Tech Mono', monospace" }}>-{pr.removed}</span>
                  <Pill status={pr.lint?"PASS":"FAIL"} />
                  <Pill status={pr.security?"PASS":"FAIL"} />
                </div>
                {selected===pr.id && (
                  <div>
                    <pre style={{ padding:"14px 18px", margin:0, fontSize:11, lineHeight:1.7, fontFamily:"'Share Tech Mono', monospace", background:"#030810", borderTop:`1px solid ${C.border}`, color:C.text, overflowX:"auto", whiteSpace:"pre-wrap", maxHeight:300, overflowY:"auto" }}>
                      {(pr.diff||"").split("\n").map((line,i) => (
                        <span key={i} style={{ display:"block", color:line.startsWith("+")?C.green:line.startsWith("-")?C.red:C.muted }}>{line}</span>
                      ))}
                    </pre>
                    <div style={{ display:"flex", gap:10, padding:"10px 14px", borderTop:`1px solid ${C.border}` }}>
                      <ActionBtn variant="success" loading={acting[pr.id]==="approving"} onClick={() => approve(pr)}>✓ APPROVE & MERGE</ActionBtn>
                      <ActionBtn variant="danger" loading={acting[pr.id]==="rejecting"} onClick={() => reject(pr)}>✗ REJECT & CLOSE</ActionBtn>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <SectionLabel>AUDIT LOG</SectionLabel>
        <div style={{ display:"grid", gap:6 }}>
          {(data?.codeLog||[]).map((entry,i) => (
            <div key={i} style={{ display:"grid", gridTemplateColumns:"140px 1fr 70px 70px 70px", gap:10, alignItems:"center", padding:"9px 12px", background:C.surface, border:`1px solid ${C.border}`, borderRadius:3, fontSize:12 }}>
              <span style={{ fontFamily:"'Share Tech Mono', monospace", fontSize:10, color:C.muted }}>{entry.ts?.slice(0,19)}</span>
              <span style={{ color:C.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{entry.intent}</span>
              <Pill status={entry.lint?"PASS":"FAIL"} />
              <Pill status={entry.security?"PASS":"FAIL"} />
              <Pill status={entry.success?"STABLE":"ERROR"} />
            </div>
          ))}
          {!data?.codeLog?.length && <div style={{ color:C.muted, textAlign:"center", padding:20, fontSize:12 }}>No audit data</div>}
        </div>
      </Card>
    </div>
  );
}

function ErrorsTab({ data, errors }) {
  const allErrors = data?.health?.subsystems ? Object.entries(data.health.subsystems).filter(([,v]) => v.status !== "ok").map(([k,v]) => ({ ts:"now", node:k, level:v.status==="error"?"ERROR":"WARN", msg:v.detail||v.status })) : [];
  const apiErrors = Object.entries(errors).map(([k,v]) => ({ ts:"now", node:k, level:"ERROR", msg:v }));
  const combined = [...apiErrors, ...allErrors];
  const [filter, setFilter] = useState("ALL");
  const filtered = filter==="ALL" ? combined : combined.filter(e => e.level===filter);

  return (
    <div className="fade-in" style={{ display:"grid", gap:16 }}>
      <div style={{ display:"flex", gap:8 }}>
        {["ALL","ERROR","WARN"].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{ padding:"5px 14px", borderRadius:2, cursor:"pointer", fontSize:11, fontFamily:"'Share Tech Mono', monospace", letterSpacing:1.5, fontWeight:700, background:filter===f?(f==="ERROR"?C.redDim:f==="WARN"?C.amberDim:C.borderHi):"transparent", color:filter===f?(f==="ERROR"?C.red:f==="WARN"?C.amber:C.text):C.muted, border:`1px solid ${filter===f?(f==="ERROR"?C.red:f==="WARN"?C.amber:C.borderHi):C.border}` }}>{f}</button>
        ))}
        <span style={{ fontSize:11, color:C.muted, fontFamily:"'Share Tech Mono', monospace", alignSelf:"center", marginLeft:"auto" }}>{filtered.length} events</span>
      </div>
      <Card style={{ padding:0, overflow:"hidden" }}>
        {filtered.length===0 ? (
          <div style={{ textAlign:"center", padding:40, color:C.green, fontFamily:"'Share Tech Mono', monospace", fontSize:12 }}>✓ ALL SYSTEMS NOMINAL</div>
        ) : (
          filtered.map((e,i) => {
            const [color] = statusMeta(e.level);
            return (
              <div key={i} style={{ display:"grid", gridTemplateColumns:"80px 90px 120px 1fr", gap:14, alignItems:"center", padding:"11px 18px", borderBottom:i<filtered.length-1?`1px solid ${C.border}`:"none", borderLeft:`3px solid ${color}`, background:i%2===0?C.surface:"transparent" }}>
                <span style={{ fontFamily:"'Share Tech Mono', monospace", fontSize:10, color:C.muted }}>{e.ts}</span>
                <Pill status={e.level} />
                <span style={{ fontSize:11, fontWeight:600, color:C.muted, fontFamily:"'Share Tech Mono', monospace" }}>{e.node}</span>
                <span style={{ fontSize:12, color:C.text }}>{e.msg}</span>
              </div>
            );
          })
        )}
      </Card>
    </div>
  );
}

function SecurityTab({ data }) {
  const checks = [
    { item:"Branch protection (main)",       status:"PASS", detail:"PRs required, bypass for kphaas" },
    { item:"Secrets in .gitignore",          status:"PASS", detail:".secrets, *.key excluded" },
    { item:"ALLOWED_WRITE_PATHS enforced",   status:"PASS", detail:"No writes outside approved dirs" },
    { item:"Bandit scan on all generations", status:"PASS", detail:"High severity auto-blocks" },
    { item:"Rate limiting active",           status:"PASS", detail:"10 writes/hr sliding window" },
    { item:"Keychain + .secrets fallback",   status:"WARN", detail:"chmod 600 — rotate periodically" },
    { item:"HTTPS on endpoints",             status:"TODO", detail:"Phase Final Hardening" },
    { item:"Token rotation policy",          status:"TODO", detail:"Phase Final Hardening" },
  ];
  const passed = checks.filter(c=>c.status==="PASS").length;
  const score = Math.round((passed/checks.length)*100);

  return (
    <div className="fade-in" style={{ display:"grid", gap:16 }}>
      <div style={{ display:"grid", gridTemplateColumns:"180px 1fr", gap:16 }}>
        <Card style={{ textAlign:"center", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", padding:28 }}>
          <div style={{ fontSize:9, letterSpacing:3, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginBottom:12 }}>SECURITY SCORE</div>
          <div style={{ width:90, height:90, borderRadius:"50%", border:`4px solid ${score>=90?C.green:score>=70?C.amber:C.red}`, display:"flex", alignItems:"center", justifyContent:"center", boxShadow:`0 0 30px ${score>=90?C.green:score>=70?C.amber:C.red}44` }}>
            <span style={{ fontFamily:"'Orbitron', monospace", fontSize:28, fontWeight:900, color:score>=90?C.green:score>=70?C.amber:C.red }}>{score}</span>
          </div>
          <div style={{ marginTop:12, fontSize:11, color:C.muted, fontFamily:"'Share Tech Mono', monospace" }}>{passed}/{checks.length} PASS</div>
        </Card>
        <Card>
          <SectionLabel>RECOMMENDED ACTIONS</SectionLabel>
          {[
            { p:"HIGH",   a:"Enable HTTPS on Brain (port 8182)" },
            { p:"HIGH",   a:"Implement token rotation for gateway token" },
            { p:"MEDIUM", a:"Rotate .secrets file — check last rotation date" },
            { p:"MEDIUM", a:"Enable secret scanning on GitHub repo" },
            { p:"LOW",    a:"Add backup strategy for Postgres DB" },
          ].map((r,i) => {
            const color = r.p==="HIGH"?C.red:r.p==="MEDIUM"?C.amber:C.muted;
            return (
              <div key={i} style={{ display:"grid", gridTemplateColumns:"70px 1fr", gap:12, alignItems:"center", padding:"8px 12px", background:C.surface, border:`1px solid ${color}22`, borderRadius:3, marginBottom:6 }}>
                <span style={{ fontSize:10, fontWeight:700, letterSpacing:1.5, color, fontFamily:"'Share Tech Mono', monospace" }}>{r.p}</span>
                <span style={{ fontSize:12, color:C.text }}>{r.a}</span>
              </div>
            );
          })}
        </Card>
      </div>
      <Card>
        <SectionLabel>SECURITY CHECKS</SectionLabel>
        <div style={{ display:"grid", gap:8 }}>
          {checks.map((check,i) => {
            const [color] = statusMeta(check.status);
            return (
              <div key={i} style={{ display:"grid", gridTemplateColumns:"60px 1fr", gap:14, alignItems:"center", padding:"11px 14px", background:C.surface, border:`1px solid ${color}22`, borderRadius:3 }}>
                <Pill status={check.status} />
                <div>
                  <div style={{ fontSize:13, fontWeight:600, color:C.text }}>{check.item}</div>
                  <div style={{ fontSize:10, color:C.muted, fontFamily:"'Share Tech Mono', monospace", marginTop:2 }}>{check.detail}</div>
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}

const TABS = [
  { id:"summary",  label:"OVERVIEW",    icon:"⬡" },
  { id:"health",   label:"HEALTH",      icon:"◈" },
  { id:"cost",     label:"COST",        icon:"◇" },
  { id:"code",     label:"CODE REVIEW", icon:"▷" },
  { id:"errors",   label:"ERRORS",      icon:"◉" },
  { id:"security", label:"SECURITY",    icon:"◆" },
];

export default function App() {
  const [tab, setTab] = useState("summary");
  const { data, errors, lastRefresh, refreshing, refresh } = useJarvisData();
  const errCount = Object.keys(errors).length;
  const openPRs = (data?.prs||[]).length;

  return (
    <>
      <style>{GLOBAL_CSS}</style>
      <div className="scan-line" />
      <div style={{ minHeight:"100vh", display:"flex", flexDirection:"column" }}>
        <header style={{ display:"flex", alignItems:"center", gap:24, padding:"0 28px", height:52, background:C.surface, borderBottom:`1px solid ${C.border}`, position:"sticky", top:0, zIndex:100 }}>
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <div style={{ width:8, height:8, borderRadius:"50%", background:C.green, boxShadow:`0 0 8px ${C.green}`, animation:"pulse 2s infinite" }} />
            <span style={{ fontFamily:"'Orbitron', monospace", fontSize:16, fontWeight:900, letterSpacing:4, color:C.green, textShadow:`0 0 16px ${C.green}66` }}>JARVIS</span>
            <span style={{ fontFamily:"'Share Tech Mono', monospace", fontSize:9, letterSpacing:2, color:C.muted }}>v3.0 · OPS</span>
          </div>
          <nav style={{ display:"flex", gap:2, flex:1 }}>
            {TABS.map(t => {
              const badge = t.id==="errors"&&errCount>0 ? errCount : t.id==="code"&&openPRs>0 ? openPRs : null;
              return (
                <button key={t.id} onClick={() => setTab(t.id)} style={{ padding:"0 16px", height:52, border:"none", cursor:"pointer", background:tab===t.id?C.panel:"transparent", borderBottom:tab===t.id?`2px solid ${C.green}`:"2px solid transparent", color:tab===t.id?C.green:C.muted, fontFamily:"'Rajdhani', sans-serif", fontSize:12, fontWeight:700, letterSpacing:2, transition:"all 0.15s", position:"relative" }}>
                  <span style={{ marginRight:6, opacity:0.7 }}>{t.icon}</span>{t.label}
                  {badge && <span style={{ position:"absolute", top:8, right:6, width:16, height:16, borderRadius:"50%", background:t.id==="errors"?C.red:C.amber, color:"#000", fontSize:9, fontWeight:900, display:"flex", alignItems:"center", justifyContent:"center" }}>{badge}</span>}
                </button>
              );
            })}
          </nav>
          <div style={{ display:"flex", alignItems:"center", gap:16 }}>
            <div style={{ fontFamily:"'Share Tech Mono', monospace", fontSize:10, color:C.muted }}>{lastRefresh?`SYNC ${lastRefresh.toLocaleTimeString()}`:"CONNECTING..."}</div>
            <button onClick={refresh} disabled={refreshing} style={{ padding:"4px 12px", borderRadius:2, border:`1px solid ${C.border}`, background:"transparent", color:refreshing?C.muted:C.green, cursor:"pointer", fontFamily:"'Share Tech Mono', monospace", fontSize:10, letterSpacing:1 }}>{refreshing?"...":"↺ REFRESH"}</button>
          </div>
        </header>
        <main style={{ flex:1, padding:"20px 28px", maxWidth:1400, width:"100%", margin:"0 auto" }}>
          {errCount>0 && (
            <div style={{ marginBottom:14, padding:"8px 14px", background:C.redDim, border:`1px solid ${C.red}44`, borderRadius:3, display:"flex", alignItems:"center", gap:12, fontSize:11, fontFamily:"'Share Tech Mono', monospace", color:C.red }}>
              ⚠ {errCount} endpoint(s) unreachable — {Object.keys(errors).join(", ")}
            </div>
          )}
          {tab==="summary"  && <SummaryTab  data={data} errors={errors} />}
          {tab==="health"   && <HealthTab   data={data} errors={errors} refresh={refresh} />}
          {tab==="cost"     && <CostTab     data={data} />}
          {tab==="code"     && <CodeReviewTab data={data} />}
          {tab==="errors"   && <ErrorsTab   data={data} errors={errors} />}
          {tab==="security" && <SecurityTab data={data} />}
        </main>
        <footer style={{ padding:"8px 28px", borderTop:`1px solid ${C.border}`, display:"flex", justifyContent:"space-between", alignItems:"center", background:C.surface }}>
          <span style={{ fontFamily:"'Share Tech Mono', monospace", fontSize:9, color:C.muted, letterSpacing:2 }}>JARVIS PRIVATE AI · TAILSCALE VPN · BRANCH PROTECTION ACTIVE</span>
          <span style={{ fontFamily:"'Share Tech Mono', monospace", fontSize:9, color:C.muted }}>BRAIN :8182 · GATEWAY :8282 · ENDPOINT :3000</span>
        </footer>
      </div>
    </>
  );
}
