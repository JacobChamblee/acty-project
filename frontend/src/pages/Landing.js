import React, { useEffect, useRef, useState } from 'react';
import { motion, useInView } from 'framer-motion';
import { Link } from 'react-router-dom';
import './Landing.css';

// ── Animated number counter ────────────────────────────────────────────────
function CountUp({ end, suffix = '', duration = 2000 }) {
  const [count, setCount] = useState(0);
  const ref = useRef();
  const inView = useInView(ref, { once: true });
  useEffect(() => {
    if (!inView) return;
    let start = 0;
    const step = end / (duration / 16);
    const timer = setInterval(() => {
      start += step;
      if (start >= end) { setCount(end); clearInterval(timer); }
      else setCount(Math.floor(start));
    }, 16);
    return () => clearInterval(timer);
  }, [inView, end, duration]);
  return <span ref={ref}>{count.toLocaleString()}{suffix}</span>;
}

// ── Mini SVG sparkline ─────────────────────────────────────────────────────
function Sparkline({ data, color = '#3B82F6', w = 100, h = 36 }) {
  if (!data.length) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    return `${x},${y}`;
  }).join(' ');
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block' }}>
      <defs>
        <linearGradient id={`sg${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.15"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${pts} ${w},${h}`} fill={`url(#sg${color.replace('#','')})`}/>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// ── Hero mock dashboard card ───────────────────────────────────────────────
function HeroCard({ label, value, unit, trend, trendDir, sparkData, color = '#3B82F6', icon }) {
  return (
    <div className="hero-mock-card">
      <div className="hero-mock-card-header">
        <span className="hero-mock-card-icon" style={{ background: color + '18' }}>{icon}</span>
        <span className="hero-mock-card-label">{label}</span>
      </div>
      <div className="hero-mock-card-value">
        {value}<span className="hero-mock-card-unit">{unit}</span>
      </div>
      <div className="hero-mock-card-footer">
        <span className={`hero-mock-card-trend ${trendDir}`}>{trend}</span>
        <Sparkline data={sparkData} color={color} w={80} h={28}/>
      </div>
    </div>
  );
}

const FADE_UP = {
  hidden: { opacity: 0, y: 24 },
  visible: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.65, delay: i * 0.12, ease: [0.22,1,0.36,1] } }),
};

const FEATURES = [
  { icon: '🔵', title: 'Real-Time OBD-II Capture', desc: 'Bluetooth SPP RFCOMM connection to your ELM327 dongle. Live RPM, coolant, fuel trims, throttle — at 1 Hz, all session long.' },
  { icon: '🛡️', title: 'Tamper-Evident Signing', desc: 'Every row SHA-256 hashed into a chain. Merkle root signed with Ed25519 from Android Keystore. Court-admissible proof your data was never altered.' },
  { icon: '🧠', title: 'AI Diagnostics (BYOK)', desc: 'Isolation Forest + XGBoost flag anomalies, RAG retrieves your service manual, your own Claude/GPT/Gemini key synthesizes a report. Raw CSV never reaches the LLM.' },
  { icon: '📊', title: 'NeedleNest Analytics', desc: 'LTFT trend across sessions, anomaly timeline, thermal profile, voltage trend, MPG over time. Longitudinal insight, not just the last drive.' },
  { icon: '🚗', title: 'Multi-Vehicle Fleet', desc: 'Separate profiles per vehicle. LTFT history, DTC log, service record, OBD adapter last-seen. Works for a single daily driver or a small fleet.' },
  { icon: '🔒', title: 'Owner-Encrypted Data', desc: 'Your key, your data. AES-256-GCM encryption before upload. Zero-knowledge identity tokens. No data brokerage — ever.' },
];

const PIPELINE_STEPS = [
  { tier: '0', label: 'Redis Cache', desc: 'Sub-ms hit', color: '#10B981' },
  { tier: '1', label: 'CPU Ensemble', desc: 'Isolation Forest + XGBoost < 2s', color: '#3B82F6' },
  { tier: '2', label: 'RAG Retrieval', desc: 'Service manual context 2–8s', color: '#8B5CF6' },
  { tier: '3', label: 'LLM Synthesis', desc: 'SSE stream (your API key)', color: '#1E40AF' },
  { tier: '4', label: 'LSTM / TFT', desc: 'Deep temporal analysis', color: '#F59E0B' },
  { tier: '5', label: 'Fleet Learning', desc: 'Privacy-preserving FL nightly', color: '#EF4444' },
];

export default function Landing() {
  return (
    <div className="landing-page">

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section className="hero-section">
        <div className="hero-bg-orb hero-bg-orb-1"/>
        <div className="hero-bg-orb hero-bg-orb-2"/>
        <div className="container hero-container">
          <motion.div className="hero-text" variants={FADE_UP} initial="hidden" animate="visible">
            <motion.div custom={0} variants={FADE_UP} className="hero-label">
              <span className="badge badge-blue">🌵 Now in Beta</span>
            </motion.div>
            <motion.h1 custom={1} variants={FADE_UP} className="hero-title">
              Your car's data,<br/>
              <span className="hero-title-accent">owned by you.</span>
            </motion.h1>
            <motion.p custom={2} variants={FADE_UP} className="hero-sub">
              Cactus Insights captures OBD-II telemetry with cryptographic signing,
              runs a six-tier ML pipeline on your data, and delivers AI-grounded diagnostics —
              without selling a single byte.
            </motion.p>
            <motion.div custom={3} variants={FADE_UP} className="hero-actions">
              <Link to="/register" className="btn btn-primary btn-lg">Get Started Free</Link>
              <Link to="/about" className="btn btn-white btn-lg">How It Works</Link>
            </motion.div>
            <motion.div custom={4} variants={FADE_UP} className="hero-trust">
              <div className="trust-item">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                Ed25519 signed sessions
              </div>
              <div className="trust-item">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                RFC 3161 timestamps
              </div>
              <div className="trust-item">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                Zero data brokerage
              </div>
            </motion.div>
          </motion.div>

          <motion.div
            className="hero-visual"
            initial={{ opacity: 0, x: 40, scale: 0.96 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            transition={{ duration: 0.9, delay: 0.3, ease: [0.22,1,0.36,1] }}
          >
            <div className="hero-dashboard-mock">
              <div className="hero-mock-header">
                <div className="hero-mock-title">
                  <span className="hero-mock-dot active"/>
                  Live Session · 2024 GR86
                </div>
                <span className="badge badge-green" style={{ fontSize: '0.7rem' }}>● Capturing</span>
              </div>
              <div className="hero-mock-cards">
                <HeroCard label="RPM" value="2,840" unit="" trend="↑ 12%" trendDir="up" color="#3B82F6"
                  icon="⚡" sparkData={[1200,1800,2200,1900,2400,2100,2600,2840]}/>
                <HeroCard label="Coolant" value="91" unit="°C" trend="Normal" trendDir="neutral" color="#10B981"
                  icon="🌡️" sparkData={[23,45,68,78,85,88,90,91]}/>
                <HeroCard label="LTFT B1" value="-6.2" unit="%" trend="↓ Lean watch" trendDir="warn" color="#F59E0B"
                  icon="⛽" sparkData={[-3,-4,-4.5,-5,-5.8,-6,-6.2,-6.2]}/>
                <HeroCard label="Throttle" value="18" unit="%" trend="Idle" trendDir="neutral" color="#8B5CF6"
                  icon="🎛️" sparkData={[0,5,12,8,15,20,18,18]}/>
              </div>
              <div className="hero-mock-score-row">
                <div className="hero-mock-score-card">
                  <div className="hero-mock-score-label">Health Score</div>
                  <div className="hero-mock-score-value" style={{ color: '#10B981' }}>82</div>
                  <div className="hero-mock-score-bar">
                    <div className="hero-mock-score-fill" style={{ width: '82%', background: '#10B981' }}/>
                  </div>
                </div>
                <div className="hero-mock-score-card">
                  <div className="hero-mock-score-label">Session Score</div>
                  <div className="hero-mock-score-value" style={{ color: '#3B82F6' }}>74</div>
                  <div className="hero-mock-score-bar">
                    <div className="hero-mock-score-fill" style={{ width: '74%', background: '#3B82F6' }}/>
                  </div>
                </div>
                <div className="hero-mock-score-card">
                  <div className="hero-mock-score-label">City MPG</div>
                  <div className="hero-mock-score-value" style={{ color: '#1E40AF' }}>26.4</div>
                  <div className="hero-mock-score-bar">
                    <div className="hero-mock-score-fill" style={{ width: '66%', background: '#1E40AF' }}/>
                  </div>
                </div>
              </div>
              <div className="hero-mock-insight">
                <span style={{ fontSize: '14px' }}>🧠</span>
                <p><strong>LTFT B1 trend:</strong> Lean drift from −3.8% → −6.2% over 8 sessions. Consistent with MAF thermal drift. Smoke test recommended.</p>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Stats strip */}
        <motion.div
          className="hero-stats-strip"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.8 }}
        >
          <div className="container">
            <div className="stats-row">
              {[
                { value: 70, suffix: '+', label: 'OBD-II PIDs tracked' },
                { value: 6, suffix: '-tier', label: 'ML pipeline' },
                { value: 9, suffix: '+', label: 'sessions on GR86' },
                { value: 100, suffix: '%', label: 'owner-encrypted' },
              ].map((s, i) => (
                <div className="stat-item" key={i}>
                  <div className="stat-number"><CountUp end={s.value} suffix={s.suffix}/></div>
                  <div className="stat-label">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </section>

      {/* ── Features grid ─────────────────────────────────────────────── */}
      <section className="section features-section" id="features">
        <div className="container">
          <motion.div className="section-header-center" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={FADE_UP}>
            <div className="section-label">Features</div>
            <h2 className="section-title">Everything your mechanic wishes<br/>they had — in your pocket.</h2>
            <p className="section-sub">Built by a car person for car people. Every feature has a real diagnostic use case behind it.</p>
          </motion.div>
          <div className="features-grid">
            {FEATURES.map((f, i) => (
              <motion.div key={i} custom={i % 3} variants={FADE_UP} initial="hidden" whileInView="visible" viewport={{ once: true }} className="feature-card glass-card">
                <div className="feature-icon">{f.icon}</div>
                <h3 className="feature-title">{f.title}</h3>
                <p className="feature-desc">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────────────── */}
      <section className="section how-section" id="how-it-works">
        <div className="container">
          <div className="how-grid">
            <motion.div className="how-text" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={FADE_UP}>
              <div className="section-label">How It Works</div>
              <h2 className="section-title">One dongle. Six tiers. Total insight.</h2>
              <p className="section-sub" style={{ marginBottom: '2rem' }}>
                Cactus doesn't just read your OBD port — it runs a full ML pipeline on your
                signed, encrypted data and streams AI-grounded insights back in real time.
              </p>
              <div className="pipeline-steps">
                {PIPELINE_STEPS.map((s, i) => (
                  <motion.div key={i} custom={i} variants={FADE_UP} initial="hidden" whileInView="visible" viewport={{ once: true }} className="pipeline-step">
                    <div className="pipeline-tier" style={{ background: s.color + '18', color: s.color, borderColor: s.color + '30' }}>
                      T{s.tier}
                    </div>
                    <div>
                      <div className="pipeline-step-title">{s.label}</div>
                      <div className="pipeline-step-desc">{s.desc}</div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
            <motion.div
              className="how-visual"
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.8, ease: [0.22,1,0.36,1] }}
            >
              <div className="how-diagram">
                <div className="how-node how-node-car">
                  <span>🚗</span>
                  <div>OBD-II Port</div>
                </div>
                <div className="how-arrow">↓ Bluetooth RFCOMM</div>
                <div className="how-node how-node-app">
                  <span>📱</span>
                  <div>Cactus App</div>
                  <div className="how-node-sub">Sign · Hash · Encrypt</div>
                </div>
                <div className="how-arrow">↓ HTTPS multipart</div>
                <div className="how-node how-node-api">
                  <span>⚙️</span>
                  <div>Cactus Backend</div>
                  <div className="how-node-sub">Anomaly · RAG · LLM</div>
                </div>
                <div className="how-arrow">↓ SSE stream</div>
                <div className="how-node how-node-insight">
                  <span>✨</span>
                  <div>AI Insight</div>
                  <div className="how-node-sub">Signed · Verifiable</div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ── Privacy section ───────────────────────────────────────────── */}
      <section className="section privacy-section" id="privacy">
        <div className="container">
          <div className="privacy-grid">
            <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={FADE_UP}>
              <div className="section-label">Privacy Architecture</div>
              <h2 className="section-title">Structurally incapable of selling your data.</h2>
              <p className="section-sub">
                Every privacy guarantee is enforced at the architecture level, not the policy level.
                Your data is encrypted before it leaves your device. We literally cannot read it.
              </p>
              <div className="privacy-pillars">
                {[
                  { icon: '🔑', title: 'Owner-Encrypted', desc: 'AES-256-GCM with your key. Backend stores cipher; you hold the key.' },
                  { icon: '⛓️', title: 'Hash-Chain Integrity', desc: 'SHA-256 per record. Tampering breaks the chain. Independently verifiable.' },
                  { icon: '🕶️', title: 'Zero-Knowledge Identity', desc: 'Rotating pseudonymous tokens. Your real identity never touches session data.' },
                  { icon: '🤝', title: 'Federated Learning', desc: 'Fleet models improve with ε ≤ 1.0 differential privacy. No raw data shared.' },
                ].map((p, i) => (
                  <motion.div key={i} custom={i} variants={FADE_UP} initial="hidden" whileInView="visible" viewport={{ once: true }} className="privacy-pillar">
                    <span className="privacy-pillar-icon">{p.icon}</span>
                    <div>
                      <div className="privacy-pillar-title">{p.title}</div>
                      <div className="privacy-pillar-desc">{p.desc}</div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
            <motion.div
              className="privacy-cert-panel"
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.7, delay: 0.2 }}
            >
              <div className="cert-card glass-card">
                <div className="cert-header">
                  <span style={{ fontSize: '24px' }}>🛡️</span>
                  <div>
                    <div className="cert-title">Verified Session</div>
                    <div className="cert-sub">acty-labs.com/verify</div>
                  </div>
                </div>
                {[
                  { label: 'Ed25519 Signature', status: '✓ Valid', color: '#10B981' },
                  { label: 'Hash Chain', status: '✓ Intact', color: '#10B981' },
                  { label: 'RFC 3161 Timestamp', status: '✓ Anchored', color: '#10B981' },
                  { label: 'Merkle Root', status: '✓ Verified', color: '#10B981' },
                ].map((item, i) => (
                  <div key={i} className="cert-row">
                    <span className="cert-row-label">{item.label}</span>
                    <span className="cert-row-status" style={{ color: item.color }}>{item.status}</span>
                  </div>
                ))}
                <div className="cert-qr-placeholder">
                  <div className="cert-qr-icon">QR</div>
                  <div className="cert-qr-text">Scan to verify session on-chain</div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────── */}
      <section className="section cta-section" id="early-access">
        <div className="container">
          <motion.div className="cta-card glass-card" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={FADE_UP}>
            <div className="cta-inner">
              <div className="cta-text">
                <h2 className="cta-title">Start your first session today.</h2>
                <p className="cta-sub">Free forever. Bring your own OBD-II dongle. No subscription. No data selling. Ever.</p>
              </div>
              <div className="cta-actions">
                <Link to="/register" className="btn btn-primary btn-lg">Create Free Account</Link>
                <Link to="/login" className="btn btn-ghost btn-lg">Sign In</Link>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

    </div>
  );
}
