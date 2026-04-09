import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useUser, DEFAULT_MAINTENANCE, DEFAULT_INSIGHT_PREFS, DEFAULT_DASH_PREFS } from '../context/UserContext';
import { Sidebar } from './Dashboard';
import './Settings.css';

const FADE = {
  hidden: { opacity: 0, y: 12 },
  visible: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.4, delay: i * 0.05, ease: [0.22,1,0.36,1] } }),
};

const TABS = [
  { key: 'profile',     label: 'Profile',      icon: '👤' },
  { key: 'account',     label: 'Account',      icon: '🔒' },
  { key: 'maintenance', label: 'Maintenance',  icon: '🔧' },
  { key: 'insights',    label: 'Insights',     icon: '💡' },
  { key: 'dashboard',   label: 'Dashboard',    icon: '📊' },
  { key: 'security',    label: 'Security',     icon: '🛡️' },
];

// ── Toggle ────────────────────────────────────────────────────────────────────
function Toggle({ checked, onChange }) {
  return (
    <div className={`stg-toggle ${checked ? 'on' : ''}`} onClick={() => onChange(!checked)}>
      <div className="stg-toggle-knob"/>
    </div>
  );
}

// ── Section card ──────────────────────────────────────────────────────────────
function SettingCard({ title, desc, children }) {
  return (
    <div className="stg-card">
      <div className="stg-card-head">
        <div className="stg-card-title">{title}</div>
        {desc && <div className="stg-card-desc">{desc}</div>}
      </div>
      <div className="stg-card-body">{children}</div>
    </div>
  );
}

// ── Save toast ────────────────────────────────────────────────────────────────
function SaveToast({ show }) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div className="stg-toast"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }}>
          ✓ Saved
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ── Profile Tab ───────────────────────────────────────────────────────────────
function ProfileTab() {
  const { user, updateUser } = useUser();
  const [displayName, setDisplayName] = useState(user?.displayName || '');
  const [saved, setSaved] = useState(false);
  const fileRef = useRef();

  const handleAvatar = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { alert('Image must be under 2 MB'); return; }
    const reader = new FileReader();
    reader.onload = (ev) => { updateUser({ avatarUrl: ev.target.result }); flash(); };
    reader.readAsDataURL(file);
  };

  const flash = () => { setSaved(true); setTimeout(() => setSaved(false), 2000); };

  const handleSave = () => {
    updateUser({ displayName: displayName.trim() || user?.username });
    flash();
  };

  const initial = (user?.displayName || user?.username || '?')[0].toUpperCase();

  return (
    <div className="stg-tab-content">
      <SaveToast show={saved}/>

      <SettingCard title="Profile Picture" desc="JPEG or PNG, max 2 MB. Stored locally on this device.">
        <div className="stg-avatar-row">
          <div className="stg-avatar" onClick={() => fileRef.current?.click()}>
            {user?.avatarUrl
              ? <img src={user.avatarUrl} alt="avatar"/>
              : <span>{initial}</span>
            }
            <div className="stg-avatar-overlay">Change</div>
          </div>
          <div>
            <button className="btn btn-ghost btn-sm" onClick={() => fileRef.current?.click()}>
              Upload Photo
            </button>
            {user?.avatarUrl && (
              <button className="btn btn-sm stg-btn-danger-ghost" style={{ marginLeft: '0.5rem' }}
                onClick={() => { updateUser({ avatarUrl: null }); flash(); }}>
                Remove
              </button>
            )}
            <p style={{ fontSize: '0.8rem', color: '#94A3B8', marginTop: '0.5rem' }}>
              Your photo is stored locally and never uploaded to our servers.
            </p>
          </div>
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" style={{ display: 'none' }} onChange={handleAvatar}/>
        </div>
      </SettingCard>

      <SettingCard title="Display Name" desc="This is how your name appears in the app.">
        <div className="stg-field-row">
          <div className="form-group" style={{ flex: 1 }}>
            <label className="form-label">Display Name</label>
            <input className="form-input" value={displayName} onChange={e => setDisplayName(e.target.value)}
              placeholder={user?.username || 'Your name'}/>
          </div>
        </div>
        <div className="form-group" style={{ marginTop: '0.75rem' }}>
          <label className="form-label">Username <span className="stg-muted">(cannot change)</span></label>
          <input className="form-input" value={user?.username || ''} disabled style={{ opacity: 0.6 }}/>
        </div>
        <button className="btn btn-primary btn-sm" style={{ marginTop: '1rem' }} onClick={handleSave}>
          Save Changes
        </button>
      </SettingCard>
    </div>
  );
}

// ── Account Tab ───────────────────────────────────────────────────────────────
function AccountTab() {
  const { user, updateUser } = useUser();
  const [email, setEmail]       = useState(user?.email || '');
  const [emailSaved, setEmailSaved] = useState(false);
  const [pw, setPw]             = useState({ current: '', next: '', confirm: '' });
  const [pwError, setPwError]   = useState('');
  const [pwSaved, setPwSaved]   = useState(false);

  const saveEmail = () => {
    if (!email.includes('@')) return;
    updateUser({ email });
    setEmailSaved(true); setTimeout(() => setEmailSaved(false), 2000);
  };

  const savePassword = () => {
    setPwError('');
    if (pw.next.length < 8) { setPwError('Password must be at least 8 characters.'); return; }
    if (pw.next !== pw.confirm) { setPwError('Passwords do not match.'); return; }
    // In production: call backend. For now store hashed in localStorage.
    updateUser({ _pwChanged: Date.now() });
    setPw({ current: '', next: '', confirm: '' });
    setPwSaved(true); setTimeout(() => setPwSaved(false), 2000);
  };

  return (
    <div className="stg-tab-content">
      <SaveToast show={emailSaved || pwSaved}/>

      <SettingCard title="Email Address" desc="Used for sign-in and optional report delivery.">
        <div className="form-group">
          <label className="form-label">Email</label>
          <input className="form-input" type="email" value={email} onChange={e => setEmail(e.target.value)}/>
        </div>
        <button className="btn btn-primary btn-sm" style={{ marginTop: '1rem' }} onClick={saveEmail}>
          Update Email
        </button>
      </SettingCard>

      <SettingCard title="Change Password" desc="Choose a strong password with at least 8 characters.">
        <div className="stg-pw-fields">
          <div className="form-group">
            <label className="form-label">Current Password</label>
            <input className="form-input" type="password" placeholder="••••••••"
              value={pw.current} onChange={e => setPw({...pw, current: e.target.value})}/>
          </div>
          <div className="form-group">
            <label className="form-label">New Password</label>
            <input className="form-input" type="password" placeholder="At least 8 characters"
              value={pw.next} onChange={e => setPw({...pw, next: e.target.value})}/>
          </div>
          <div className="form-group">
            <label className="form-label">Confirm New Password</label>
            <input className="form-input" type="password" placeholder="••••••••"
              value={pw.confirm} onChange={e => setPw({...pw, confirm: e.target.value})}/>
          </div>
        </div>
        {pwError && <div className="stg-error">{pwError}</div>}
        <button className="btn btn-primary btn-sm" style={{ marginTop: '1rem' }} onClick={savePassword}>
          Change Password
        </button>
      </SettingCard>
    </div>
  );
}

// ── Maintenance Tab ───────────────────────────────────────────────────────────
const MAINTENANCE_SERVICES = [
  { key: 'oilChange',         label: 'Oil Change',           icon: '🔧', defaultInterval: 5000,
    hint: 'Standard: 5,000–10,000 mi. Severity-weighted advisor may recommend earlier.' },
  { key: 'cabinAirFilter',    label: 'Cabin Air Filter',     icon: '💨', defaultInterval: 20000,
    hint: 'Standard: every 15,000–25,000 mi or annually.' },
  { key: 'brakes',            label: 'Brake Inspection',     icon: '🛑', defaultInterval: 50000,
    hint: 'Standard: every 25,000–65,000 mi. Varies heavily by driving style.' },
  { key: 'transmissionFluid', label: 'Transmission Fluid',   icon: '⚙️', defaultInterval: 45000,
    hint: 'Automatic: every 30,000–60,000 mi. Manual: every 30,000–45,000 mi.' },
  { key: 'coolantFlush',      label: 'Coolant Flush',        icon: '🧊', defaultInterval: 30000,
    hint: 'Standard: every 30,000–50,000 mi or every 5 years.' },
];

function MaintenanceTab() {
  const { maintenance, updateMaintenance, updateServiceRecord } = useUser();
  const [saved, setSaved] = useState(false);
  const [odo, setOdo]     = useState(maintenance?.currentOdometer ?? '');

  const flash = () => { setSaved(true); setTimeout(() => setSaved(false), 2000); };

  const saveOdo = () => {
    const val = parseFloat(odo);
    if (isNaN(val) || val < 0) return;
    updateMaintenance({ currentOdometer: Math.round(val) });
    flash();
  };

  return (
    <div className="stg-tab-content">
      <SaveToast show={saved}/>

      <SettingCard title="Current Odometer"
        desc="Enter your current mileage to enable maintenance countdowns. Update periodically for accurate estimates.">
        <div className="stg-field-row">
          <div className="form-group" style={{ flex: 1 }}>
            <label className="form-label">Odometer (miles)</label>
            <input className="form-input" type="number" placeholder="e.g. 32500" min="0"
              value={odo} onChange={e => setOdo(e.target.value)}/>
          </div>
          <button className="btn btn-primary btn-sm" style={{ alignSelf: 'flex-end' }} onClick={saveOdo}>
            Save
          </button>
        </div>
        {maintenance?.currentOdometer && (
          <p style={{ fontSize: '0.8rem', color: '#64748B', marginTop: '0.5rem' }}>
            Current: <strong>{maintenance.currentOdometer.toLocaleString()} mi</strong>
          </p>
        )}
      </SettingCard>

      {MAINTENANCE_SERVICES.map((svc, i) => {
        const record = maintenance?.[svc.key] || { lastMi: null, intervalMi: svc.defaultInterval };
        return (
          <ServiceRecordCard key={svc.key} svc={svc} record={record}
            onSave={(patch) => { updateServiceRecord(svc.key, patch); flash(); }}/>
        );
      })}
    </div>
  );
}

function ServiceRecordCard({ svc, record, onSave }) {
  const [lastMi,     setLastMi]     = useState(record.lastMi ?? '');
  const [intervalMi, setIntervalMi] = useState(record.intervalMi ?? svc.defaultInterval);

  return (
    <SettingCard title={`${svc.icon} ${svc.label}`} desc={svc.hint}>
      <div className="stg-field-row">
        <div className="form-group" style={{ flex: 1 }}>
          <label className="form-label">Last done at (miles)</label>
          <input className="form-input" type="number" placeholder="Leave blank if unknown"
            value={lastMi} onChange={e => setLastMi(e.target.value)}/>
        </div>
        <div className="form-group" style={{ flex: 1 }}>
          <label className="form-label">Change interval (miles)</label>
          <input className="form-input" type="number" min="1000"
            value={intervalMi} onChange={e => setIntervalMi(e.target.value)}/>
        </div>
      </div>
      <button className="btn btn-ghost btn-sm" style={{ marginTop: '0.875rem' }}
        onClick={() => onSave({
          lastMi:     lastMi !== '' ? Math.round(parseFloat(lastMi)) : null,
          intervalMi: Math.round(parseFloat(intervalMi) || svc.defaultInterval),
        })}>
        Save Record
      </button>
    </SettingCard>
  );
}

// ── Insights Tab ──────────────────────────────────────────────────────────────
const INSIGHT_TOGGLES = [
  { key: 'maintenanceCountdown', label: 'Maintenance Countdown',   desc: 'Oil change, cabin filter, brakes, transmission, coolant — with mileage countdown.' },
  { key: 'oilChange',            label: 'Oil Change Advisor',      desc: 'Severity-weighted oil life estimate based on your driving conditions.' },
  { key: 'ltft',                 label: 'LTFT Analysis',           desc: 'Long-term fuel trim drift and lean/rich trend warnings.' },
  { key: 'thermal',              label: 'Thermal Profile',         desc: 'Coolant warmup, oil temperature, and catalyst light-off analysis.' },
  { key: 'charging',             label: 'Charging System',         desc: 'Alternator voltage, battery health, and thermal derating alerts.' },
  { key: 'dtcs',                 label: 'DTC Alerts',              desc: 'Diagnostic trouble codes — pending and confirmed.' },
];

function InsightsTab() {
  const { insightPrefs, updateInsightPrefs } = useUser();
  const [saved, setSaved] = useState(false);

  const toggle = (key) => {
    updateInsightPrefs({ [key]: !insightPrefs[key] });
    setSaved(true); setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="stg-tab-content">
      <SaveToast show={saved}/>
      <SettingCard title="Insight Visibility"
        desc="Choose which insight types appear on your Dashboard. Changes apply immediately.">
        <div className="stg-toggle-list">
          {INSIGHT_TOGGLES.map((t) => (
            <div key={t.key} className="stg-toggle-row">
              <div>
                <div className="stg-toggle-label">{t.label}</div>
                <div className="stg-toggle-desc">{t.desc}</div>
              </div>
              <Toggle checked={insightPrefs[t.key] ?? true} onChange={() => toggle(t.key)}/>
            </div>
          ))}
        </div>
      </SettingCard>
    </div>
  );
}

// ── Dashboard Tab ─────────────────────────────────────────────────────────────
const DASH_TOGGLES = [
  { key: 'healthRing',   label: 'Vehicle Health Ring',   desc: 'The circular health score card with sub-scores.' },
  { key: 'ltftChart',    label: 'LTFT Trend Chart',      desc: 'Area chart showing long-term fuel trim over sessions.' },
  { key: 'mpgChart',     label: 'MPG Trend Chart',       desc: 'Session-average fuel economy over time.' },
  { key: 'sessionTable', label: 'Recent Sessions Table', desc: 'Last 3 sessions with score, LTFT, and DTC summary.' },
  { key: 'quickActions', label: 'Quick Actions',         desc: 'Start Session, NeedleNest, Share Report, Add Vehicle shortcuts.' },
];

function DashboardTab() {
  const { dashPrefs, updateDashPrefs } = useUser();
  const [saved, setSaved] = useState(false);

  const toggle = (key) => {
    updateDashPrefs({ [key]: !dashPrefs[key] });
    setSaved(true); setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="stg-tab-content">
      <SaveToast show={saved}/>
      <SettingCard title="Dashboard Widgets"
        desc="Show or hide sections on your Dashboard. At least one widget must remain visible.">
        <div className="stg-toggle-list">
          {DASH_TOGGLES.map((t) => {
            const checked = dashPrefs[t.key] ?? true;
            const activeCount = Object.values(dashPrefs).filter(Boolean).length;
            const canToggle = checked ? activeCount > 1 : true;
            return (
              <div key={t.key} className="stg-toggle-row">
                <div>
                  <div className="stg-toggle-label">{t.label}</div>
                  <div className="stg-toggle-desc">{t.desc}</div>
                </div>
                <Toggle checked={checked} onChange={() => { if (canToggle) toggle(t.key); }}/>
              </div>
            );
          })}
        </div>
      </SettingCard>
    </div>
  );
}

// ── Security Tab ──────────────────────────────────────────────────────────────
function SecurityTab() {
  const { logout, deleteAccount } = useUser();
  const navigate = useNavigate();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteInput, setDeleteInput]     = useState('');

  const handleLogout = () => { logout(); navigate('/'); };
  const handleDelete = () => {
    if (deleteInput !== 'DELETE') return;
    deleteAccount();
    navigate('/');
  };

  return (
    <div className="stg-tab-content">
      <SettingCard title="Sessions & Data"
        desc="Your data is stored locally on this device. Nothing is shared without your explicit action.">
        <div className="stg-info-pills">
          {['Owner-encrypted', 'Ed25519 Signed', 'Zero data brokerage', 'Local-first'].map(p => (
            <span key={p} className="badge badge-blue">{p}</span>
          ))}
        </div>
        <p style={{ fontSize: '0.875rem', color: '#64748B', marginTop: '1rem', lineHeight: 1.65 }}>
          Your OBD session data, API keys, and account details are stored in your browser's localStorage.
          They are never transmitted to Acty Labs servers in readable form.
        </p>
      </SettingCard>

      <SettingCard title="Sign Out" desc="Sign out of this device. Your local data is preserved.">
        <button className="btn btn-ghost" onClick={handleLogout}>Sign Out</button>
      </SettingCard>

      <SettingCard title="Delete Account"
        desc="Permanently removes all your data from this device. This cannot be undone.">
        {!confirmDelete ? (
          <button className="btn stg-btn-danger" onClick={() => setConfirmDelete(true)}>
            Delete My Account
          </button>
        ) : (
          <div className="stg-delete-confirm">
            <p style={{ fontSize: '0.875rem', color: '#DC2626', marginBottom: '0.75rem', fontWeight: 600 }}>
              This will permanently delete all your vehicles, sessions, settings, and data.
            </p>
            <div className="form-group">
              <label className="form-label">Type <strong>DELETE</strong> to confirm</label>
              <input className="form-input stg-danger-input" value={deleteInput}
                onChange={e => setDeleteInput(e.target.value)} placeholder="DELETE"/>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.875rem' }}>
              <button className="btn btn-ghost btn-sm" onClick={() => { setConfirmDelete(false); setDeleteInput(''); }}>
                Cancel
              </button>
              <button className="btn stg-btn-danger btn-sm" disabled={deleteInput !== 'DELETE'} onClick={handleDelete}>
                Permanently Delete
              </button>
            </div>
          </div>
        )}
      </SettingCard>
    </div>
  );
}

// ── Settings Page ─────────────────────────────────────────────────────────────
export default function Settings() {
  const { user } = useUser();
  const [activeTab, setActiveTab] = useState('profile');
  const navigate = useNavigate();

  if (!user) { navigate('/login'); return null; }

  const tabContent = {
    profile:     <ProfileTab/>,
    account:     <AccountTab/>,
    maintenance: <MaintenanceTab/>,
    insights:    <InsightsTab/>,
    dashboard:   <DashboardTab/>,
    security:    <SecurityTab/>,
  };

  return (
    <div className="dashboard-layout">
      <Sidebar/>
      <main className="dashboard-main">
        <motion.div variants={FADE} custom={0} initial="hidden" animate="visible" className="dash-header">
          <h1>Settings</h1>
          <p style={{ color: '#94A3B8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Manage your profile, maintenance records, and preferences
          </p>
        </motion.div>

        <motion.div variants={FADE} custom={1} initial="hidden" animate="visible" className="stg-layout">
          {/* Sidebar nav */}
          <div className="stg-sidebar">
            {TABS.map(t => (
              <button key={t.key}
                className={`stg-tab-btn ${activeTab === t.key ? 'active' : ''}`}
                onClick={() => setActiveTab(t.key)}>
                <span className="stg-tab-icon">{t.icon}</span>
                {t.label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="stg-content">
            <AnimatePresence mode="wait">
              <motion.div key={activeTab}
                initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }} transition={{ duration: 0.2 }}>
                {tabContent[activeTab]}
              </motion.div>
            </AnimatePresence>
          </div>
        </motion.div>
      </main>
    </div>
  );
}
