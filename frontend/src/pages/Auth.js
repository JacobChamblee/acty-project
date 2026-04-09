import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useUser } from '../context/UserContext';
import { authStore } from '../context/UserContext';
import './Auth.css';

// ── OAuth App IDs ─────────────────────────────────────────────────────────────
// Replace these with your real credentials before deploying.
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID || '';
const FB_APP_ID        = process.env.REACT_APP_FB_APP_ID        || '';

// ── Helpers ───────────────────────────────────────────────────────────────────
async function hashPw(password) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(password));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function decodeJwt(token) {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(payload));
  } catch { return null; }
}

function loadScript(src, id) {
  return new Promise((resolve, reject) => {
    if (document.getElementById(id)) { resolve(); return; }
    const s = document.createElement('script');
    s.id = id; s.src = src; s.async = true; s.defer = true;
    s.onload = resolve; s.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(s);
  });
}

const FADE_UP = {
  hidden:  { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] } },
};

// ── Side panel ────────────────────────────────────────────────────────────────
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

// ── Google SVG logo ───────────────────────────────────────────────────────────
function GoogleLogo() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
      <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34.1 6.8 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.9z"/>
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 16 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34.1 6.8 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.2 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8H6.4C9.7 35.8 16.3 44 24 44z"/>
      <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.3 4.1-4.2 5.4l6.2 5.2C37 38.2 44 33 44 24c0-1.3-.1-2.7-.4-3.9z"/>
    </svg>
  );
}

// ── Facebook SVG logo ─────────────────────────────────────────────────────────
function FacebookLogo() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path fill="#1877F2" d="M24 12.073C24 5.4 18.627 0 12 0S0 5.4 0 12.073C0 18.1 4.388 23.094 10.125 24v-8.437H7.078v-3.49h3.047V9.413c0-3.025 1.792-4.697 4.533-4.697 1.313 0 2.686.236 2.686.236v2.97h-1.513c-1.491 0-1.956.93-1.956 1.886v2.267h3.328l-.532 3.49h-2.796V24C19.612 23.094 24 18.1 24 12.073z"/>
    </svg>
  );
}

// ── Social sign-in shared handler ─────────────────────────────────────────────
function useSocialSignIn(setUser, navigate) {
  return useCallback(async ({ email, displayName, avatarUrl, provider }) => {
    const key = email.toLowerCase();
    let account = authStore.getAccount(key);
    if (!account) {
      account = {
        username:        displayName?.split(' ')[0] || key.split('@')[0],
        displayName,
        email:           key,
        region:          '',
        avatarUrl:       avatarUrl || null,
        provider,
        vehicles:        [],
        obdAdapters:     [],
        activeVehicleId: null,
      };
      authStore.createAccount(account);
    } else {
      // Update display name / avatar from provider if not overridden
      if (!account.displayName && displayName) authStore.updateAccount(key, { displayName, avatarUrl });
      authStore.setSession(key);
    }
    const fresh = authStore.getAccount(key);
    setUser(fresh);
    navigate('/dashboard');
  }, [setUser, navigate]);
}

// ── Login ─────────────────────────────────────────────────────────────────────
export function LoginPage() {
  const [form, setForm]       = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [gLoading, setGLoad]  = useState(false);
  const [fbLoading, setFbLoad]= useState(false);
  const [error, setError]     = useState('');
  const { setUser }           = useUser();
  const navigate              = useNavigate();
  const handleSocial          = useSocialSignIn(setUser, navigate);

  // ── Google One-Tap ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    loadScript('https://accounts.google.com/gsi/client', 'gsi-script').then(() => {
      window.google?.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (response) => {
          setGLoad(true);
          const payload = decodeJwt(response.credential);
          if (!payload?.email) { setError('Google sign-in failed.'); setGLoad(false); return; }
          await handleSocial({ email: payload.email, displayName: payload.name, avatarUrl: payload.picture, provider: 'google' });
          setGLoad(false);
        },
        auto_select: false,
      });
    }).catch(() => {});
  }, [handleSocial]);

  // ── Facebook SDK ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!FB_APP_ID) return;
    window.fbAsyncInit = () => {
      window.FB.init({ appId: FB_APP_ID, cookie: true, xfbml: false, version: 'v19.0' });
    };
    loadScript('https://connect.facebook.net/en_US/sdk.js', 'fb-sdk').catch(() => {});
  }, []);

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    await new Promise(r => setTimeout(r, 400));

    const account = authStore.getAccount(form.email);
    if (!account) {
      setError('No account found for that email. Please register first.');
      setLoading(false);
      return;
    }
    if (account.provider && !account._pwHash) {
      setError(`This account was created with ${account.provider}. Please use that sign-in method.`);
      setLoading(false);
      return;
    }
    const hash = await hashPw(form.password);
    if (hash !== account._pwHash) {
      setError('Incorrect password. Please try again.');
      setLoading(false);
      return;
    }
    authStore.setSession(form.email);
    setUser(account);
    setLoading(false);
    navigate('/dashboard');
  };

  const handleGoogleClick = () => {
    if (!GOOGLE_CLIENT_ID) { setError('Google sign-in is not configured.'); return; }
    setError('');
    window.google?.accounts.id.prompt();
  };

  const handleFacebookClick = () => {
    if (!FB_APP_ID) { setError('Facebook sign-in is not configured.'); return; }
    setError('');
    setFbLoad(true);
    window.FB?.login(async (res) => {
      if (res.authResponse) {
        window.FB.api('/me', { fields: 'name,email,picture.type(large)' }, async (data) => {
          if (!data.email) { setError('Facebook did not provide an email address.'); setFbLoad(false); return; }
          await handleSocial({ email: data.email, displayName: data.name, avatarUrl: data.picture?.data?.url, provider: 'facebook' });
          setFbLoad(false);
        });
      } else {
        setError('Facebook sign-in was cancelled.');
        setFbLoad(false);
      }
    }, { scope: 'email,public_profile' });
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

          <div className="auth-providers">
            <button className="auth-provider-btn auth-provider-google" onClick={handleGoogleClick} disabled={gLoading}>
              {gLoading ? <span className="auth-spinner auth-spinner-dark"/> : <GoogleLogo/>}
              Continue with Google
            </button>
            <button className="auth-provider-btn auth-provider-fb" onClick={handleFacebookClick} disabled={fbLoading}>
              {fbLoading ? <span className="auth-spinner"/> : <FacebookLogo/>}
              Continue with Facebook
            </button>
          </div>

          <div className="divider">or sign in with email</div>

          {error && <div className="auth-error">{error}</div>}
          <form onSubmit={handleEmailLogin} className="auth-form">
            <div className="form-group">
              <label className="form-label">Email</label>
              <input
                type="email" className="form-input"
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

          <p className="auth-switch">
            Don't have an account? <Link to="/register">Create one free</Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}

// ── Register ──────────────────────────────────────────────────────────────────
export function RegisterPage() {
  const [step, setStep]   = useState(1);
  const [form, setForm]   = useState({
    username: '', email: '', password: '', confirmPw: '', region: '',
    vehicleYear: '', vehicleMake: '', vehicleModel: '', vehicleTrim: '', vehicleDrivetrain: '',
  });
  const [loading, setLoading] = useState(false);
  const [gLoading, setGLoad]  = useState(false);
  const [fbLoading, setFbLoad]= useState(false);
  const [error, setError]     = useState('');
  const { setUser }           = useUser();
  const navigate              = useNavigate();
  const handleSocial          = useSocialSignIn(setUser, navigate);

  // ── Google ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    loadScript('https://accounts.google.com/gsi/client', 'gsi-script').then(() => {
      window.google?.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (response) => {
          setGLoad(true);
          const payload = decodeJwt(response.credential);
          if (!payload?.email) { setError('Google sign-in failed.'); setGLoad(false); return; }
          await handleSocial({ email: payload.email, displayName: payload.name, avatarUrl: payload.picture, provider: 'google' });
          setGLoad(false);
        },
        auto_select: false,
      });
    }).catch(() => {});
  }, [handleSocial]);

  // ── Facebook ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!FB_APP_ID) return;
    window.fbAsyncInit = () => {
      window.FB.init({ appId: FB_APP_ID, cookie: true, xfbml: false, version: 'v19.0' });
    };
    loadScript('https://connect.facebook.net/en_US/sdk.js', 'fb-sdk').catch(() => {});
  }, []);

  const handleGoogleClick = () => {
    if (!GOOGLE_CLIENT_ID) { setError('Google sign-in is not configured.'); return; }
    setError('');
    window.google?.accounts.id.prompt();
  };

  const handleFacebookClick = () => {
    if (!FB_APP_ID) { setError('Facebook sign-in is not configured.'); return; }
    setError('');
    setFbLoad(true);
    window.FB?.login(async (res) => {
      if (res.authResponse) {
        window.FB.api('/me', { fields: 'name,email,picture.type(large)' }, async (data) => {
          if (!data.email) { setError('Facebook did not provide an email address.'); setFbLoad(false); return; }
          await handleSocial({ email: data.email, displayName: data.name, avatarUrl: data.picture?.data?.url, provider: 'facebook' });
          setFbLoad(false);
        });
      } else {
        setError('Facebook sign-in was cancelled.');
        setFbLoad(false);
      }
    }, { scope: 'email,public_profile' });
  };

  const validateStep1 = () => {
    if (form.username.length < 2)  return 'Username must be at least 2 characters.';
    if (!form.email.includes('@'))  return 'Please enter a valid email.';
    if (form.password.length < 8)   return 'Password must be at least 8 characters.';
    if (form.password !== form.confirmPw) return 'Passwords do not match.';
    if (authStore.getAccount(form.email)) return 'An account with this email already exists.';
    return null;
  };

  const handleNext = async (e) => {
    e.preventDefault();
    setError('');
    if (step === 1) {
      const err = validateStep1();
      if (err) { setError(err); return; }
    }
    if (step < 3) { setStep(step + 1); return; }
    await handleSubmit(false);
  };

  const handleSubmit = async (skipVehicle = true) => {
    setLoading(true);
    const vehicles = (!skipVehicle && form.vehicleMake && form.vehicleModel) ? [{
      id:          `v${Date.now()}`,
      year:        form.vehicleYear,
      make:        form.vehicleMake,
      model:       form.vehicleModel,
      trim:        form.vehicleTrim,
      drivetrain:  form.vehicleDrivetrain,
    }] : [];

    const hash = await hashPw(form.password);
    const account = {
      username:        form.username,
      displayName:     form.username,
      email:           form.email.toLowerCase(),
      _pwHash:         hash,
      region:          form.region,
      vehicles,
      obdAdapters:     [],
      activeVehicleId: vehicles[0]?.id || null,
    };
    authStore.createAccount(account);
    setUser(authStore.getAccount(form.email));
    setLoading(false);
    navigate('/dashboard');
  };

  const REGIONS    = ['North America', 'Europe', 'Asia Pacific', 'Latin America', 'Middle East & Africa'];
  const MAKES      = ['Toyota', 'Honda', 'Ford', 'Chevrolet', 'BMW', 'Mercedes', 'Audi', 'Volkswagen', 'Subaru', 'Mazda', 'Nissan', 'Hyundai', 'Kia', 'Dodge', 'Jeep', 'Ram', 'GMC'];
  const DRIVETRAINS= ['FWD', 'RWD', 'AWD', '4WD'];

  return (
    <div className="auth-layout">
      <SidePanel/>
      <div className="auth-form-panel">
        <motion.div className="auth-form-wrap" variants={FADE_UP} initial="hidden" animate="visible">

          {/* Step indicators */}
          <div className="auth-steps">
            {[1,2,3].map(s => (
              <div key={s} className={`auth-step ${step >= s ? 'active' : ''} ${step > s ? 'done' : ''}`}>
                <div className="auth-step-dot">{step > s ? '✓' : s}</div>
                <div className="auth-step-label">{['Account', 'Region', 'Vehicle'][s-1]}</div>
              </div>
            ))}
          </div>

          <div className="auth-form-header" style={{ marginTop: '1.5rem' }}>
            <h1 className="auth-form-title">
              {step === 1 ? 'Create your account' : step === 2 ? 'Your region' : 'Your vehicle'}
            </h1>
            <p className="auth-form-sub">
              {step === 1 ? 'Free forever. No credit card.' : step === 2 ? 'Used for anonymized fleet analytics only.' : 'You can add more vehicles later.'}
            </p>
          </div>

          {/* Social sign-up — only on step 1 */}
          {step === 1 && (
            <>
              <div className="auth-providers">
                <button className="auth-provider-btn auth-provider-google" onClick={handleGoogleClick} disabled={gLoading}>
                  {gLoading ? <span className="auth-spinner auth-spinner-dark"/> : <GoogleLogo/>}
                  Continue with Google
                </button>
                <button className="auth-provider-btn auth-provider-fb" onClick={handleFacebookClick} disabled={fbLoading}>
                  {fbLoading ? <span className="auth-spinner"/> : <FacebookLogo/>}
                  Continue with Facebook
                </button>
              </div>
              <div className="divider">or create with email</div>
            </>
          )}

          {error && <div className="auth-error">{error}</div>}

          <form onSubmit={handleNext} className="auth-form">
            {/* ── Step 1: Account ── */}
            {step === 1 && (
              <>
                <div className="form-group">
                  <label className="form-label">Username</label>
                  <input type="text" className="form-input" placeholder="johndoe"
                    value={form.username} onChange={e => setForm({...form, username: e.target.value})} required minLength={2}/>
                </div>
                <div className="form-group">
                  <label className="form-label">Email</label>
                  <input type="email" className="form-input" placeholder="you@example.com"
                    value={form.email} onChange={e => setForm({...form, email: e.target.value})} required/>
                </div>
                <div className="form-group">
                  <label className="form-label">Password</label>
                  <input type="password" className="form-input" placeholder="At least 8 characters"
                    value={form.password} onChange={e => setForm({...form, password: e.target.value})} required minLength={8}/>
                </div>
                <div className="form-group">
                  <label className="form-label">Confirm Password</label>
                  <input type="password" className="form-input" placeholder="••••••••"
                    value={form.confirmPw} onChange={e => setForm({...form, confirmPw: e.target.value})} required/>
                </div>
              </>
            )}

            {/* ── Step 2: Region ── */}
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

            {/* ── Step 3: Vehicle ── */}
            {step === 3 && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">Year</label>
                    <input type="number" className="form-input" placeholder="2024"
                      min="1990" max="2026" value={form.vehicleYear}
                      onChange={e => setForm({...form, vehicleYear: e.target.value})}/>
                  </div>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">Make</label>
                    <select className="form-input" value={form.vehicleMake}
                      onChange={e => setForm({...form, vehicleMake: e.target.value})}>
                      <option value="">Select…</option>
                      {MAKES.map(m => <option key={m}>{m}</option>)}
                    </select>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">Model</label>
                    <input type="text" className="form-input" placeholder="Camry, RAV4…"
                      value={form.vehicleModel} onChange={e => setForm({...form, vehicleModel: e.target.value})}/>
                  </div>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">Trim <span style={{ color: '#94A3B8', fontWeight: 400 }}>(optional)</span></label>
                    <input type="text" className="form-input" placeholder="SE, XLE…"
                      value={form.vehicleTrim} onChange={e => setForm({...form, vehicleTrim: e.target.value})}/>
                  </div>
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
                <p style={{ fontSize: '0.8rem', color: '#94A3B8', marginTop: '-0.5rem' }}>
                  Vehicle fields are all optional — you can add them later.
                </p>
              </>
            )}

            <div className="auth-form-actions">
              {step > 1 && (
                <button type="button" className="btn btn-ghost" onClick={() => { setError(''); setStep(step - 1); }}>
                  Back
                </button>
              )}
              <button type="submit" className="btn btn-primary" style={{ flex: 1 }}
                disabled={loading || (step === 2 && !form.region)}>
                {loading ? <span className="auth-spinner"/> : step < 3 ? 'Continue' : 'Create Account'}
              </button>
            </div>

            {step === 3 && (
              <button type="button" className="btn btn-ghost btn-sm"
                style={{ width: '100%', marginTop: '0.25rem' }}
                onClick={() => handleSubmit(true)}
                disabled={loading}>
                Skip — add vehicle later
              </button>
            )}
          </form>

          {step === 1 && (
            <p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p>
          )}
        </motion.div>
      </div>
    </div>
  );
}
