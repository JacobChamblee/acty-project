import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { UserProvider, useUser } from './context/UserContext';
import './App.css';

// Pages
import Landing from './pages/Landing';
import { LoginPage, RegisterPage } from './pages/Auth';
import Dashboard from './pages/Dashboard';
import NeedleNest from './pages/NeedleNest';
import About from './pages/About';
import Vehicles from './pages/Vehicles';
import Settings from './pages/Settings';

// ── OAuth Callback ────────────────────────────────────────────────────────────
// Supabase redirects here after Google/Facebook OAuth.
// The Supabase SDK detects the session token in the URL automatically;
// onAuthStateChange in UserContext picks it up and sets the user.
function AuthCallbackPage() {
  const navigate = useNavigate();
  const { user } = useUser();

  // Navigate to dashboard once the session is established
  useEffect(() => {
    if (user) navigate('/dashboard', { replace: true });
  }, [user, navigate]);

  // Handle error query params from Supabase (e.g. invalid link)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const err = params.get('error_description') || params.get('error');
    if (err) navigate(`/login?error=${encodeURIComponent(err)}`, { replace: true });
  }, [navigate]);

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0F1117' }}>
      <div style={{ color: '#94A3B8', fontSize: '1rem' }}>Signing you in…</div>
    </div>
  );
}

// ── Shared Navbar ─────────────────────────────────────────────────────────────
function Navbar() {
  const loc = useLocation();
  const navigate = useNavigate();
  const { user, activeVehicle, logout } = useUser();
  const [menuOpen, setMenuOpen] = React.useState(false);
  const isDash = ['/dashboard', '/needlenest', '/vehicles', '/sharing', '/settings'].some(p => loc.pathname.startsWith(p));
  const isAuth = loc.pathname === '/login' || loc.pathname === '/register';
  if (isAuth) return null;

  const vehicleLabel = activeVehicle
    ? [activeVehicle.year, activeVehicle.make, activeVehicle.model].filter(Boolean).join(' ')
    : 'No vehicle';
  const displayName = user?.displayName || user?.username || '?';
  const initial = displayName[0].toUpperCase();

  const handleLogout = () => { setMenuOpen(false); logout(); navigate('/'); };

  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">
        <div className="nav-brand-icon">🌵</div>
        <span>Cactus Insights</span>
      </Link>
      {!isDash ? (
        <div className="nav-links">
          <a href="/#features">Features</a>
          <a href="/#how-it-works">How It Works</a>
          <a href="/#privacy">Privacy</a>
          <Link to="/about">About</Link>
        </div>
      ) : (
        <div className="nav-links">
          <Link to="/dashboard" className={loc.pathname === '/dashboard' ? 'active' : ''}>Dashboard</Link>
          <Link to="/needlenest" className={loc.pathname === '/needlenest' ? 'active' : ''}>NeedleNest</Link>
          <Link to="/vehicles" className={loc.pathname === '/vehicles' ? 'active' : ''}>Vehicles</Link>
          <Link to="/about">About</Link>
        </div>
      )}
      <div className="nav-actions">
        {isDash && user ? (
          <>
            <Link to="/vehicles" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.375rem 0.75rem', background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '8px', textDecoration: 'none' }}>
              <span style={{ fontSize: '14px' }}>🚗</span>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#475569' }}>{vehicleLabel}</span>
            </Link>
            {/* Avatar with dropdown */}
            <div style={{ position: 'relative' }}>
              <div onClick={() => setMenuOpen(o => !o)} style={{ width: 34, height: 34, borderRadius: '50%', overflow: 'hidden', background: 'linear-gradient(135deg, #1E40AF, #3B82F6)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 700, fontSize: '0.875rem', cursor: 'pointer', border: menuOpen ? '2px solid #3B82F6' : '2px solid transparent', transition: 'border 0.15s' }}>
                {user?.avatarUrl
                  ? <img src={user.avatarUrl} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }}/>
                  : initial}
              </div>
              {menuOpen && (
                <>
                  <div style={{ position: 'fixed', inset: 0, zIndex: 299 }} onClick={() => setMenuOpen(false)}/>
                  <div style={{ position: 'absolute', top: 'calc(100% + 8px)', right: 0, background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.12)', zIndex: 300, minWidth: 200, overflow: 'hidden' }}>
                    <div style={{ padding: '0.875rem 1rem', borderBottom: '1px solid #F1F5F9' }}>
                      <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#0F172A' }}>{displayName}</div>
                      <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>{user?.email}</div>
                    </div>
                    {[
                      { label: 'Settings', to: '/settings' },
                      { label: 'Vehicles', to: '/vehicles' },
                    ].map(item => (
                      <Link key={item.to} to={item.to} onClick={() => setMenuOpen(false)}
                        style={{ display: 'block', padding: '0.625rem 1rem', fontSize: '0.875rem', color: '#475569', fontWeight: 500, transition: 'background 0.15s', textDecoration: 'none' }}
                        onMouseEnter={e => e.target.style.background = '#F8FAFC'}
                        onMouseLeave={e => e.target.style.background = 'transparent'}>
                        {item.label}
                      </Link>
                    ))}
                    <div style={{ borderTop: '1px solid #F1F5F9' }}>
                      <button onClick={handleLogout} style={{ display: 'block', width: '100%', padding: '0.625rem 1rem', fontSize: '0.875rem', color: '#EF4444', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', transition: 'background 0.15s' }}
                        onMouseEnter={e => e.target.style.background = '#FEF2F2'}
                        onMouseLeave={e => e.target.style.background = 'transparent'}>
                        Sign Out
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </>
        ) : !isDash ? (
          <>
            <Link to="/login" className="btn btn-ghost btn-sm">Sign In</Link>
            <Link to="/register" className="btn btn-primary btn-sm">Get Started</Link>
          </>
        ) : null}
      </div>
    </nav>
  );
}

// ── Shared Footer ─────────────────────────────────────────────────────────────
function Footer() {
  const loc = useLocation();
  const hide = ['/dashboard', '/needlenest', '/vehicles', '/sharing', '/settings', '/login', '/register'].some(p => loc.pathname.startsWith(p));
  if (hide) return null;
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-grid">
          <div className="footer-brand">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.75rem' }}>
              <div className="nav-brand-icon" style={{ width: 32, height: 32, fontSize: 16, borderRadius: 8 }}>🌵</div>
              <span style={{ color: '#F1F5F9', fontWeight: 800, fontSize: '1rem' }}>Cactus Insights</span>
            </div>
            <p>Privacy-first OBD-II vehicle telemetry. Owner-encrypted data. Tamper-evident signed reports. AI diagnostics without selling a byte.</p>
            <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {['Ed25519 Signed', 'RFC 3161', 'Zero Data Brokerage'].map(t => (
                <span key={t} className="badge" style={{ background: 'rgba(255,255,255,0.06)', color: '#64748B', border: '1px solid #1E293B', fontSize: '0.7rem' }}>{t}</span>
              ))}
            </div>
          </div>
          <div className="footer-col">
            <h4>Product</h4>
            <a href="/#features">Features</a>
            <a href="/#how-it-works">How It Works</a>
            <Link to="/about">NeedleNest</Link>
            <Link to="/about">BYOK AI</Link>
          </div>
          <div className="footer-col">
            <h4>Company</h4>
            <Link to="/about">About</Link>
            <Link to="/about">Privacy Architecture</Link>
            <a href="https://github.com/JacobChamblee/acty-project" target="_blank" rel="noopener noreferrer">GitHub</a>
            <a href="https://acty-labs.com">Acty Labs</a>
          </div>
          <div className="footer-col">
            <h4>Developers</h4>
            <a href="#api">API Reference</a>
            <a href="#verify">Verify a Report</a>
            <a href="#fsm">FSM Ingestion</a>
            <a href="https://github.com/JacobChamblee/acty-project" target="_blank" rel="noopener noreferrer">Open Source</a>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} Acty Labs. All rights reserved.</span>
          <span style={{ color: '#334155' }}>Built for car people, by car people.</span>
        </div>
      </div>
    </footer>
  );
}

// ── Route-keyed page wrapper ──────────────────────────────────────────────────
function PageWrap({ children }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
      {children}
    </motion.div>
  );
}

// ── Routes ────────────────────────────────────────────────────────────────────
function AppRoutes() {
  const loc = useLocation();
  return (
    <>
      <Navbar/>
      <AnimatePresence mode="wait">
        <Routes location={loc} key={loc.pathname}>
          <Route path="/" element={<PageWrap><Landing/></PageWrap>}/>
          <Route path="/login" element={<PageWrap><LoginPage/></PageWrap>}/>
          <Route path="/register" element={<PageWrap><RegisterPage/></PageWrap>}/>
          <Route path="/about" element={<PageWrap><About/></PageWrap>}/>
          <Route path="/dashboard" element={<PageWrap><div className="page-content"><Dashboard/></div></PageWrap>}/>
          <Route path="/needlenest" element={<PageWrap><div className="page-content"><NeedleNest/></div></PageWrap>}/>
          <Route path="/vehicles" element={<PageWrap><div className="page-content"><Vehicles/></div></PageWrap>}/>
          <Route path="/sharing" element={<PageWrap><div className="page-content"><Dashboard/></div></PageWrap>}/>
          <Route path="/settings" element={<PageWrap><div className="page-content"><Settings/></div></PageWrap>}/>
          <Route path="/auth/callback" element={<AuthCallbackPage/>}/>
          <Route path="*" element={<PageWrap><Landing/></PageWrap>}/>
        </Routes>
      </AnimatePresence>
      <Footer/>
    </>
  );
}

export default function App() {
  return (
    <UserProvider>
      <div className="App">
        <BrowserRouter>
          <AppRoutes/>
        </BrowserRouter>
      </div>
    </UserProvider>
  );
}
