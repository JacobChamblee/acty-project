import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { API_BASE } from '../config';
import { motion } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useUser, computeMaintenanceItems } from '../context/UserContext';
import './Dashboard.css';

// ── Sidebar ──────────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { icon: '🏠', label: 'Dashboard',  path: '/dashboard' },
  { icon: '📊', label: 'NeedleNest', path: '/needlenest' },
  { icon: '🤖', label: 'Insights',   path: '/insights' },
  { icon: '📋', label: 'Sessions',   path: '/sessions' },
  { icon: '🚗', label: 'Vehicles',   path: '/vehicles' },
  { icon: '📤', label: 'Sharing',    path: '/sharing' },
];

export function Sidebar() {
  const loc = useLocation();
  return (
    <div className="sidebar">
      <div className="sidebar-section-label">Main</div>
      {NAV_ITEMS.slice(0, 4).map(n => (
        <Link key={n.path} to={n.path} className={`sidebar-nav-item ${loc.pathname === n.path ? 'active' : ''}`}>
          <span>{n.icon}</span> {n.label}
        </Link>
      ))}
      <div className="sidebar-section-label">Manage</div>
      {NAV_ITEMS.slice(4).map(n => (
        <Link key={n.path} to={n.path} className={`sidebar-nav-item ${loc.pathname === n.path ? 'active' : ''}`}>
          <span>{n.icon}</span> {n.label}
        </Link>
      ))}
      <Link to="/settings" className={`sidebar-nav-item ${loc.pathname === '/settings' ? 'active' : ''}`}>
        <span>⚙️</span> Settings
      </Link>
      <div style={{ flex: 1 }}/>
      <div className="sidebar-section-label">Quick Capture</div>
      <button className="sidebar-capture-btn">
        <span>⏺</span> Start Session
      </button>
    </div>
  );
}

// ── Health Score Ring ─────────────────────────────────────────────────────────
function HealthRing({ score, size = 120, strokeWidth = 10 }) {
  const r = (size - strokeWidth) / 2;
  const circ = 2 * Math.PI * r;
  const progress = (score / 100) * circ;
  const color = score >= 80 ? '#10B981' : score >= 55 ? '#F59E0B' : '#EF4444';
  return (
    <div className="health-ring-inner" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#E2E8F0" strokeWidth={strokeWidth}/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeLinecap="round" strokeDasharray={`${progress} ${circ}`}
          style={{ transition: 'stroke-dasharray 0.8s ease' }}
        />
      </svg>
      <div className="health-ring-label" style={{ position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center' }}>
        <div className="score" style={{ color }}>{score}</div>
        <div className="score-sub">/ 100</div>
      </div>
    </div>
  );
}

// ── Mini sparkline ────────────────────────────────────────────────────────────
function Spark({ data, color = '#3B82F6', h = 36, w = 80 }) {
  if (!data || !data.length) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => `${(i/(data.length-1))*w},${h - ((v-min)/range)*(h-4)-2}`).join(' ');
  const gradId = `sg${color.replace('#','')}${Math.random().toString(36).slice(2,6)}`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.15"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${pts} ${w},${h}`} fill={`url(#${gradId})`}/>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// ── Mock data ─────────────────────────────────────────────────────────────────
const SESSION_DATA = [
  { date: 'Apr 1', ltft: -3.8, rpm: 1840, mpg: 28.2, health: 87 },
  { date: 'Apr 2', ltft: -4.2, rpm: 2100, mpg: 26.1, health: 84 },
  { date: 'Apr 3', ltft: -4.8, rpm: 1950, mpg: 27.4, health: 82 },
  { date: 'Apr 4', ltft: -5.1, rpm: 2200, mpg: 25.8, health: 80 },
  { date: 'Apr 5', ltft: -5.8, rpm: 1780, mpg: 29.1, health: 79 },
  { date: 'Apr 6', ltft: -6.0, rpm: 2050, mpg: 26.7, health: 78 },
  { date: 'Apr 7', ltft: -6.2, rpm: 2840, mpg: 26.4, health: 82 },
];

const INSIGHTS = [
  { icon: '⚠️', bg: '#FFFBEB', border: '#FDE68A', title: 'LTFT B1 Lean Drift', severity: 'warn',
    desc: 'Long-term fuel trim drifted from −3.8% → −6.2% over 7 sessions. Consistent with MAF thermal drift. Smoke test recommended.' },
  { icon: '🌡️', bg: '#EFF6FF', border: '#BFDBFE', title: 'Normal Thermal Profile', severity: 'ok',
    desc: 'Coolant reaches 90°C in 4.2 min. Oil lags 2.8 min. Catalyst lit-off at 312°C. All within factory service spec.' },
  { icon: '⚡', bg: '#ECFDF5', border: '#A7F3D0', title: 'Charging System Healthy', severity: 'ok',
    desc: 'Voltage avg 14.1V. No thermal derating. Alternator output consistent across all sessions.' },
];

const SESSIONS = [
  { id: 'S-1943', date: 'Apr 7, 2026', vehicle: '2024 GR86', duration: '42 min', score: 74, ltft: '-6.2%', dtcs: 0, synced: true },
  { id: 'S-1942', date: 'Apr 6, 2026', vehicle: '2024 GR86', duration: '28 min', score: 71, ltft: '-6.0%', dtcs: 0, synced: true },
  { id: 'S-1941', date: 'Apr 5, 2026', vehicle: '2024 GR86', duration: '55 min', score: 68, ltft: '-5.8%', dtcs: 0, synced: true },
];

const FADE_UP = {
  hidden: { opacity: 0, y: 16 },
  visible: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.5, delay: i * 0.08, ease: [0.22,1,0.36,1] } }),
};

// ── Maintenance countdown panel ───────────────────────────────────────────────
function statusStyle(status) {
  switch (status) {
    case 'overdue':  return { color: '#DC2626', bg: '#FEF2F2', bar: '#EF4444', badge: 'Overdue' };
    case 'due_soon': return { color: '#B45309', bg: '#FEF3C7', bar: '#F59E0B', badge: 'Due Soon' };
    case 'watch':    return { color: '#B45309', bg: '#FFFBEB', bar: '#F59E0B', badge: 'Watch' };
    case 'ok':       return { color: '#065F46', bg: '#ECFDF5', bar: '#10B981', badge: 'Good' };
    default:         return { color: '#475569', bg: '#F8FAFC', bar: '#94A3B8', badge: 'Unknown' };
  }
}

function MaintenanceCountdownCard({ items, currentOdometer }) {
  if (!currentOdometer) {
    return (
      <div className="insight-card" style={{ background: '#F8FAFC', borderColor: '#E2E8F0', flexDirection: 'column', alignItems: 'stretch', gap: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
          <div className="insight-icon" style={{ background: '#E2E8F0' }}>🔧</div>
          <div>
            <h4 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 700, color: '#0F172A' }}>Maintenance Schedule</h4>
            <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>Oil change, filters, brakes, fluids</div>
          </div>
        </div>
        <p style={{ fontSize: '0.8125rem', color: '#64748B', margin: 0, lineHeight: 1.6 }}>
          Enter your current odometer in <Link to="/settings" style={{ color: '#1E40AF', fontWeight: 600 }}>Settings → Maintenance</Link> to enable mileage countdowns for all service items.
        </p>
      </div>
    );
  }

  return (
    <div className="insight-card" style={{ background: '#fff', borderColor: '#E2E8F0', flexDirection: 'column', alignItems: 'stretch', gap: 0, padding: '1rem 1.125rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.875rem' }}>
        <div>
          <h4 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 700, color: '#0F172A' }}>Maintenance Schedule</h4>
          <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>Current: {currentOdometer.toLocaleString()} mi</div>
        </div>
        <Link to="/settings" style={{ fontSize: '0.75rem', color: '#1E40AF', fontWeight: 600, textDecoration: 'none' }}>Edit →</Link>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
        {items.map((item) => {
          const s = statusStyle(item.status);
          const pct = item.pctUsed ?? 0;
          return (
            <div key={item.key} style={{ background: s.bg, borderRadius: 10, padding: '0.625rem 0.75rem', border: `1px solid ${s.bar}30` }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.375rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '1rem' }}>{item.icon}</span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#0F172A' }}>{item.label}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {item.miRemaining !== null && (
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: s.color }}>
                      {item.miRemaining <= 0
                        ? `${Math.abs(item.miRemaining).toLocaleString()} mi overdue`
                        : `${item.miRemaining.toLocaleString()} mi`}
                    </span>
                  )}
                  <span style={{ fontSize: '0.7rem', fontWeight: 700, color: s.color, background: s.bar + '20', padding: '1px 7px', borderRadius: 100, border: `1px solid ${s.bar}40` }}>{s.badge}</span>
                </div>
              </div>
              {item.pctUsed !== null && (
                <div style={{ height: 4, background: '#E2E8F0', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: s.bar, borderRadius: 2, transition: 'width 0.8s ease' }}/>
                </div>
              )}
              {item.status === 'unknown' && (
                <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '0.2rem' }}>
                  No record — <Link to="/settings" style={{ color: '#1E40AF' }}>add last service date</Link>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Custom tooltip ────────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '0.6rem 0.875rem', boxShadow: '0 4px 16px rgba(0,0,0,0.08)' }}>
      <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ fontSize: '0.875rem', fontWeight: 700, color: p.color }}>{p.name}: {p.value}</div>
      ))}
    </div>
  );
}

// ── Empty state (no vehicles) ─────────────────────────────────────────────────
function EmptyState({ username }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', textAlign: 'center', padding: '2rem' }}>
      <div style={{ fontSize: '4rem', marginBottom: '1.5rem' }}>🌵</div>
      <h2 style={{ fontSize: '1.75rem', fontWeight: 800, marginBottom: '0.75rem' }}>
        Welcome, {username || 'there'}!
      </h2>
      <p style={{ color: '#64748B', fontSize: '1.05rem', maxWidth: 460, lineHeight: 1.7, marginBottom: '2rem' }}>
        Your Cactus Insights account is ready. Add your first vehicle and OBD-II adapter to start capturing sessions and analyzing your vehicle's health.
      </p>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center' }}>
        <Link to="/vehicles" className="btn btn-primary btn-lg">
          Add Your First Vehicle
        </Link>
        <Link to="/about" className="btn btn-ghost btn-lg">
          Learn How It Works
        </Link>
      </div>
      <div style={{ marginTop: '3rem', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', maxWidth: 600, width: '100%' }}>
        {[
          { step: '1', label: 'Add vehicle', desc: 'Year, make, model, trim' },
          { step: '2', label: 'Pair OBD adapter', desc: 'Bluetooth or Wi-Fi dongle' },
          { step: '3', label: 'Start capturing', desc: 'Live PIDs & session analytics' },
        ].map(s => (
          <div key={s.step} style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, padding: '1.25rem', textAlign: 'center' }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#EFF6FF', color: '#1E40AF', fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 0.75rem' }}>{s.step}</div>
            <div style={{ fontWeight: 700, fontSize: '0.9rem', marginBottom: '0.25rem' }}>{s.label}</div>
            <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>{s.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const { user, activeVehicle, insightPrefs, dashPrefs, maintenance } = useUser();
  const navigate = useNavigate();

  const maintenanceItems = computeMaintenanceItems(maintenance);

  // Real sessions from API
  const [liveSessions, setLiveSessions] = useState([]);
  useEffect(() => {
    fetch(`${API_BASE}/sessions`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => setLiveSessions((data.sessions || []).filter(s => !s.error).slice(0, 5)))
      .catch(() => {});
  }, []);

  const vehicleName = activeVehicle
    ? [activeVehicle.year, activeVehicle.make, activeVehicle.model, activeVehicle.trim].filter(Boolean).join(' ')
    : null;

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  })();

  const hasVehicles = user?.vehicles?.length > 0;

  return (
    <div className="dashboard-layout">
      <Sidebar/>
      <main className="dashboard-main">

        {!hasVehicles ? (
          <EmptyState username={user?.username}/>
        ) : (
          <>
        <motion.div variants={FADE_UP} custom={0} initial="hidden" animate="visible" className="dash-header">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h1>{greeting}, {user?.username || 'there'}</h1>
              <p style={{ color: '#94A3B8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
                {vehicleName} · No sessions yet
              </p>
            </div>
            <Link to="/dashboard/capture" className="btn btn-primary">
              ⏺ Start Session
            </Link>
          </div>
        </motion.div>

        {/* KPI row */}
        <div className="kpi-grid">
          {[
            { icon: '❤️', bg: '#FEF2F2', label: 'Health Score', value: '82', unit: '/100', trend: '▼ 2 pts', dir: 'down', spark: [87,84,82,80,79,78,82] },
            { icon: '⛽', bg: '#FFFBEB', label: 'LTFT B1', value: '-6.2', unit: '%', trend: 'Watch lean drift', dir: 'warn', spark: [-3.8,-4.2,-4.8,-5.1,-5.8,-6.0,-6.2] },
            { icon: '🚗', bg: '#EFF6FF', label: 'City MPG', value: '26.4', unit: '', trend: '↑ 0.3 vs avg', dir: 'up', spark: [28.2,26.1,27.4,25.8,29.1,26.7,26.4] },
            { icon: '⚡', bg: '#ECFDF5', label: 'Voltage', value: '14.1', unit: 'V', trend: '✓ Normal', dir: 'up', spark: [14.0,14.2,14.1,14.3,14.0,14.1,14.1] },
          ].map((k, i) => (
            <motion.div key={i} custom={i} variants={FADE_UP} initial="hidden" animate="visible" className="kpi-card">
              <div className="kpi-icon-wrap" style={{ background: k.bg }}>{k.icon}</div>
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value">{k.value}<span className="kpi-unit">{k.unit}</span></div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.5rem' }}>
                <div className={`kpi-trend ${k.dir}`}>{k.trend}</div>
                <Spark data={k.spark} color={k.dir === 'up' ? '#10B981' : k.dir === 'warn' ? '#F59E0B' : '#EF4444'} w={60} h={28}/>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Main grid */}
        <div className="dash-main-grid">
          {/* Health + Session score */}
          <motion.div custom={4} variants={FADE_UP} initial="hidden" animate="visible" className="chart-card dash-health-card">
            <div className="chart-card-title">Vehicle Health</div>
            <div className="chart-card-sub">2024 Toyota GR86</div>
            <div className="dash-health-body">
              <div className="health-ring-wrap">
                <HealthRing score={82} size={130} strokeWidth={11}/>
                <div style={{ marginTop: '0.75rem', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.8rem', color: '#94A3B8', fontWeight: 500 }}>Overall</div>
                </div>
              </div>
              <div className="dash-sub-scores">
                {[
                  { label: 'Efficiency', score: 74, color: '#3B82F6' },
                  { label: 'Thermal', score: 91, color: '#10B981' },
                  { label: 'Smoothness', score: 80, color: '#8B5CF6' },
                  { label: 'Charging', score: 95, color: '#10B981' },
                ].map((s, i) => (
                  <div key={i} className="sub-score-row">
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                      <span style={{ fontSize: '0.8rem', color: '#475569', fontWeight: 500 }}>{s.label}</span>
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: s.color }}>{s.score}</span>
                    </div>
                    <div style={{ height: 5, background: '#E2E8F0', borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${s.score}%`, background: s.color, borderRadius: 3, transition: 'width 0.8s ease' }}/>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="dash-dtc-row">
              <div className="dash-dtc-item ok">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                No active DTCs
              </div>
              <div className="dash-dtc-item ok">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                0 pending codes
              </div>
            </div>
          </motion.div>

          {/* LTFT trend chart */}
          {dashPrefs.ltftChart && <motion.div custom={5} variants={FADE_UP} initial="hidden" animate="visible" className="chart-card">
            <div className="chart-card-title">LTFT B1 — Session Trend</div>
            <div className="chart-card-sub">Long-term fuel trim across 7 sessions · normal: ±7.5%</div>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              <span className="badge badge-amber">⚠ Lean watch</span>
              <span className="badge badge-gray">7 sessions</span>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={SESSION_DATA} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
                <defs>
                  <linearGradient id="ltftGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.15}/>
                    <stop offset="95%" stopColor="#F59E0B" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false}/>
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false}/>
                <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`}/>
                <Tooltip content={<CustomTooltip/>}/>
                <Area type="monotone" dataKey="ltft" name="LTFT B1" stroke="#F59E0B" strokeWidth={2.5} fill="url(#ltftGrad)" dot={{ fill: '#F59E0B', r: 3 }}/>
              </AreaChart>
            </ResponsiveContainer>
          </motion.div>}

          {/* Insights */}
          <motion.div custom={6} variants={FADE_UP} initial="hidden" animate="visible" className="chart-card dash-insights-card">
            <div className="chart-card-title">AI Insights</div>
            <div className="chart-card-sub">Powered by Isolation Forest + RAG · your API key</div>
            {insightPrefs.maintenanceCountdown && (
              <MaintenanceCountdownCard items={maintenanceItems} currentOdometer={maintenance?.currentOdometer}/>
            )}
            {insightPrefs.ltft && (
              <div className="insight-card" style={{ background: '#FFFBEB', borderColor: '#FDE68A' }}>
                <div className="insight-icon" style={{ background: '#FDE68A60' }}>⚠️</div>
                <div className="insight-body"><h4>LTFT B1 Lean Drift</h4><p>Long-term fuel trim drifted from −3.8% → −6.2% over 7 sessions. Consistent with MAF thermal drift. Smoke test recommended.</p></div>
              </div>
            )}
            {insightPrefs.thermal && (
              <div className="insight-card" style={{ background: '#EFF6FF', borderColor: '#BFDBFE' }}>
                <div className="insight-icon" style={{ background: '#BFDBFE60' }}>🌡️</div>
                <div className="insight-body"><h4>Normal Thermal Profile</h4><p>Coolant reaches 90°C in 4.2 min. Oil lags 2.8 min. Catalyst lit-off at 312°C. All within factory service spec.</p></div>
              </div>
            )}
            {insightPrefs.charging && (
              <div className="insight-card" style={{ background: '#ECFDF5', borderColor: '#A7F3D0' }}>
                <div className="insight-icon" style={{ background: '#A7F3D060' }}>⚡</div>
                <div className="insight-body"><h4>Charging System Healthy</h4><p>Voltage avg 14.1V. No thermal derating. Alternator output consistent across all sessions.</p></div>
              </div>
            )}
            <button className="btn btn-ghost btn-sm" style={{ width: '100%', marginTop: '0.5rem' }}>
              ✨ Generate Full AI Report
            </button>
          </motion.div>

          {/* Recent sessions */}
          {dashPrefs.sessionTable && <motion.div custom={7} variants={FADE_UP} initial="hidden" animate="visible" className="chart-card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
              <div>
                <div className="chart-card-title">Recent Sessions</div>
                <div className="chart-card-sub" style={{ marginBottom: 0 }}>
                  {liveSessions.length > 0 ? `${liveSessions.length} sessions · click to analyze` : 'No sessions synced yet'}
                </div>
              </div>
              <Link to="/sessions" className="btn btn-ghost btn-sm">View all</Link>
            </div>
            {liveSessions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem 1rem', color: '#94A3B8' }}>
                <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>📂</div>
                <div style={{ fontSize: '0.875rem' }}>
                  No sessions on server.{' '}
                  <Link to="/sessions" style={{ color: '#1E40AF', fontWeight: 600 }}>Upload a CSV</Link>
                  {' '}or sync from the Android app.
                </div>
              </div>
            ) : (
              <table className="sessions-table">
                <thead>
                  <tr>
                    <th>Session</th>
                    <th>Date</th>
                    <th>Duration</th>
                    <th>Score</th>
                    <th>LTFT B1</th>
                  </tr>
                </thead>
                <tbody>
                  {liveSessions.map(s => {
                    const ltft = s.ltft_b1 ?? s.avg_ltft_b1;
                    const label = s.filename
                      .replace(/^acty_obd_/, '')
                      .replace(/_[a-f0-9-]{36}\.csv$/, '')
                      .replace(/\.csv$/, '');
                    return (
                      <tr
                        key={s.filename}
                        style={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/insights?session=${encodeURIComponent(s.filename)}`)}
                        onMouseEnter={e => e.currentTarget.style.background = '#F8FAFC'}
                        onMouseLeave={e => e.currentTarget.style.background = ''}
                      >
                        <td><span className="session-id">{label}</span></td>
                        <td style={{ color: '#475569', fontSize: '0.8125rem' }}>{s.session_date || '—'}</td>
                        <td style={{ color: '#94A3B8', fontSize: '0.8125rem' }}>
                          {s.duration_min != null ? `${s.duration_min} min` : '—'}
                        </td>
                        <td>
                          {s.health_score != null
                            ? <span style={{ fontWeight: 700, color: s.health_score >= 75 ? '#10B981' : s.health_score >= 55 ? '#F59E0B' : '#EF4444' }}>{s.health_score}</span>
                            : <span style={{ color: '#94A3B8' }}>—</span>}
                        </td>
                        <td>
                          {ltft != null
                            ? <span style={{ fontWeight: 600, color: Math.abs(ltft) > 8 ? '#EF4444' : '#F59E0B' }}>{ltft > 0 ? '+' : ''}{Number(ltft).toFixed(1)}%</span>
                            : <span style={{ color: '#94A3B8' }}>—</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </motion.div>}

          {/* MPG trend */}
          {dashPrefs.mpgChart && <motion.div custom={8} variants={FADE_UP} initial="hidden" animate="visible" className="chart-card">
            <div className="chart-card-title">MPG Trend</div>
            <div className="chart-card-sub">Session average fuel economy · 7 sessions</div>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={SESSION_DATA} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
                <defs>
                  <linearGradient id="mpgGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.15}/>
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false}/>
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false}/>
                <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} domain={['auto','auto']}/>
                <Tooltip content={<CustomTooltip/>}/>
                <Area type="monotone" dataKey="mpg" name="MPG" stroke="#3B82F6" strokeWidth={2.5} fill="url(#mpgGrad)" dot={{ fill: '#3B82F6', r: 3 }}/>
              </AreaChart>
            </ResponsiveContainer>
          </motion.div>}

          {/* Quick actions */}
          {dashPrefs.quickActions && <motion.div custom={9} variants={FADE_UP} initial="hidden" animate="visible" className="chart-card">
            <div className="chart-card-title">Quick Actions</div>
            <div className="chart-card-sub">Common tasks</div>
            <div className="quick-actions-grid">
              {[
                { icon: '⏺', label: 'Start Session', color: '#1E40AF', bg: '#EFF6FF', to: '/dashboard/capture' },
                { icon: '📊', label: 'NeedleNest', color: '#8B5CF6', bg: '#EDE9FE', to: '/needlenest' },
                { icon: '📤', label: 'Share Report', color: '#10B981', bg: '#ECFDF5', to: '/sharing' },
                { icon: '🚗', label: 'Add Vehicle', color: '#F59E0B', bg: '#FFFBEB', to: '/vehicles' },
              ].map((a, i) => (
                <Link key={i} to={a.to} className="quick-action-btn" style={{ '--qa-color': a.color, '--qa-bg': a.bg }}>
                  <div className="qa-icon" style={{ background: a.bg, color: a.color }}>{a.icon}</div>
                  <span className="qa-label">{a.label}</span>
                </Link>
              ))}
            </div>
          </motion.div>}
        </div>
          </>
        )}
      </main>
    </div>
  );
}
