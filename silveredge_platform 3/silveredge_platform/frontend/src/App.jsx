import { useState, useEffect, useCallback, useRef, createContext, useContext } from "react";

// ─── API ────────────────────────────────────────────────────────────
const API = "http://localhost:8000";
const WS  = "ws://localhost:8000";

function apiFetch(path, opts = {}, token) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${API}${path}`, { ...opts, headers }).then(async r => {
    if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || r.statusText); }
    return r.json();
  });
}

// ─── Auth Context ───────────────────────────────────────────────────
const AuthCtx = createContext(null);
function useAuth() { return useContext(AuthCtx); }

function AuthProvider({ children }) {
  const [token, setToken]   = useState(() => localStorage.getItem("token") || "");
  const [user,  setUser]    = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async (t) => {
    if (!t) { setLoading(false); return; }
    try {
      const me = await apiFetch("/api/me", {}, t);
      setUser(me);
    } catch { setToken(""); localStorage.removeItem("token"); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchMe(token); }, [token]);

  const login = async (username, password) => {
    const form = new URLSearchParams({ username, password });
    const data = await fetch(`${API}/api/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form
    }).then(r => r.ok ? r.json() : r.json().then(e => { throw new Error(e.detail); }));
    localStorage.setItem("token", data.access_token);
    setToken(data.access_token);
    setUser({ user_id: data.user_id, username: data.username, balance: data.balance });
    return data;
  };

  const signup = async (username, email, password, balance) => {
    const data = await apiFetch("/api/auth/signup", {
      method: "POST", body: JSON.stringify({ username, email, password, balance })
    });
    localStorage.setItem("token", data.access_token);
    setToken(data.access_token);
    setUser({ user_id: data.user_id, username: data.username, balance: data.balance });
    return data;
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(""); setUser(null);
  };

  const refreshUser = useCallback(() => fetchMe(token), [token]);

  return (
    <AuthCtx.Provider value={{ token, user, loading, login, signup, logout, refreshUser }}>
      {children}
    </AuthCtx.Provider>
  );
}

// ─── Styles ─────────────────────────────────────────────────────────
const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap');

  :root {
    --bg:       #050a0f;
    --surface:  #0c1520;
    --surface2: #111d2b;
    --border:   #1a2d40;
    --border2:  #243d55;
    --gold:     #f0b429;
    --gold2:    #ffd060;
    --green:    #00e5a0;
    --red:      #ff4d6a;
    --blue:     #2dd4ff;
    --muted:    #4a6680;
    --text:     #cce0f5;
    --text2:    #7a9ab5;
    --font:     'Syne', sans-serif;
    --mono:     'Space Mono', monospace;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    min-height: 100vh;
    overflow-x: hidden;
  }

  .app-shell {
    display: grid;
    grid-template-columns: 220px 1fr;
    grid-template-rows: 56px 1fr;
    min-height: 100vh;
  }

  /* ── Topbar ── */
  .topbar {
    grid-column: 1 / -1;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    position: sticky;
    top: 0;
    z-index: 100;
  }
  .topbar-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 800;
    letter-spacing: -0.5px;
  }
  .topbar-logo span { color: var(--gold); }
  .logo-icon {
    width: 32px; height: 32px;
    background: linear-gradient(135deg, var(--gold), var(--gold2));
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px;
  }
  .topbar-right { display: flex; align-items: center; gap: 16px; }
  .balance-chip {
    background: var(--surface2);
    border: 1px solid var(--border2);
    border-radius: 20px;
    padding: 4px 14px;
    font-family: var(--mono);
    font-size: 13px;
    color: var(--gold);
  }
  .live-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
    animation: pulse 2s infinite;
  }
  .live-dot.off { background: var(--muted); box-shadow: none; animation: none; }
  @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }
  .user-badge {
    display: flex; align-items: center; gap: 8px;
    cursor: pointer;
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid var(--border);
    transition: border-color .2s;
  }
  .user-badge:hover { border-color: var(--border2); }
  .avatar {
    width: 28px; height: 28px; border-radius: 50%;
    background: linear-gradient(135deg, #1a3a5c, #2a5a8a);
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; color: var(--blue);
  }

  /* ── Sidebar ── */
  .sidebar {
    background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 20px 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .sidebar-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: var(--muted);
    text-transform: uppercase;
    padding: 12px 12px 4px;
  }
  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    color: var(--text2);
    transition: all .15s;
    border: 1px solid transparent;
  }
  .nav-item:hover { background: var(--surface2); color: var(--text); }
  .nav-item.active {
    background: rgba(240,180,41,0.08);
    border-color: rgba(240,180,41,0.2);
    color: var(--gold);
  }
  .nav-icon { font-size: 16px; width: 20px; text-align: center; }

  /* ── Main content ── */
  .main {
    overflow-y: auto;
    padding: 28px;
    background: var(--bg);
  }

  /* ── Cards ── */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 22px;
  }
  .card-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 18px;
  }
  .card-title {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: var(--text2);
    text-transform: uppercase;
  }

  /* ── Stats grid ── */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }
  .stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px;
    position: relative;
    overflow: hidden;
  }
  .stat-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
  }
  .stat-card.gold::before  { background: var(--gold); }
  .stat-card.green::before { background: var(--green); }
  .stat-card.red::before   { background: var(--red); }
  .stat-card.blue::before  { background: var(--blue); }

  .stat-label { font-size: 11px; font-weight: 700; letter-spacing: 1px; color: var(--muted); text-transform: uppercase; margin-bottom: 8px; }
  .stat-value { font-size: 26px; font-weight: 800; font-family: var(--mono); }
  .stat-sub   { font-size: 11px; color: var(--text2); margin-top: 4px; }
  .stat-card.gold  .stat-value { color: var(--gold); }
  .stat-card.green .stat-value { color: var(--green); }
  .stat-card.red   .stat-value { color: var(--red); }
  .stat-card.blue  .stat-value { color: var(--blue); }

  /* ── Dashboard grid ── */
  .dash-grid {
    display: grid;
    grid-template-columns: 1fr 380px;
    gap: 20px;
  }
  .dash-left  { display: flex; flex-direction: column; gap: 20px; }
  .dash-right { display: flex; flex-direction: column; gap: 20px; }

  /* ── Allocation panel ── */
  .alloc-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px;
    margin-top: 4px;
  }
  .alloc-item { }
  .alloc-k { font-size: 10px; font-weight: 700; color: var(--muted); letter-spacing: 1px; text-transform: uppercase; margin-bottom: 4px; }
  .alloc-v { font-family: var(--mono); font-size: 14px; color: var(--text); font-weight: 700; }
  .alloc-v.gold  { color: var(--gold); }
  .alloc-v.green { color: var(--green); }
  .alloc-v.blue  { color: var(--blue); }
  .alloc-v.red   { color: var(--red); }

  /* ── Buttons ── */
  .btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 9px 18px;
    border-radius: 8px;
    font-family: var(--font);
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    border: none;
    transition: all .15s;
  }
  .btn-gold {
    background: var(--gold);
    color: #000;
  }
  .btn-gold:hover { background: var(--gold2); }
  .btn-ghost {
    background: transparent;
    border: 1px solid var(--border2);
    color: var(--text2);
  }
  .btn-ghost:hover { border-color: var(--text2); color: var(--text); }
  .btn-danger {
    background: rgba(255,77,106,0.1);
    border: 1px solid rgba(255,77,106,0.3);
    color: var(--red);
  }
  .btn-danger:hover { background: rgba(255,77,106,0.2); }
  .btn-green {
    background: rgba(0,229,160,0.1);
    border: 1px solid rgba(0,229,160,0.3);
    color: var(--green);
  }
  .btn-green:hover { background: rgba(0,229,160,0.2); }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-sm { padding: 6px 12px; font-size: 12px; }

  /* ── Tables ── */
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th {
    text-align: left; padding: 8px 12px;
    font-size: 10px; font-weight: 700; letter-spacing: 1px;
    color: var(--muted); text-transform: uppercase;
    border-bottom: 1px solid var(--border);
  }
  td {
    padding: 11px 12px;
    border-bottom: 1px solid var(--border);
    font-family: var(--mono);
    font-size: 12px;
  }
  tr:hover td { background: var(--surface2); }
  tr:last-child td { border-bottom: none; }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
    font-family: var(--font);
  }
  .badge-buy   { background: rgba(0,229,160,0.12); color: var(--green); }
  .badge-sell  { background: rgba(255,77,106,0.12); color: var(--red); }
  .badge-open  { background: rgba(45,212,255,0.12); color: var(--blue); }
  .badge-closed{ background: rgba(74,102,128,0.2);  color: var(--muted); }
  .badge-entry { background: rgba(240,180,41,0.12); color: var(--gold); }
  .badge-exit  { background: rgba(74,102,128,0.2);  color: var(--text2); }
  .pnl-pos { color: var(--green); }
  .pnl-neg { color: var(--red); }

  /* ── Live ticker ── */
  .ticker-bar {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 18px;
    display: flex;
    align-items: center;
    gap: 20px;
  }
  .ticker-sym { font-size: 13px; font-weight: 800; color: var(--text2); }
  .ticker-ltp { font-size: 28px; font-weight: 800; font-family: var(--mono); color: var(--gold); line-height: 1; }
  .ticker-change { font-family: var(--mono); font-size: 13px; }
  .ticker-meta { font-size: 11px; color: var(--muted); font-family: var(--mono); }

  /* ── Signals feed ── */
  .signal-feed { display: flex; flex-direction: column; gap: 8px; max-height: 320px; overflow-y: auto; }
  .signal-item {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: start;
    gap: 10px;
    transition: border-color .15s;
  }
  .signal-item:hover { border-color: var(--border2); }
  .signal-item.entry { border-left: 3px solid var(--gold); }
  .signal-item.exit  { border-left: 3px solid var(--muted); }
  .signal-dir { font-size: 18px; }
  .signal-body {}
  .signal-title { font-size: 12px; font-weight: 700; color: var(--text); margin-bottom: 2px; }
  .signal-reason { font-size: 11px; color: var(--text2); font-family: var(--mono); }
  .signal-filters { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
  .filter-tag {
    background: rgba(240,180,41,0.08); border: 1px solid rgba(240,180,41,0.2);
    color: var(--gold); font-size: 9px; font-weight: 700; padding: 1px 6px; border-radius: 3px; letter-spacing: 0.5px;
  }
  .signal-meta { text-align: right; }
  .signal-conf { font-family: var(--mono); font-size: 13px; font-weight: 700; }
  .signal-time { font-size: 10px; color: var(--muted); margin-top: 2px; }

  /* ── Open trade panel ── */
  .trade-active {
    background: rgba(0,229,160,0.04);
    border: 1px solid rgba(0,229,160,0.2);
    border-radius: 12px;
    padding: 18px;
  }
  .trade-active-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
  .trade-active-title { font-size: 13px; font-weight: 800; color: var(--green); letter-spacing: 0.5px; }
  .trade-row { display: flex; justify-content: space-between; font-size: 12px; font-family: var(--mono); padding: 4px 0; }
  .trade-row-k { color: var(--muted); }
  .trade-row-v { font-weight: 700; }

  /* ── PnL bar ── */
  .pnl-bar { height: 4px; border-radius: 2px; background: var(--border); overflow: hidden; margin-top: 10px; }
  .pnl-fill { height: 100%; border-radius: 2px; transition: width .5s; }

  /* ── Auth pages ── */
  .auth-page {
    min-height: 100vh;
    background: var(--bg);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .auth-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 40px;
    width: 100%;
    max-width: 420px;
  }
  .auth-logo { text-align: center; margin-bottom: 32px; }
  .auth-logo-mark {
    width: 56px; height: 56px;
    background: linear-gradient(135deg, var(--gold), var(--gold2));
    border-radius: 16px;
    display: flex; align-items: center; justify-content: center;
    font-size: 28px; margin: 0 auto 12px;
  }
  .auth-logo h1 { font-size: 22px; font-weight: 800; }
  .auth-logo h1 span { color: var(--gold); }
  .auth-logo p { color: var(--text2); font-size: 13px; margin-top: 4px; }
  .field { margin-bottom: 16px; }
  .field label { display: block; font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
  .field input {
    width: 100%;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 11px 14px;
    font-family: var(--font);
    font-size: 14px;
    color: var(--text);
    transition: border-color .15s;
  }
  .field input:focus { outline: none; border-color: var(--gold); }
  .field input::placeholder { color: var(--muted); }
  .auth-submit {
    width: 100%;
    padding: 13px;
    background: var(--gold);
    color: #000;
    border: none;
    border-radius: 10px;
    font-family: var(--font);
    font-size: 15px;
    font-weight: 800;
    cursor: pointer;
    margin-top: 8px;
    transition: background .15s;
  }
  .auth-submit:hover { background: var(--gold2); }
  .auth-toggle { text-align: center; margin-top: 20px; font-size: 13px; color: var(--text2); }
  .auth-toggle button { background: none; border: none; color: var(--gold); cursor: pointer; font-weight: 700; font-family: var(--font); }
  .error-msg { background: rgba(255,77,106,0.1); border: 1px solid rgba(255,77,106,0.3); color: var(--red); border-radius: 8px; padding: 10px 14px; font-size: 13px; margin-bottom: 16px; }

  /* ── Scrollbars ── */
  ::-webkit-scrollbar { width: 4px; height: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

  /* ── Page header ── */
  .page-header { margin-bottom: 24px; }
  .page-header h2 { font-size: 22px; font-weight: 800; }
  .page-header p  { font-size: 13px; color: var(--text2); margin-top: 4px; }

  /* ── Loading ── */
  .spinner { width: 20px; height: 20px; border: 2px solid var(--border); border-top-color: var(--gold); border-radius: 50%; animation: spin .7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loading-full { display: flex; align-items: center; justify-content: center; height: 100vh; gap: 12px; font-size: 14px; color: var(--text2); }

  /* ── Empty ── */
  .empty-state { text-align: center; padding: 48px 20px; color: var(--muted); }
  .empty-icon { font-size: 36px; margin-bottom: 12px; opacity: 0.5; }
  .empty-text { font-size: 13px; }

  /* ── Vol badge ── */
  .vol-high   { color: var(--red); }
  .vol-normal { color: var(--gold); }
  .vol-low    { color: var(--green); }

  /* ── Price sparkle ── */
  @keyframes priceFlash { 0%{opacity:0.5}100%{opacity:1} }
  .price-update { animation: priceFlash .3s ease; }

  /* ── Responsive ── */
  @media (max-width: 900px) {
    .app-shell { grid-template-columns: 1fr; }
    .sidebar { display: none; }
    .stats-grid { grid-template-columns: repeat(2,1fr); }
    .dash-grid { grid-template-columns: 1fr; }
  }
`;

// ─── Small components ───────────────────────────────────────────────
function Spinner() { return <div className="spinner" />; }

function EmptyState({ icon, text }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <div className="empty-text">{text}</div>
    </div>
  );
}

function VolBadge({ level }) {
  const cls = level === "HIGH" ? "vol-high" : level === "LOW" ? "vol-low" : "vol-normal";
  return <span className={cls}>{level || "—"}</span>;
}

function PnlNum({ v }) {
  if (v == null) return <span className="pnl-neg">—</span>;
  return <span className={v >= 0 ? "pnl-pos" : "pnl-neg"}>₹{v >= 0 ? "+" : ""}{v.toFixed(2)}</span>;
}

function fmt(n) { return n != null ? n.toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "—"; }
function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso + (iso.includes("Z") ? "" : "Z"));
  return d.toLocaleTimeString("en-IN", { hour12: false });
}
function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso + (iso.includes("Z") ? "" : "Z"));
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

// ─── Auth Pages ─────────────────────────────────────────────────────
function AuthPage() {
  const [mode, setMode]   = useState("login");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, signup } = useAuth();

  const [form, setForm] = useState({ username: "", email: "", password: "", balance: "100000" });
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));

  const submit = async e => {
    e.preventDefault(); setError(""); setLoading(true);
    try {
      if (mode === "login") await login(form.username, form.password);
      else await signup(form.username, form.email, form.password, parseFloat(form.balance));
    } catch (err) { setError(err.message); }
    setLoading(false);
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-mark">🥈</div>
          <h1>Silver<span>Edge</span></h1>
          <p>{mode === "login" ? "Sign in to your trading account" : "Create your trading account"}</p>
        </div>
        {error && <div className="error-msg">{error}</div>}
        <form onSubmit={submit}>
          <div className="field">
            <label>Username</label>
            <input value={form.username} onChange={set("username")} placeholder="trader_xyz" required />
          </div>
          {mode === "signup" && (
            <>
              <div className="field">
                <label>Email</label>
                <input type="email" value={form.email} onChange={set("email")} placeholder="you@example.com" required />
              </div>
              <div className="field">
                <label>Starting Balance (₹)</label>
                <input type="number" value={form.balance} onChange={set("balance")} min="10000" step="1000" required />
              </div>
            </>
          )}
          <div className="field">
            <label>Password</label>
            <input type="password" value={form.password} onChange={set("password")} placeholder="••••••••" required />
          </div>
          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? "Please wait…" : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>
        <div className="auth-toggle">
          {mode === "login" ? <>New here? <button onClick={() => { setMode("signup"); setError(""); }}>Create account</button></> : <>Have an account? <button onClick={() => { setMode("login"); setError(""); }}>Sign in</button></>}
        </div>
      </div>
    </div>
  );
}

// ─── Dashboard ──────────────────────────────────────────────────────
function Dashboard({ feed, tradingStatus }) {
  const { token, user, refreshUser } = useAuth();
  const [stats,   setStats]   = useState(null);
  const [signals, setSignals] = useState([]);
  const [allocation, setAllocation] = useState(null);
  const [allocLoading, setAllocLoading] = useState(false);

  const loadStats = useCallback(async () => {
    try { setStats(await apiFetch("/api/stats", {}, token)); } catch {}
  }, [token]);

  useEffect(() => {
    loadStats();
    apiFetch("/api/signals", {}, token).then(s => setSignals(s.slice(0, 8))).catch(() => {});
    if (tradingStatus?.allocation) setAllocation(tradingStatus.allocation);
  }, [token, tradingStatus]);

  const runAlloc = async () => {
    setAllocLoading(true);
    try { const a = await apiFetch("/api/allocate", { method: "POST" }, token); setAllocation(a); }
    catch (e) { alert(e.message); }
    setAllocLoading(false);
  };

  const openTrade = tradingStatus?.open_trade;
  const prevLtp = useRef(feed.ltp);
  const ltpChanged = feed.ltp !== prevLtp.current;
  useEffect(() => { prevLtp.current = feed.ltp; }, [feed.ltp]);

  return (
    <div>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Live market overview and account performance</p>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card gold">
          <div className="stat-label">Balance</div>
          <div className="stat-value">₹{((user?.balance || 0) / 1000).toFixed(1)}K</div>
          <div className="stat-sub">Available capital</div>
        </div>
        <div className="stat-card green">
          <div className="stat-label">Total P&L</div>
          <div className="stat-value" style={{ color: (stats?.total_pnl || 0) >= 0 ? "var(--green)" : "var(--red)" }}>
            ₹{(stats?.total_pnl || 0).toFixed(0)}
          </div>
          <div className="stat-sub">{stats?.total_trades || 0} closed trades</div>
        </div>
        <div className="stat-card blue">
          <div className="stat-label">Win Rate</div>
          <div className="stat-value">{stats?.win_rate || 0}%</div>
          <div className="stat-sub">{stats?.wins || 0}W / {stats?.losses || 0}L</div>
        </div>
        <div className="stat-card" style={{ borderTopColor: "var(--text2)" }}>
          <div className="stat-label">Signals Today</div>
          <div className="stat-value" style={{ color: "var(--text)" }}>{signals.length}</div>
          <div className="stat-sub">{signals.filter(s => s.signal_type === "ENTRY").length} entry signals</div>
        </div>
      </div>

      <div className="dash-grid">
        <div className="dash-left">
          {/* Live Ticker */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Live Price Feed</span>
              <div className="live-dot" style={{ background: feed.connected ? "var(--green)" : "var(--muted)" }} />
            </div>
            <div className="ticker-bar">
              <div>
                <div className="ticker-sym">{allocation?.trading_symbol || "MCX SILVER"}</div>
                <div className={`ticker-ltp ${ltpChanged ? "price-update" : ""}`}>
                  ₹{feed.ltp > 0 ? fmt(feed.ltp) : "—"}
                </div>
              </div>
              <div style={{ flex: 1 }}>
                {allocation && (
                  <div style={{ display: "flex", gap: 24 }}>
                    <div className="ticker-meta">Vol: <VolBadge level={allocation.volatility_level} /></div>
                    <div className="ticker-meta">ATR: {allocation.atr_pct?.toFixed(2) || "—"}%</div>
                    <div className="ticker-meta">Lots: {allocation.lots_possible || "—"}</div>
                    <div className="ticker-meta">Bars: {feed.barCount}</div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Allocation */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Smart Allocation</span>
              <button className="btn btn-ghost btn-sm" onClick={runAlloc} disabled={allocLoading}>
                {allocLoading ? <Spinner /> : "↻"} Recalculate
              </button>
            </div>
            {allocation && !allocation.error ? (
              <div className="alloc-grid">
                <div className="alloc-item"><div className="alloc-k">Contract</div><div className="alloc-v blue">{allocation.trading_symbol}</div></div>
                <div className="alloc-item"><div className="alloc-k">Symbol Type</div><div className="alloc-v">{allocation.symbol_type}</div></div>
                <div className="alloc-item"><div className="alloc-k">LTP</div><div className="alloc-v gold">₹{fmt(allocation.ltp)}</div></div>
                <div className="alloc-item"><div className="alloc-k">Volatility</div><div className="alloc-v"><VolBadge level={allocation.volatility_level} /></div></div>
                <div className="alloc-item"><div className="alloc-k">ATR%</div><div className="alloc-v">{allocation.atr_pct}%</div></div>
                <div className="alloc-item"><div className="alloc-k">Risk %</div><div className="alloc-v">{allocation.risk_pct}</div></div>
                <div className="alloc-item"><div className="alloc-k">Risk Amount</div><div className="alloc-v gold">₹{fmt(allocation.risk_amount)}</div></div>
                <div className="alloc-item"><div className="alloc-k">Lots</div><div className="alloc-v green">{allocation.lots_possible}</div></div>
                <div className="alloc-item"><div className="alloc-k">Total Qty</div><div className="alloc-v green">{allocation.total_quantity} units</div></div>
                <div className="alloc-item"><div className="alloc-k">Margin Used</div><div className="alloc-v">₹{fmt(allocation.total_margin)}</div></div>
                <div className="alloc-item"><div className="alloc-k">Remaining</div><div className="alloc-v">{allocation.days_to_expiry}d expiry</div></div>
                <div className="alloc-item"><div className="alloc-k">Reasoning</div><div className="alloc-v" style={{ fontSize: 11, lineHeight: 1.4 }}>{allocation.reasoning}</div></div>
              </div>
            ) : (
              <EmptyState icon="📊" text={allocation?.error || "Click Recalculate to run allocation"} />
            )}
          </div>
        </div>

        <div className="dash-right">
          {/* Open Trade */}
          {openTrade ? (
            <div className="trade-active">
              <div className="trade-active-header">
                <span className="trade-active-title">⚡ OPEN TRADE</span>
                <span className="badge badge-open">LIVE</span>
              </div>
              <div className="trade-row"><span className="trade-row-k">Symbol</span><span className="trade-row-v" style={{ color: "var(--blue)" }}>{openTrade.trading_symbol}</span></div>
              <div className="trade-row"><span className="trade-row-k">Direction</span><span className={`badge badge-${openTrade.direction.toLowerCase()}`}>{openTrade.direction}</span></div>
              <div className="trade-row"><span className="trade-row-k">Entry</span><span className="trade-row-v">₹{fmt(openTrade.entry_price)}</span></div>
              <div className="trade-row"><span className="trade-row-k">Stop Loss</span><span className="trade-row-v" style={{ color: "var(--red)" }}>₹{fmt(openTrade.stop_loss)}</span></div>
              <div className="trade-row"><span className="trade-row-k">Target</span><span className="trade-row-v" style={{ color: "var(--green)" }}>₹{fmt(openTrade.target)}</span></div>
              <div className="trade-row"><span className="trade-row-k">Qty / Lots</span><span className="trade-row-v">{openTrade.quantity} / {openTrade.lots}</span></div>
              <div className="trade-row"><span className="trade-row-k">LTP</span><span className="trade-row-v" style={{ color: "var(--gold)" }}>₹{fmt(feed.ltp)}</span></div>
              {feed.ltp > 0 && (() => {
                const unreal = openTrade.direction === "BUY"
                  ? (feed.ltp - openTrade.entry_price) * openTrade.quantity
                  : (openTrade.entry_price - feed.ltp) * openTrade.quantity;
                const pct = ((feed.ltp - openTrade.entry_price) / openTrade.entry_price * 100).toFixed(2);
                return (
                  <>
                    <div className="trade-row">
                      <span className="trade-row-k">Unrealised P&L</span>
                      <PnlNum v={Math.round(unreal)} />
                    </div>
                    <div className="pnl-bar">
                      <div className="pnl-fill" style={{
                        width: `${Math.min(100, Math.abs(unreal) / openTrade.quantity * 10)}%`,
                        background: unreal >= 0 ? "var(--green)" : "var(--red)"
                      }} />
                    </div>
                  </>
                );
              })()}
            </div>
          ) : (
            <div className="card" style={{ border: "1px dashed var(--border2)" }}>
              <EmptyState icon="💤" text="No open trade — engine watching for entry signal" />
            </div>
          )}

          {/* Recent Signals */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Recent Signals</span>
              <span style={{ fontSize: 11, color: "var(--muted)" }}>{signals.length} total</span>
            </div>
            <div className="signal-feed">
              {signals.length === 0 ? (
                <EmptyState icon="📡" text="Waiting for signals…" />
              ) : signals.map(s => (
                <div key={s.signal_id} className={`signal-item ${s.signal_type.toLowerCase()}`}>
                  <div className="signal-dir">{s.signal_type === "ENTRY" ? "📈" : "📉"}</div>
                  <div className="signal-body">
                    <div className="signal-title">
                      <span className={`badge badge-${s.direction.toLowerCase()}`}>{s.direction}</span>
                      {" "}
                      <span className={`badge badge-${s.signal_type.toLowerCase()}`}>{s.signal_type}</span>
                      {" "}₹{fmt(s.price)}
                    </div>
                    <div className="signal-reason">{s.reason?.slice(0, 60) || "—"}</div>
                    <div className="signal-filters">
                      {(s.filters || []).slice(0, 4).map(f => <span key={f} className="filter-tag">{f.replace(/_/g, " ")}</span>)}
                    </div>
                  </div>
                  <div className="signal-meta">
                    <div className="signal-conf" style={{ color: s.confidence > 0.8 ? "var(--green)" : "var(--gold)" }}>
                      {(s.confidence * 100).toFixed(0)}%
                    </div>
                    <div className="signal-time">{fmtTime(s.timestamp)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Trades Page ────────────────────────────────────────────────────
function TradesPage() {
  const { token } = useAuth();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/api/trades", {}, token).then(t => { setTrades(t); setLoading(false); }).catch(() => setLoading(false));
  }, [token]);

  return (
    <div>
      <div className="page-header">
        <h2>Trade History</h2>
        <p>All executed trades with P&L</p>
      </div>
      <div className="card">
        <div className="table-wrap">
          {loading ? (
            <div style={{ padding: 40, textAlign: "center" }}><Spinner /></div>
          ) : trades.length === 0 ? (
            <EmptyState icon="📋" text="No trades yet — start the engine to begin" />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Trade ID</th><th>Symbol</th><th>Dir</th>
                  <th>Entry ₹</th><th>Exit ₹</th>
                  <th>Qty</th><th>Lots</th>
                  <th>SL</th><th>Target</th>
                  <th>Status</th><th>P&L</th>
                  <th>Entry Time</th><th>Exit Time</th>
                  <th>Exit Reason</th>
                </tr>
              </thead>
              <tbody>
                {trades.map(t => (
                  <tr key={t.trade_id}>
                    <td style={{ color: "var(--text2)", fontSize: 10 }}>{t.trade_id.slice(-10)}</td>
                    <td style={{ color: "var(--blue)" }}>{t.trading_symbol}</td>
                    <td><span className={`badge badge-${(t.direction||"").toLowerCase()}`}>{t.direction}</span></td>
                    <td>₹{fmt(t.entry_price)}</td>
                    <td>{t.exit_price ? `₹${fmt(t.exit_price)}` : "—"}</td>
                    <td>{t.quantity}</td>
                    <td>{t.lots}</td>
                    <td style={{ color: "var(--red)" }}>₹{fmt(t.stop_loss)}</td>
                    <td style={{ color: "var(--green)" }}>₹{fmt(t.target)}</td>
                    <td><span className={`badge badge-${(t.status||"").toLowerCase()}`}>{t.status}</span></td>
                    <td><PnlNum v={t.pnl} /></td>
                    <td style={{ fontSize: 10, color: "var(--text2)" }}>{fmtDate(t.entry_time)} {fmtTime(t.entry_time)}</td>
                    <td style={{ fontSize: 10, color: "var(--text2)" }}>{t.exit_time ? `${fmtDate(t.exit_time)} ${fmtTime(t.exit_time)}` : "—"}</td>
                    <td style={{ fontSize: 10, color: "var(--text2)", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.exit_reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Signals Page ───────────────────────────────────────────────────
function SignalsPage() {
  const { token } = useAuth();
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState("ALL");

  useEffect(() => {
    apiFetch("/api/signals", {}, token).then(s => { setSignals(s); setLoading(false); }).catch(() => setLoading(false));
  }, [token]);

  const filtered = filter === "ALL" ? signals : signals.filter(s => s.signal_type === filter);

  return (
    <div>
      <div className="page-header">
        <h2>Signal Log</h2>
        <p>All generated entry & exit signals with filter breakdown</p>
      </div>
      <div className="card">
        <div className="card-header">
          <span className="card-title">All Signals ({filtered.length})</span>
          <div style={{ display: "flex", gap: 8 }}>
            {["ALL","ENTRY","EXIT"].map(f => (
              <button key={f} className={`btn btn-sm ${filter === f ? "btn-gold" : "btn-ghost"}`} onClick={() => setFilter(f)}>{f}</button>
            ))}
          </div>
        </div>
        <div className="table-wrap">
          {loading ? (
            <div style={{ padding: 40, textAlign: "center" }}><Spinner /></div>
          ) : filtered.length === 0 ? (
            <EmptyState icon="📡" text="No signals yet" />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Time</th><th>Type</th><th>Direction</th>
                  <th>Price ₹</th><th>Confidence</th>
                  <th>Filters</th><th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(s => (
                  <tr key={s.signal_id}>
                    <td style={{ fontSize: 10, color: "var(--text2)" }}>{fmtDate(s.timestamp)} {fmtTime(s.timestamp)}</td>
                    <td><span className={`badge badge-${s.signal_type.toLowerCase()}`}>{s.signal_type}</span></td>
                    <td><span className={`badge badge-${(s.direction||"none").toLowerCase()}`}>{s.direction}</span></td>
                    <td>₹{fmt(s.price)}</td>
                    <td style={{ color: s.confidence > 0.8 ? "var(--green)" : s.confidence > 0.65 ? "var(--gold)" : "var(--text2)" }}>
                      {(s.confidence * 100).toFixed(1)}%
                    </td>
                    <td>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                        {(s.filters || []).map(f => <span key={f} className="filter-tag">{f.replace(/_/g," ")}</span>)}
                      </div>
                    </td>
                    <td style={{ fontSize: 11, color: "var(--text2)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Settings Page ──────────────────────────────────────────────────
function SettingsPage() {
  const { token, user, refreshUser, logout } = useAuth();
  const [balance, setBalance] = useState(user?.balance || "");
  const [saving, setSaving]   = useState(false);
  const [saved,  setSaved]    = useState(false);

  const saveBalance = async () => {
    setSaving(true);
    try {
      await apiFetch("/api/me/balance", { method: "PUT", body: JSON.stringify({ balance: parseFloat(balance) }) }, token);
      await refreshUser();
      setSaved(true); setTimeout(() => setSaved(false), 2000);
    } catch (e) { alert(e.message); }
    setSaving(false);
  };

  return (
    <div>
      <div className="page-header">
        <h2>Settings</h2>
        <p>Manage your account and capital</p>
      </div>
      <div style={{ maxWidth: 480 }}>
        <div className="card">
          <div className="card-header"><span className="card-title">Account</span></div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <div className="alloc-k" style={{ marginBottom: 6 }}>Username</div>
              <div style={{ fontFamily: "var(--mono)", color: "var(--blue)", fontSize: 15 }}>{user?.username}</div>
            </div>
            <div>
              <div className="alloc-k" style={{ marginBottom: 6 }}>Email</div>
              <div style={{ color: "var(--text2)", fontSize: 14 }}>{user?.email}</div>
            </div>
            <div>
              <div className="alloc-k" style={{ marginBottom: 6 }}>Trading Capital (₹)</div>
              <div style={{ display: "flex", gap: 10 }}>
                <input
                  className="field"
                  style={{ flex: 1, background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 14px", fontFamily: "var(--mono)", fontSize: 15, color: "var(--gold)" }}
                  type="number"
                  value={balance}
                  onChange={e => setBalance(e.target.value)}
                  min="10000"
                  step="1000"
                />
                <button className="btn btn-gold" onClick={saveBalance} disabled={saving}>
                  {saving ? <Spinner /> : saved ? "✓ Saved" : "Update"}
                </button>
              </div>
              <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 6 }}>
                Changing capital triggers re-allocation on next trading start.
              </div>
            </div>
          </div>
          <div style={{ marginTop: 24, paddingTop: 20, borderTop: "1px solid var(--border)" }}>
            <button className="btn btn-danger" onClick={logout}>Sign Out</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main App ────────────────────────────────────────────────────────
function TradingApp() {
  const { token, user, logout } = useAuth();
  const [page, setPage]         = useState("dashboard");
  const [tradingStatus, setTradingStatus] = useState(null);
  const [tradingLoading, setTradingLoading] = useState(false);
  const [feed, setFeed]         = useState({ ltp: 0, connected: false, barCount: 0 });
  const wsRef = useRef(null);
  const statusInterval = useRef(null);

  // WebSocket for real-time updates
  useEffect(() => {
    if (!user) return;
    const ws = new WebSocket(`${WS}/ws/${user.user_id}`);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "TICK") {
        // Only update if it matches our current contract or we have no contract yet
        const currentToken = tradingStatus?.allocation?.token;
        if (!currentToken || msg.token === String(currentToken)) {
          setFeed(f => ({ ...f, ltp: msg.ltp, connected: true }));
        }
      } else if (msg.type === "ENTRY" || msg.type === "EXIT") {
        // Refresh status on trade events
        fetchStatus();
      }
    };
    ws.onerror = () => setFeed(f => ({ ...f, connected: false }));
    ws.onclose = () => setFeed(f => ({ ...f, connected: false }));
    return () => ws.close();
  }, [user]);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await apiFetch("/api/trading/status", {}, token);
      setTradingStatus(s);
      if (s.feed_ltp > 0) setFeed(f => ({ ...f, ltp: s.feed_ltp, connected: s.feed_connected }));
      // get bar count
      apiFetch("/api/feed/latest", {}, token).then(l => {
        setFeed(f => ({ ...f, barCount: l.bar_count || 0 }));
      }).catch(() => {});
    } catch {}
  }, [token]);

  useEffect(() => {
    fetchStatus();
    statusInterval.current = setInterval(fetchStatus, 5000);
    return () => clearInterval(statusInterval.current);
  }, [fetchStatus]);

  const toggleTrading = async () => {
    setTradingLoading(true);
    try {
      if (tradingStatus?.active) {
        await apiFetch("/api/trading/stop", { method: "POST" }, token);
      } else {
        await apiFetch("/api/trading/start", { method: "POST" }, token);
      }
      await fetchStatus();
    } catch (e) { alert(e.message); }
    setTradingLoading(false);
  };

  const isActive = tradingStatus?.active;

  const navItems = [
    { id: "dashboard", icon: "◈", label: "Dashboard" },
    { id: "trades",    icon: "⟁", label: "Trades" },
    { id: "signals",   icon: "⌬", label: "Signals" },
    { id: "settings",  icon: "⊙", label: "Settings" },
  ];

  return (
    <div className="app-shell">
      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-logo">
          <div className="logo-icon">🥈</div>
          Silver<span>Edge</span>
        </div>
        <div className="topbar-right">
          <div className={`live-dot ${feed.connected ? "" : "off"}`} title={feed.connected ? "Feed connected" : "Feed offline"} />
          {feed.ltp > 0 && <div className="balance-chip">₹{fmt(feed.ltp)}</div>}
          <div className="balance-chip" style={{ color: "var(--green)" }}>₹{fmt(user?.balance)}</div>
          <button
            className={`btn btn-sm ${isActive ? "btn-danger" : "btn-green"}`}
            onClick={toggleTrading}
            disabled={tradingLoading}
          >
            {tradingLoading ? <Spinner /> : isActive ? "⏹ Stop Engine" : "▶ Start Engine"}
          </button>
          <div className="user-badge" onClick={() => setPage("settings")}>
            <div className="avatar">{user?.username?.[0]?.toUpperCase()}</div>
            <span style={{ fontSize: 13, fontWeight: 700 }}>{user?.username}</span>
          </div>
        </div>
      </header>

      {/* Sidebar */}
      <nav className="sidebar">
        <div className="sidebar-label">Navigation</div>
        {navItems.map(n => (
          <div key={n.id} className={`nav-item ${page === n.id ? "active" : ""}`} onClick={() => setPage(n.id)}>
            <span className="nav-icon">{n.icon}</span>
            {n.label}
          </div>
        ))}
        <div style={{ flex: 1 }} />
        <div className="sidebar-label">Status</div>
        <div style={{ padding: "8px 12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <div className={`live-dot ${isActive ? "" : "off"}`} />
            <span style={{ fontSize: 12, color: isActive ? "var(--green)" : "var(--muted)" }}>
              {isActive ? "Engine Running" : "Engine Stopped"}
            </span>
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", fontFamily: "var(--mono)" }}>
            {feed.barCount} bars accumulated
          </div>
        </div>
      </nav>

      {/* Main */}
      <main className="main">
        {page === "dashboard" && <Dashboard feed={feed} tradingStatus={tradingStatus} />}
        {page === "trades"    && <TradesPage />}
        {page === "signals"   && <SignalsPage />}
        {page === "settings"  && <SettingsPage />}
      </main>
    </div>
  );
}

// ─── Root ────────────────────────────────────────────────────────────
export default function App() {
  return (
    <AuthProvider>
      <style>{styles}</style>
      <Inner />
    </AuthProvider>
  );
}

function Inner() {
  const { user, loading } = useAuth();
  if (loading) return (
    <>
      <style>{styles}</style>
      <div className="loading-full">
        <div className="spinner" />
        <span>Loading SilverEdge…</span>
      </div>
    </>
  );
  return user ? <TradingApp /> : <AuthPage />;
}
