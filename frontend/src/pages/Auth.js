import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import './Auth.css';

const FADE_UP = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] } },
};

function SidePanel() {
  return (
    <div className="auth-side">
      <div className="auth-side-inner">
        <Link to="/" className="auth-brand">
          <div className="nav-brand-icon" style={{ width: 40, height: 40, fontSize: 22, borderRadius: 12 }}>🌵</div>
          <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fff' }}>Cactus Insights</span>
        </Link>
        <div className="auth-side-content">
          <h2 className="auth-side-title">Own your<br/>vehicle data.</h2>
          <p className="auth-side-sub">
            Cryptographically signed sessions. Six-tier ML pipeline.
            AI diagnostics powered by your own API key. No data selling. Ever.
          </p>
          <div className="auth-side-pills">
            {['Ed25519 Signed', 'RFC 3161 Timestamps', 'Zero Data Brokerage', 'BYOK AI'].map(p => (
              <div key={p} className="auth-side-pill">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                {p}
              </div>
            ))}
          </div>
        </div>
        <div className="auth-side-quote">
          <p>"Your car knows more about its health than any mechanic's visual inspection. Cactus makes that data yours."</p>
          <div className="auth-side-quote-attr">— Acty Labs</div>
        </div>
      </div>
    </div>
  );
}

// ── Login ────────────────────────────────────────────────────────────────────
export function LoginPage() {
  const [form, setForm] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    await new Promise(r => setTimeout(r, 900)); // mock
    setLoading(false);
    navigate('/dashboard');
  };

  return (
    <div className="auth-layout">
      <SidePanel/>
      <div className="auth-form-panel">
        <motion.div className="auth-form-wrap" variants={FADE_UP} initial="hidden" animate="visible">
          <div className="auth-form-header">
            <h1 className="auth-form-title">Welcome back</h1>
            <p className="auth-form-sub">Sign in to your Cactus Insights account</p>
          </div>
          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label className="form-label">Email or Username</label>
              <input
                type="text" className="form-input"
                placeholder="you@example.com"
                value={form.email}
                onChange={e => setForm({...form, email: e.target.value})}
                required
              />
            </div>
            <div className="form-group">
              <div className="auth-label-row">
                <label className="form-label">Password</label>
                <a href="#forgot" className="auth-forgot">Forgot password?</a>
              </div>
              <input
                type="password" className="form-input"
                placeholder="••••••••"
                value={form.password}
                onChange={e => setForm({...form, password: e.target.value})}
                required
              />
            </div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={loading}>
              {loading ? <span className="auth-spinner"/> : 'Sign In'}
            </button>
          </form>
          <div className="divider">or</div>
          <div className="auth-providers">
            {['Google', 'GitHub'].map(p => (
              <button key={p} className="auth-provider-btn">
                <span>{p === 'Google' ? '🔵' : '⚫'}</span> Continue with {p}
              </button>
            ))}
          </div>
          <p className="auth-switch">
            Don't have an account? <Link to="/register">Create one free</Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}

// ── Register ─────────────────────────────────────────────────────────────────
export function RegisterPage() {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    username: '', email: '', password: '', region: '', vehicleMake: '', vehicleModel: '', vehicleDrivetrain: '',
  });
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleNext = (e) => {
    e.preventDefault();
    if (step < 3) setStep(step + 1);
    else handleSubmit();
  };

  const handleSubmit = async () => {
    setLoading(true);
    await new Promise(r => setTimeout(r, 900));
    setLoading(false);
    navigate('/dashboard');
  };

  const REGIONS = ['North America', 'Europe', 'Asia Pacific', 'Latin America', 'Middle East & Africa'];
  const MAKES = ['Toyota', 'Honda', 'Ford', 'Chevrolet', 'BMW', 'Mercedes', 'Audi', 'Volkswagen', 'Subaru', 'Mazda', 'Nissan', 'Hyundai'];
  const DRIVETRAINS = ['FWD', 'RWD', 'AWD', '4WD'];

  return (
    <div className="auth-layout">
      <SidePanel/>
      <div className="auth-form-panel">
        <motion.div className="auth-form-wrap" variants={FADE_UP} initial="hidden" animate="visible">
          <div className="auth-form-header">
            <div className="auth-steps">
              {[1,2,3].map(s => (
                <div key={s} className={`auth-step ${step >= s ? 'active' : ''} ${step > s ? 'done' : ''}`}>
                  <div className="auth-step-dot">{step > s ? '✓' : s}</div>
                  <div className="auth-step-label">{['Account', 'Region', 'Vehicle'][s-1]}</div>
                </div>
              ))}
            </div>
            <h1 className="auth-form-title" style={{ marginTop: '1.5rem' }}>
              {step === 1 ? 'Create your account' : step === 2 ? 'Your region' : 'Your vehicle'}
            </h1>
            <p className="auth-form-sub">
              {step === 1 ? 'Free forever. No credit card.' : step === 2 ? 'Used for anonymized fleet analytics only.' : 'You can add more vehicles later.'}
            </p>
          </div>

          <form onSubmit={handleNext} className="auth-form">
            {step === 1 && (
              <>
                <div className="form-group">
                  <label className="form-label">Username</label>
                  <input type="text" className="form-input" placeholder="johndoe" value={form.username}
                    onChange={e => setForm({...form, username: e.target.value})} required/>
                </div>
                <div className="form-group">
                  <label className="form-label">Email</label>
                  <input type="email" className="form-input" placeholder="you@example.com" value={form.email}
                    onChange={e => setForm({...form, email: e.target.value})} required/>
                </div>
                <div className="form-group">
                  <label className="form-label">Password</label>
                  <input type="password" className="form-input" placeholder="At least 8 characters" value={form.password}
                    onChange={e => setForm({...form, password: e.target.value})} required minLength={8}/>
                </div>
              </>
            )}
            {step === 2 && (
              <div className="form-group">
                <label className="form-label">Region</label>
                <div className="auth-region-grid">
                  {REGIONS.map(r => (
                    <button type="button" key={r}
                      className={`auth-region-btn ${form.region === r ? 'selected' : ''}`}
                      onClick={() => setForm({...form, region: r})}
                    >{r}</button>
                  ))}
                </div>
              </div>
            )}
            {step === 3 && (
              <>
                <div className="form-group">
                  <label className="form-label">Make</label>
                  <select className="form-input" value={form.vehicleMake}
                    onChange={e => setForm({...form, vehicleMake: e.target.value})} required>
                    <option value="">Select make…</option>
                    {MAKES.map(m => <option key={m}>{m}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Model</label>
                  <input type="text" className="form-input" placeholder="e.g. GR86, RAV4, F-150"
                    value={form.vehicleModel} onChange={e => setForm({...form, vehicleModel: e.target.value})} required/>
                </div>
                <div className="form-group">
                  <label className="form-label">Drivetrain</label>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {DRIVETRAINS.map(d => (
                      <button type="button" key={d}
                        className={`auth-drivetrain-btn ${form.vehicleDrivetrain === d ? 'selected' : ''}`}
                        onClick={() => setForm({...form, vehicleDrivetrain: d})}
                      >{d}</button>
                    ))}
                  </div>
                </div>
              </>
            )}

            <div className="auth-form-actions">
              {step > 1 && (
                <button type="button" className="btn btn-ghost" onClick={() => setStep(step - 1)}>Back</button>
              )}
              <button type="submit" className="btn btn-primary" style={{ flex: 1 }} disabled={loading || (step === 2 && !form.region)}>
                {loading ? <span className="auth-spinner"/> : step < 3 ? 'Continue' : 'Create Account'}
              </button>
            </div>
          </form>

          {step === 1 && (
            <p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p>
          )}
        </motion.div>
      </div>
    </div>
  );
}
