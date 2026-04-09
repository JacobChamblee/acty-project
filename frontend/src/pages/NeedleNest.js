import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts';
import { Sidebar } from './Dashboard';
import './NeedleNest.css';

// ── Date range selector ──────────────────────────────────────────────────────
const RANGES = ['7d', '30d', '90d', 'All'];

// ── Mock data ─────────────────────────────────────────────────────────────────
const LTFT_DATA = [
  { date: 'Mar 30', ltftB1: -3.8, ltftB2: -4.1 },
  { date: 'Apr 1',  ltftB1: -4.2, ltftB2: -4.3 },
  { date: 'Apr 2',  ltftB1: -4.8, ltftB2: -4.5 },
  { date: 'Apr 3',  ltftB1: -5.1, ltftB2: -4.8 },
  { date: 'Apr 4',  ltftB1: -5.8, ltftB2: -5.0 },
  { date: 'Apr 5',  ltftB1: -6.0, ltftB2: -5.2 },
  { date: 'Apr 7',  ltftB1: -6.2, ltftB2: -5.4 },
];

const ANOMALY_DATA = [
  { date: 'Mar 30', score: 0.12, anomaly: 0 },
  { date: 'Apr 1',  score: 0.18, anomaly: 0 },
  { date: 'Apr 2',  score: 0.31, anomaly: 0 },
  { date: 'Apr 3',  score: 0.42, anomaly: 0 },
  { date: 'Apr 4',  score: 0.58, anomaly: 1 },
  { date: 'Apr 5',  score: 0.61, anomaly: 1 },
  { date: 'Apr 7',  score: 0.54, anomaly: 1 },
];

const THERMAL_DATA = [
  { min: 0,  coolant: 22,  oil: 22,  catalyst: 18 },
  { min: 1,  coolant: 35,  oil: 24,  catalyst: 50 },
  { min: 2,  coolant: 52,  oil: 27,  catalyst: 120 },
  { min: 3,  coolant: 67,  oil: 31,  catalyst: 220 },
  { min: 4,  coolant: 78,  oil: 38,  catalyst: 305 },
  { min: 5,  coolant: 86,  oil: 47,  catalyst: 358 },
  { min: 7,  coolant: 90,  oil: 60,  catalyst: 389 },
  { min: 10, coolant: 91,  oil: 72,  catalyst: 402 },
  { min: 15, coolant: 91,  oil: 81,  catalyst: 398 },
  { min: 20, coolant: 90,  oil: 85,  catalyst: 401 },
];

const VOLTAGE_DATA = [
  { date: 'Apr 1', idle: 14.1, load: 13.8, regen: 14.4 },
  { date: 'Apr 2', idle: 14.0, load: 13.7, regen: 14.3 },
  { date: 'Apr 3', idle: 14.2, load: 13.9, regen: 14.5 },
  { date: 'Apr 4', idle: 14.1, load: 13.8, regen: 14.4 },
  { date: 'Apr 5', idle: 14.0, load: 13.6, regen: 14.2 },
  { date: 'Apr 6', idle: 14.1, load: 13.7, regen: 14.3 },
  { date: 'Apr 7', idle: 14.1, load: 13.8, regen: 14.4 },
];

const MPG_DATA = [
  { date: 'Mar 30', mpg: 28.2, baseline: 27.0 },
  { date: 'Apr 1',  mpg: 26.1, baseline: 27.0 },
  { date: 'Apr 2',  mpg: 27.4, baseline: 27.0 },
  { date: 'Apr 3',  mpg: 25.8, baseline: 27.0 },
  { date: 'Apr 4',  mpg: 29.1, baseline: 27.0 },
  { date: 'Apr 5',  mpg: 26.7, baseline: 27.0 },
  { date: 'Apr 7',  mpg: 26.4, baseline: 27.0 },
];

const ANOMALY_EVENTS = [
  { date: 'Apr 4', type: 'LTFT Lean Drift', severity: 'warn', detail: 'LTFT B1 exceeded −5.5% threshold. Isolation Forest score: 0.58' },
  { date: 'Apr 5', type: 'LTFT Lean Drift', severity: 'warn', detail: 'LTFT B1 at −6.0%. Continues to worsen. Score: 0.61' },
  { date: 'Apr 7', type: 'Warm-idle Retard', severity: 'warn', detail: '8 timing retard events at warm idle. Max −18°. Possible EVAP purge.' },
];

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

const FADE = {
  hidden: { opacity: 0, y: 16 },
  visible: (i=0) => ({ opacity: 1, y: 0, transition: { duration: 0.5, delay: i*0.07, ease: [0.22,1,0.36,1] } }),
};

// ── Anomaly severity badge ────────────────────────────────────────────────────
function SevBadge({ s }) {
  const map = { critical: 'badge-red', warn: 'badge-amber', ok: 'badge-green' };
  return <span className={`badge ${map[s] || 'badge-gray'}`}>{s === 'warn' ? '⚠ Watch' : s === 'critical' ? '🔴 Critical' : '✓ OK'}</span>;
}

// ── NeedleNest ────────────────────────────────────────────────────────────────
export default function NeedleNest() {
  const [range, setRange] = useState('7d');
  const [activeTab, setActiveTab] = useState('ltft');

  const TABS = [
    { id: 'ltft',     label: 'LTFT Trend' },
    { id: 'anomaly',  label: 'Anomaly Timeline' },
    { id: 'thermal',  label: 'Thermal Profile' },
    { id: 'voltage',  label: 'Voltage' },
    { id: 'mpg',      label: 'Fuel Economy' },
    { id: 'compare',  label: 'Cross-Session' },
  ];

  return (
    <div className="dashboard-layout">
      <Sidebar/>
      <main className="dashboard-main">
        <motion.div custom={0} variants={FADE} initial="hidden" animate="visible" className="dash-header">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h1 style={{ fontSize: '1.5rem' }}>NeedleNest Analytics</h1>
              <p style={{ color: '#94A3B8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
                2024 Toyota GR86 · Longitudinal diagnostics
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <div className="range-picker">
                {RANGES.map(r => (
                  <button key={r} className={`range-btn ${range === r ? 'active' : ''}`} onClick={() => setRange(r)}>{r}</button>
                ))}
              </div>
              <button className="btn btn-ghost btn-sm">Export CSV</button>
            </div>
          </div>
        </motion.div>

        {/* Summary KPIs */}
        <div className="kpi-grid" style={{ marginBottom: '1.25rem' }}>
          {[
            { icon: '⛽', bg: '#FFFBEB', label: 'Avg LTFT B1', value: '-5.2', unit: '%', trend: '↓ Lean drift', dir: 'warn' },
            { icon: '🔴', bg: '#FEF2F2', label: 'Anomaly Events', value: '3', unit: '', trend: 'Apr 4–7', dir: 'warn' },
            { icon: '🌡️', bg: '#EFF6FF', label: 'Warm-up Time', value: '4.2', unit: 'min', trend: '↑ 0.3 vs baseline', dir: 'neutral' },
            { icon: '⚡', bg: '#ECFDF5', label: 'Avg Voltage', value: '14.1', unit: 'V', trend: '✓ Normal range', dir: 'up' },
          ].map((k, i) => (
            <motion.div key={i} custom={i} variants={FADE} initial="hidden" animate="visible" className="kpi-card">
              <div className="kpi-icon-wrap" style={{ background: k.bg }}>{k.icon}</div>
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value">{k.value}<span className="kpi-unit">{k.unit}</span></div>
              <div className={`kpi-trend ${k.dir}`} style={{ marginTop: '0.5rem' }}>{k.trend}</div>
            </motion.div>
          ))}
        </div>

        {/* Tab nav */}
        <motion.div custom={4} variants={FADE} initial="hidden" animate="visible" className="nn-tab-bar">
          {TABS.map(t => (
            <button key={t.id} className={`nn-tab ${activeTab === t.id ? 'active' : ''}`} onClick={() => setActiveTab(t.id)}>
              {t.label}
            </button>
          ))}
        </motion.div>

        {/* Tab content */}
        <motion.div key={activeTab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>

          {/* ── LTFT Trend ─────────────────────────────────────────────── */}
          {activeTab === 'ltft' && (
            <div className="nn-grid-2">
              <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
                <div className="chart-card-title">Long-Term Fuel Trim — Bank 1 & Bank 2</div>
                <div className="chart-card-sub">Normal range: ±7.5% (action) · ±10% (concern) · Negative = running lean</div>
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                  <span className="badge badge-amber">⚠ B1 Lean watch (−6.2%)</span>
                  <span className="badge badge-gray">B2 Normal (−5.4%)</span>
                </div>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={LTFT_DATA} margin={{ top: 5, right: 10, bottom: 5, left: -15 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false}/>
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false}/>
                    <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`}/>
                    <Tooltip content={<CustomTooltip/>}/>
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }}/>
                    <ReferenceLine y={-7.5} stroke="#F59E0B" strokeDasharray="4 4" strokeWidth={1.5}
                      label={{ value: 'Watch limit', fill: '#F59E0B', fontSize: 10, position: 'insideTopRight' }}/>
                    <ReferenceLine y={0} stroke="#E2E8F0" strokeWidth={1}/>
                    <Line type="monotone" dataKey="ltftB1" name="LTFT B1" stroke="#F59E0B" strokeWidth={2.5} dot={{ fill: '#F59E0B', r: 4 }} activeDot={{ r: 6 }}/>
                    <Line type="monotone" dataKey="ltftB2" name="LTFT B2" stroke="#8B5CF6" strokeWidth={2.5} dot={{ fill: '#8B5CF6', r: 4 }} activeDot={{ r: 6 }} strokeDasharray="5 3"/>
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="chart-card">
                <div className="chart-card-title">LTFT B1 — Session Distribution</div>
                <div className="chart-card-sub">Warm-phase values across {range}</div>
                <div className="ltft-analysis">
                  {[
                    { session: 'S-1937', date: 'Mar 30', ltft: -3.8, status: 'ok' },
                    { session: 'S-1939', date: 'Apr 1',  ltft: -4.2, status: 'ok' },
                    { session: 'S-1940', date: 'Apr 2',  ltft: -4.8, status: 'ok' },
                    { session: 'S-1941', date: 'Apr 5',  ltft: -5.8, status: 'watch' },
                    { session: 'S-1942', date: 'Apr 6',  ltft: -6.0, status: 'watch' },
                    { session: 'S-1943', date: 'Apr 7',  ltft: -6.2, status: 'watch' },
                  ].map((s, i) => (
                    <div key={i} className="ltft-row">
                      <span className="session-id">{s.session}</span>
                      <span style={{ fontSize: '0.8rem', color: '#94A3B8' }}>{s.date}</span>
                      <div className="ltft-bar-wrap">
                        <div className="ltft-bar" style={{ width: `${Math.abs(s.ltft) / 10 * 100}%`, background: s.status === 'watch' ? '#F59E0B' : '#10B981' }}/>
                      </div>
                      <span style={{ fontWeight: 700, color: s.status === 'watch' ? '#B45309' : '#059669', fontSize: '0.875rem', minWidth: '50px', textAlign: 'right' }}>{s.ltft}%</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="chart-card">
                <div className="chart-card-title">Diagnostic Summary</div>
                <div className="chart-card-sub">AI-grounded interpretation</div>
                <div className="nn-diagnosis-card">
                  <div className="nn-diag-header">
                    <span style={{ fontSize: '20px' }}>⛽</span>
                    <div>
                      <div style={{ fontWeight: 700, color: '#0F172A', fontSize: '0.9rem' }}>LTFT Lean Drift — MAF Thermal</div>
                      <span className="badge badge-amber" style={{ marginTop: '0.3rem' }}>FSM §17-6: MAF sensor spec</span>
                    </div>
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: '#475569', lineHeight: 1.6, margin: '0.875rem 0' }}>
                    LTFT B1 has degraded from −3.8% → −6.2% across 7 sessions at a rate consistent with MAF thermal drift patterns observed in 23 other FA24 vehicles in the fleet.
                    MAF was cleaned → trend improving toward −5.5% warm plateau. Smoke test pending.
                  </p>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <span className="badge badge-blue">Isolation Forest: 0.54</span>
                    <span className="badge badge-gray">9 sessions analyzed</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── Anomaly Timeline ──────────────────────────────────────── */}
          {activeTab === 'anomaly' && (
            <div className="nn-grid-2">
              <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
                <div className="chart-card-title">Anomaly Score — Isolation Forest</div>
                <div className="chart-card-sub">Score &gt; 0.5 = anomaly flagged · Threshold line shown</div>
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart data={ANOMALY_DATA} margin={{ top: 5, right: 10, bottom: 5, left: -15 }}>
                    <defs>
                      <linearGradient id="anomGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#EF4444" stopOpacity={0.15}/>
                        <stop offset="95%" stopColor="#EF4444" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false}/>
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false}/>
                    <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} domain={[0, 1]}/>
                    <Tooltip content={<CustomTooltip/>}/>
                    <ReferenceLine y={0.5} stroke="#EF4444" strokeDasharray="4 4" strokeWidth={1.5}
                      label={{ value: 'Anomaly threshold', fill: '#EF4444', fontSize: 10, position: 'insideTopRight' }}/>
                    <Area type="monotone" dataKey="score" name="Anomaly Score" stroke="#EF4444" strokeWidth={2.5} fill="url(#anomGrad)" dot={{ fill: '#EF4444', r: 4 }}/>
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
                <div className="chart-card-title">Anomaly Events</div>
                <div className="chart-card-sub">Flagged by Isolation Forest · 3 events in range</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.5rem' }}>
                  {ANOMALY_EVENTS.map((ev, i) => (
                    <div key={i} className="anomaly-event-row">
                      <div className="anomaly-event-date">{ev.date}</div>
                      <div className="anomaly-event-body">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                          <span style={{ fontWeight: 700, color: '#0F172A', fontSize: '0.875rem' }}>{ev.type}</span>
                          <SevBadge s={ev.severity}/>
                        </div>
                        <p style={{ fontSize: '0.8125rem', color: '#475569', lineHeight: 1.5, margin: 0 }}>{ev.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ── Thermal Profile ───────────────────────────────────────── */}
          {activeTab === 'thermal' && (
            <div className="nn-grid-2">
              <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
                <div className="chart-card-title">Thermal Profile — Apr 7 Session</div>
                <div className="chart-card-sub">Coolant · Oil · Catalyst vs warm-up time (minutes)</div>
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                  <span className="badge badge-blue">Coolant 80°C @ 4.2 min</span>
                  <span className="badge badge-gray">Oil 80°C @ 7.1 min</span>
                  <span className="badge badge-green">Catalyst lit-off @ 4.0 min</span>
                </div>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={THERMAL_DATA} margin={{ top: 5, right: 10, bottom: 5, left: -15 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false}/>
                    <XAxis dataKey="min" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} tickFormatter={v => `${v}m`}/>
                    <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} tickFormatter={v => `${v}°C`}/>
                    <Tooltip content={<CustomTooltip/>}/>
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }}/>
                    <ReferenceLine y={80} stroke="#94A3B8" strokeDasharray="3 3" strokeWidth={1}
                      label={{ value: '80°C', fill: '#94A3B8', fontSize: 10 }}/>
                    <ReferenceLine y={300} stroke="#10B981" strokeDasharray="3 3" strokeWidth={1}
                      label={{ value: 'Catalyst lit-off', fill: '#10B981', fontSize: 10 }}/>
                    <Line type="monotone" dataKey="coolant" name="Coolant" stroke="#3B82F6" strokeWidth={2.5} dot={false}/>
                    <Line type="monotone" dataKey="oil" name="Oil" stroke="#F59E0B" strokeWidth={2.5} dot={false}/>
                    <Line type="monotone" dataKey="catalyst" name="Catalyst" stroke="#10B981" strokeWidth={2.5} dot={false}/>
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="chart-card">
                <div className="chart-card-title">Warm-up Summary</div>
                <div className="chart-card-sub">vs factory service spec</div>
                {[
                  { label: 'Coolant to 80°C', value: '4.2 min', spec: '< 5.5 min', ok: true },
                  { label: 'Oil to 80°C', value: '7.1 min', spec: '< 9.0 min', ok: true },
                  { label: 'Catalyst lit-off', value: '4.0 min', spec: '< 4.5 min', ok: true },
                  { label: 'Max coolant', value: '91°C', spec: '87–93°C', ok: true },
                ].map((row, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.65rem 0', borderBottom: '1px solid #F8FAFC' }}>
                    <div>
                      <div style={{ fontWeight: 600, color: '#0F172A', fontSize: '0.875rem' }}>{row.label}</div>
                      <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Spec: {row.spec}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontWeight: 700, color: '#0F172A', fontSize: '0.9rem' }}>{row.value}</span>
                      <span className={`badge ${row.ok ? 'badge-green' : 'badge-red'}`}>{row.ok ? '✓' : '✗'}</span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="chart-card">
                <div className="chart-card-title">Cross-Session Warm-up</div>
                <div className="chart-card-sub">Time to coolant 80°C by session</div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={[
                    { date: 'Apr 1', time: 4.0 }, { date: 'Apr 2', time: 4.1 },
                    { date: 'Apr 3', time: 4.5 }, { date: 'Apr 4', time: 4.3 },
                    { date: 'Apr 5', time: 3.9 }, { date: 'Apr 6', time: 4.4 },
                    { date: 'Apr 7', time: 4.2 },
                  ]} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false}/>
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94A3B8' }} axisLine={false} tickLine={false}/>
                    <YAxis tick={{ fontSize: 10, fill: '#94A3B8' }} axisLine={false} tickLine={false} tickFormatter={v => `${v}m`}/>
                    <Tooltip content={<CustomTooltip/>}/>
                    <Bar dataKey="time" name="Minutes" fill="#3B82F6" radius={[4,4,0,0]} maxBarSize={32}/>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* ── Voltage ───────────────────────────────────────────────── */}
          {activeTab === 'voltage' && (
            <div className="nn-grid-2">
              <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
                <div className="chart-card-title">Voltage Trend — Idle / Load / Regen</div>
                <div className="chart-card-sub">Normal: 13.8–14.5V · Watch: &lt;13.5V · Action: &lt;13.0V</div>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={VOLTAGE_DATA} margin={{ top: 5, right: 10, bottom: 5, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false}/>
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false}/>
                    <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false}
                      domain={[13.0, 15.0]} tickFormatter={v => `${v}V`}/>
                    <Tooltip content={<CustomTooltip/>}/>
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }}/>
                    <ReferenceLine y={13.5} stroke="#F59E0B" strokeDasharray="4 4" strokeWidth={1.5}
                      label={{ value: 'Watch', fill: '#F59E0B', fontSize: 10, position: 'insideTopRight' }}/>
                    <ReferenceLine y={14.5} stroke="#E2E8F0" strokeWidth={1}/>
                    <Line type="monotone" dataKey="idle" name="Idle" stroke="#3B82F6" strokeWidth={2.5} dot={{ fill: '#3B82F6', r: 3 }}/>
                    <Line type="monotone" dataKey="load" name="Under Load" stroke="#F59E0B" strokeWidth={2.5} dot={{ fill: '#F59E0B', r: 3 }} strokeDasharray="5 3"/>
                    <Line type="monotone" dataKey="regen" name="Regen" stroke="#10B981" strokeWidth={2.5} dot={{ fill: '#10B981', r: 3 }}/>
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* ── Fuel Economy ──────────────────────────────────────────── */}
          {activeTab === 'mpg' && (
            <div className="nn-grid-2">
              <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
                <div className="chart-card-title">Session MPG vs Baseline</div>
                <div className="chart-card-sub">Session average · GR86 FA24 fleet baseline: 27.0 MPG</div>
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={MPG_DATA} margin={{ top: 5, right: 10, bottom: 5, left: -15 }}>
                    <defs>
                      <linearGradient id="mpgGrad2" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.15}/>
                        <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false}/>
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false}/>
                    <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} domain={['auto','auto']}/>
                    <Tooltip content={<CustomTooltip/>}/>
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }}/>
                    <ReferenceLine y={27.0} stroke="#94A3B8" strokeDasharray="4 4" strokeWidth={1.5}
                      label={{ value: 'Fleet baseline', fill: '#94A3B8', fontSize: 10, position: 'insideTopRight' }}/>
                    <Area type="monotone" dataKey="mpg" name="Session MPG" stroke="#3B82F6" strokeWidth={2.5} fill="url(#mpgGrad2)" dot={{ fill: '#3B82F6', r: 4 }}/>
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* ── Cross-Session Compare ─────────────────────────────────── */}
          {activeTab === 'compare' && (
            <div className="nn-grid-2">
              <div className="chart-card" style={{ gridColumn: '1 / -1' }}>
                <div className="chart-card-title">Cross-Session Health Score</div>
                <div className="chart-card-sub">Overall health score across all sessions in range</div>
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart data={[
                    { date: 'Mar 30', health: 87 }, { date: 'Apr 1', health: 84 },
                    { date: 'Apr 2', health: 82 }, { date: 'Apr 3', health: 80 },
                    { date: 'Apr 4', health: 79 }, { date: 'Apr 5', health: 78 },
                    { date: 'Apr 7', health: 82 },
                  ]} margin={{ top: 5, right: 10, bottom: 5, left: -15 }}>
                    <defs>
                      <linearGradient id="healthGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10B981" stopOpacity={0.15}/>
                        <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false}/>
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false}/>
                    <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} domain={[60, 100]}/>
                    <Tooltip content={<CustomTooltip/>}/>
                    <Area type="monotone" dataKey="health" name="Health Score" stroke="#10B981" strokeWidth={2.5} fill="url(#healthGrad)" dot={{ fill: '#10B981', r: 4 }}/>
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

        </motion.div>
      </main>
    </div>
  );
}
