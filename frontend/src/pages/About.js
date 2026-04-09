import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import './About.css';

const FADE = {
  hidden: { opacity: 0, y: 20 },
  visible: (i=0) => ({ opacity: 1, y: 0, transition: { duration: 0.6, delay: i*0.1, ease: [0.22,1,0.36,1] } }),
};

const SECURITY_LAYERS = [
  { icon: '🔐', color: '#3B82F6', bg: '#EFF6FF', title: 'AES-256-GCM Encryption', desc: 'All session data encrypted with your key before leaving the device. The backend stores only ciphertext — it cannot read your data.' },
  { icon: '✍️', color: '#8B5CF6', bg: '#EDE9FE', title: 'Ed25519 Session Signing', desc: 'Every session signed by a hardware-backed Ed25519 key (Android Keystore TEE / ATECC608B). Private key never exported.' },
  { icon: '⛓️', color: '#F59E0B', bg: '#FFFBEB', title: 'SHA-256 Hash Chain', desc: 'Each record includes SHA-256(seq + timestamp + PIDs + prev_hash). Tampering any record breaks the entire chain — detectable by anyone.' },
  { icon: '🌳', color: '#10B981', bg: '#ECFDF5', title: 'Merkle Root Manifest', desc: 'Session-end Merkle tree over all record hashes. Root signed and anchored. Backend re-verifies independently on upload.' },
  { icon: '⏱️', color: '#EF4444', bg: '#FEF2F2', title: 'RFC 3161 Timestamp', desc: 'DigiCert TSA anchor embedded in each session manifest. Provides court-admissible proof of data capture time.' },
  { icon: '🕶️', color: '#1E40AF', bg: '#EFF6FF', title: 'Zero-Knowledge Identity', desc: 'Rotating pseudonymous tokens. Your real identity is never stored alongside session data.' },
];

const ML_PIPELINE = [
  { tier: 'T0', title: 'Redis Cache', time: '< 1ms', color: '#10B981', desc: 'Cache hit on known vehicle+session pattern. Returns immediately without touching any ML model.' },
  { tier: 'T1', title: 'CPU Ensemble', time: '< 2s', color: '#3B82F6', desc: 'Isolation Forest anomaly detection on 11 PIDs + XGBoost predictive maintenance. Runs synchronously on every upload.' },
  { tier: 'T2', title: 'RAG Retrieval', time: '2–8s', color: '#8B5CF6', desc: 'ChromaDB semantic search over ingested factory service manuals. Returns OEM-specified thresholds and FSM citations for your exact vehicle.' },
  { tier: 'T3', title: 'LLM Synthesis', time: '5–30s', color: '#1E40AF', desc: 'Your own API key (Claude, GPT-4o, Gemini, DeepSeek, Llama). Receives only pre-analyzed CactusPrompt — never raw CSV. SSE streamed.' },
  { tier: 'T4', title: 'LSTM / TFT', time: '2–5 min', color: '#F59E0B', desc: 'Deep temporal analysis via Celery async job. LSTM Autoencoder reconstruction error + Temporal Fusion Transformer for predictive insights.' },
  { tier: 'T5', title: 'Fleet FL', time: 'Nightly', color: '#EF4444', desc: 'Federated Learning aggregation via Flower. ε ≤ 1.0 differential privacy enforced. Global model improves without any individual raw data shared.' },
];

const BYOK_PROVIDERS = [
  { name: 'Anthropic Claude', models: 'claude-opus-4, claude-sonnet-4', color: '#D97706' },
  { name: 'OpenAI GPT-4o', models: 'gpt-4o, gpt-4o-mini, o3, o4-mini', color: '#10A37F' },
  { name: 'Google Gemini', models: 'gemini-2.0-flash, gemini-2.5-pro', color: '#4285F4' },
  { name: 'Meta Llama (Groq)', models: 'llama-3.3-70b-versatile', color: '#0064E0' },
  { name: 'DeepSeek', models: 'deepseek-chat, deepseek-reasoner', color: '#1E40AF' },
  { name: 'Mistral AI', models: 'mistral-large, mixtral-8x7b', color: '#FF7000' },
  { name: 'Cohere', models: 'command-r-plus, command-r', color: '#39594D' },
];

export default function About() {
  return (
    <div className="page-content about-page">

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section className="about-hero">
        <div className="about-hero-bg-orb"/>
        <div className="container">
          <motion.div className="about-hero-inner" variants={FADE} initial="hidden" animate="visible">
            <div className="section-label">About Cactus Insights</div>
            <h1 className="about-hero-title">
              A car's data is<br/>
              <span className="hero-title-accent">evidence, not revenue.</span>
            </h1>
            <p className="about-hero-sub">
              We built Cactus because every OBD telemetry platform before it either
              owned your data, sold it, or both. We decided the right answer was to
              make it structurally impossible for us to do either.
            </p>
          </motion.div>
        </div>
      </section>

      {/* ── Mission ───────────────────────────────────────────────────── */}
      <section className="section about-mission-section">
        <div className="container">
          <div className="about-mission-grid">
            <motion.div variants={FADE} initial="hidden" whileInView="visible" viewport={{ once: true }}>
              <div className="section-label">Mission</div>
              <h2 className="section-title">Owner-encrypted telemetry. Always.</h2>
              <p style={{ fontSize: '1.05rem', lineHeight: 1.75, marginBottom: '1.5rem' }}>
                <strong>Acty Labs</strong> builds privacy-first automotive diagnostics infrastructure. Our flagship product,
                Cactus Insights, is the user-facing interface to that stack — free, forever, for the people who own the cars.
              </p>
              <p style={{ fontSize: '1rem', lineHeight: 1.75, color: '#475569' }}>
                We make money on hardware sales and verified report fees. Not data. That's not an aspiration —
                it's enforced by the architecture. Your data is encrypted before it leaves your device.
                We literally cannot read it, sell it, or lose it in a meaningful breach.
              </p>
            </motion.div>
            <motion.div variants={FADE} initial="hidden" whileInView="visible" viewport={{ once: true }} custom={1}>
              <div className="about-values-grid">
                {[
                  { icon: '🏛️', title: 'Court-Admissible', desc: 'Hash-chain + RFC 3161 timestamps + Ed25519 signing = defensible evidence.' },
                  { icon: '🚫', title: 'No Data Brokerage', desc: 'Structural guarantee. Owner-encryption makes it architecturally impossible.' },
                  { icon: '🔬', title: 'FSM-Grounded AI', desc: 'Factory service manual RAG. Real thresholds, not LLM hallucinations.' },
                  { icon: '🤝', title: 'Bootstrapped', desc: 'No VC. No investor pressure to monetize your data. Revenue = hardware + reports.' },
                ].map((v, i) => (
                  <div key={i} className="about-value-card glass-card">
                    <div style={{ fontSize: '1.75rem', marginBottom: '0.625rem' }}>{v.icon}</div>
                    <div style={{ fontWeight: 700, color: '#0F172A', marginBottom: '0.375rem' }}>{v.title}</div>
                    <p style={{ fontSize: '0.8125rem', color: '#475569', lineHeight: 1.6, margin: 0 }}>{v.desc}</p>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ── Security layers ───────────────────────────────────────────── */}
      <section className="section about-security-section">
        <div className="container">
          <motion.div className="section-header-center" variants={FADE} initial="hidden" whileInView="visible" viewport={{ once: true }}>
            <div className="section-label">Security Architecture</div>
            <h2 className="section-title">Six layers of cryptographic integrity.</h2>
            <p className="section-sub">Every layer is independently verifiable. No single trusted party. No way to fake a report.</p>
          </motion.div>
          <div className="security-grid">
            {SECURITY_LAYERS.map((s, i) => (
              <motion.div key={i} custom={i % 3} variants={FADE} initial="hidden" whileInView="visible" viewport={{ once: true }} className="security-card glass-card">
                <div className="security-icon" style={{ background: s.bg, color: s.color }}>{s.icon}</div>
                <h3 className="security-title">{s.title}</h3>
                <p className="security-desc">{s.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── ML Pipeline ──────────────────────────────────────────────── */}
      <section className="section about-pipeline-section">
        <div className="container">
          <motion.div className="section-header-center" variants={FADE} initial="hidden" whileInView="visible" viewport={{ once: true }}>
            <div className="section-label">ML Pipeline</div>
            <h2 className="section-title">Six tiers. From cache to federated learning.</h2>
            <p className="section-sub">Each tier adds depth. Tier 0 hits in under a millisecond. Tier 5 improves the global model every night.</p>
          </motion.div>
          <div className="pipeline-full">
            {ML_PIPELINE.map((p, i) => (
              <motion.div key={i} custom={i} variants={FADE} initial="hidden" whileInView="visible" viewport={{ once: true }} className="pipeline-full-item">
                <div className="pipeline-full-header">
                  <div className="pipeline-full-tier" style={{ background: p.color + '18', color: p.color, borderColor: p.color + '40' }}>
                    {p.tier}
                  </div>
                  <div>
                    <div className="pipeline-full-title">{p.title}</div>
                    <span className="badge badge-gray" style={{ fontSize: '0.7rem' }}>{p.time}</span>
                  </div>
                </div>
                <p className="pipeline-full-desc">{p.desc}</p>
                {i < ML_PIPELINE.length - 1 && <div className="pipeline-full-arrow">↓</div>}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── BYOK ─────────────────────────────────────────────────────── */}
      <section className="section byok-section">
        <div className="container">
          <div className="byok-grid">
            <motion.div variants={FADE} initial="hidden" whileInView="visible" viewport={{ once: true }}>
              <div className="section-label">Bring Your Own Key</div>
              <h2 className="section-title">Your API key. Your bill. Your insight.</h2>
              <p className="section-sub" style={{ marginBottom: '1.5rem' }}>
                Cactus never calls a commercial LLM on your behalf using a shared key. You register your own API key — encrypted on-device with AES-256-GCM before it ever touches our servers.
              </p>
              <p style={{ fontSize: '0.9375rem', color: '#475569', lineHeight: 1.7 }}>
                The LLM receives a structured <strong>CactusPrompt</strong> — pre-analyzed features from the ML pipeline, FSM citations, cross-session trends. <em>Never raw OBD CSV data.</em> This is why Cactus insight is better than uploading your CSV to ChatGPT directly.
              </p>
            </motion.div>
            <motion.div variants={FADE} initial="hidden" whileInView="visible" viewport={{ once: true }} custom={1}>
              <div className="byok-providers">
                {BYOK_PROVIDERS.map((p, i) => (
                  <div key={i} className="byok-provider-row">
                    <div className="byok-provider-dot" style={{ background: p.color }}/>
                    <div>
                      <div style={{ fontWeight: 600, color: '#0F172A', fontSize: '0.9rem' }}>{p.name}</div>
                      <div style={{ fontSize: '0.775rem', color: '#94A3B8' }}>{p.models}</div>
                    </div>
                    <span className="badge badge-green" style={{ marginLeft: 'auto' }}>Supported</span>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ── Verified reports ─────────────────────────────────────────── */}
      <section className="section verified-section">
        <div className="container">
          <motion.div className="section-header-center" variants={FADE} initial="hidden" whileInView="visible" viewport={{ once: true }}>
            <div className="section-label">Verified Reports</div>
            <h2 className="section-title">Why a Cactus report means something<br/>a ChatGPT export doesn't.</h2>
          </motion.div>
          <div className="verified-compare">
            <div className="verified-col">
              <div className="verified-col-header bad">CSV upload to any LLM</div>
              {['No signature — anyone can edit the file', 'No timestamp — date is self-reported', 'LLM sees raw data — hallucination risk', 'No FSM grounding — generic advice', 'No cross-session memory', 'Worthless in a dispute'].map((t, i) => (
                <div key={i} className="verified-row bad">
                  <span style={{ color: '#EF4444' }}>✗</span> {t}
                </div>
              ))}
            </div>
            <div className="verified-col">
              <div className="verified-col-header good">Cactus Verified Report</div>
              {['Ed25519 signed by device hardware', 'RFC 3161 timestamp — DigiCert anchor', 'LLM receives CactusPrompt — no raw data', 'FSM-grounded: OEM spec citations', 'Longitudinal memory across all sessions', 'Legally defensible. Mechanic-readable.'].map((t, i) => (
                <div key={i} className="verified-row good">
                  <span style={{ color: '#10B981' }}>✓</span> {t}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────── */}
      <section className="section about-cta">
        <div className="container">
          <motion.div className="cta-card glass-card" variants={FADE} initial="hidden" whileInView="visible" viewport={{ once: true }}>
            <div className="cta-inner">
              <div className="cta-text">
                <h2 className="cta-title">Ready to own your data?</h2>
                <p className="cta-sub">Free forever. Bring your OBD-II dongle and your own API key.</p>
              </div>
              <div className="cta-actions">
                <Link to="/register" className="btn btn-primary btn-lg">Get Started Free</Link>
                <a href="https://github.com/JacobChamblee/acty-project" target="_blank" rel="noopener noreferrer" className="btn btn-white btn-lg">View on GitHub</a>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

    </div>
  );
}
