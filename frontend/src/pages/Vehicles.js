import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useUser } from '../context/UserContext';
import { Sidebar } from './Dashboard';
import './Vehicles.css';

const FADE = {
  hidden: { opacity: 0, y: 16 },
  visible: (i = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.45, delay: i * 0.07, ease: [0.22,1,0.36,1] } }),
};

const MAKES = ['Acura','Alfa Romeo','Audi','BMW','Buick','Cadillac','Chevrolet','Chrysler','Dodge','Ford','Genesis','GMC','Honda','Hyundai','Infiniti','Jeep','Kia','Lexus','Lincoln','Mazda','Mercedes-Benz','Mitsubishi','Nissan','Porsche','Ram','Subaru','Tesla','Toyota','Volkswagen','Volvo','Other'];
const DRIVETRAINS = ['FWD','RWD','AWD','4WD'];
const ADAPTER_TYPES = [
  { value: 'bluetooth', label: 'Bluetooth', icon: '📶' },
  { value: 'wifi', label: 'Wi-Fi', icon: '📡' },
  { value: 'usb', label: 'USB / Wired', icon: '🔌' },
];
const COMMON_ADAPTERS = [
  { name: 'OBDLink MX+', type: 'bluetooth', protocol: 'OBDLink' },
  { name: 'Veepeak OBDCheck BLE', type: 'bluetooth', protocol: 'ELM327' },
  { name: 'BAFX Products BT', type: 'bluetooth', protocol: 'ELM327' },
  { name: 'OBDLink EX', type: 'usb', protocol: 'OBDLink' },
  { name: 'Veepeak WiFi OBD2', type: 'wifi', protocol: 'ELM327' },
  { name: 'Other ELM327 device', type: 'bluetooth', protocol: 'ELM327' },
];

// ── Add Vehicle Modal ──────────────────────────────────────────────────────────
function AddVehicleModal({ onClose }) {
  const { addVehicle } = useUser();
  const [form, setForm] = useState({ year: '', make: '', model: '', trim: '', drivetrain: '' });
  const [saving, setSaving] = useState(false);

  const valid = form.year && form.make && form.model && form.drivetrain;

  const handleSave = async () => {
    if (!valid) return;
    setSaving(true);
    await new Promise(r => setTimeout(r, 400));
    addVehicle(form);
    setSaving(false);
    onClose();
  };

  return (
    <div className="veh-modal-backdrop" onClick={onClose}>
      <motion.div className="veh-modal" initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }} onClick={e => e.stopPropagation()}>
        <div className="veh-modal-header">
          <h2>Add Vehicle</h2>
          <button className="veh-modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="veh-modal-body">
          <div className="veh-form-row">
            <div className="form-group">
              <label className="form-label">Year *</label>
              <input type="number" className="form-input" placeholder="2024" min="1990" max="2026"
                value={form.year} onChange={e => setForm({...form, year: e.target.value})}/>
            </div>
            <div className="form-group">
              <label className="form-label">Make *</label>
              <select className="form-input" value={form.make} onChange={e => setForm({...form, make: e.target.value})}>
                <option value="">Select…</option>
                {MAKES.map(m => <option key={m}>{m}</option>)}
              </select>
            </div>
          </div>
          <div className="veh-form-row">
            <div className="form-group">
              <label className="form-label">Model *</label>
              <input type="text" className="form-input" placeholder="Camry, F-150, Model 3…"
                value={form.model} onChange={e => setForm({...form, model: e.target.value})}/>
            </div>
            <div className="form-group">
              <label className="form-label">Trim <span className="form-label-opt">(optional)</span></label>
              <input type="text" className="form-input" placeholder="XSE, Sport, Premium…"
                value={form.trim} onChange={e => setForm({...form, trim: e.target.value})}/>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Drivetrain *</label>
            <div className="veh-dt-grid">
              {DRIVETRAINS.map(d => (
                <button key={d} type="button"
                  className={`veh-dt-btn ${form.drivetrain === d ? 'selected' : ''}`}
                  onClick={() => setForm({...form, drivetrain: d})}>{d}</button>
              ))}
            </div>
          </div>
        </div>
        <div className="veh-modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={!valid || saving}>
            {saving ? 'Adding…' : 'Add Vehicle'}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Add Adapter Modal ──────────────────────────────────────────────────────────
function AddAdapterModal({ onClose }) {
  const { addAdapter } = useUser();
  const [mode, setMode] = useState('pick'); // 'pick' | 'custom'
  const [form, setForm] = useState({ name: '', type: 'bluetooth', protocol: 'ELM327', notes: '' });
  const [saving, setSaving] = useState(false);

  const handlePick = async (preset) => {
    setSaving(true);
    await new Promise(r => setTimeout(r, 400));
    addAdapter(preset);
    setSaving(false);
    onClose();
  };

  const handleCustomSave = async () => {
    if (!form.name) return;
    setSaving(true);
    await new Promise(r => setTimeout(r, 400));
    addAdapter(form);
    setSaving(false);
    onClose();
  };

  return (
    <div className="veh-modal-backdrop" onClick={onClose}>
      <motion.div className="veh-modal" initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }} onClick={e => e.stopPropagation()}>
        <div className="veh-modal-header">
          <h2>Add OBD-II Adapter</h2>
          <button className="veh-modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="veh-modal-body">
          {mode === 'pick' ? (
            <>
              <p style={{ fontSize: '0.875rem', color: '#64748B', marginBottom: '1rem' }}>
                Select your adapter from the list, or enter a custom device.
              </p>
              <div className="veh-adapter-list">
                {COMMON_ADAPTERS.map((a, i) => (
                  <button key={i} className="veh-adapter-row" onClick={() => handlePick(a)} disabled={saving}>
                    <span className="veh-adapter-icon">{ADAPTER_TYPES.find(t => t.value === a.type)?.icon}</span>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{a.name}</div>
                      <div style={{ fontSize: '0.775rem', color: '#94A3B8' }}>{a.type} · {a.protocol}</div>
                    </div>
                    <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: '#1E40AF', fontWeight: 600 }}>
                      {saving ? '…' : 'Add →'}
                    </span>
                  </button>
                ))}
              </div>
              <button className="btn btn-ghost btn-sm" style={{ width: '100%', marginTop: '0.75rem' }}
                onClick={() => setMode('custom')}>
                Enter custom device
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-ghost btn-sm" style={{ marginBottom: '1rem' }} onClick={() => setMode('pick')}>
                ← Back to list
              </button>
              <div className="form-group">
                <label className="form-label">Device Name *</label>
                <input type="text" className="form-input" placeholder="My OBD Adapter"
                  value={form.name} onChange={e => setForm({...form, name: e.target.value})}/>
              </div>
              <div className="veh-form-row">
                <div className="form-group">
                  <label className="form-label">Connection Type</label>
                  <select className="form-input" value={form.type} onChange={e => setForm({...form, type: e.target.value})}>
                    {ADAPTER_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Protocol</label>
                  <select className="form-input" value={form.protocol} onChange={e => setForm({...form, protocol: e.target.value})}>
                    <option>ELM327</option>
                    <option>OBDLink</option>
                    <option>STN11xx</option>
                    <option>Other</option>
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Notes <span className="form-label-opt">(optional)</span></label>
                <input type="text" className="form-input" placeholder="e.g. paired to 2024 GR86"
                  value={form.notes} onChange={e => setForm({...form, notes: e.target.value})}/>
              </div>
            </>
          )}
        </div>
        {mode === 'custom' && (
          <div className="veh-modal-footer">
            <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" onClick={handleCustomSave} disabled={!form.name || saving}>
              {saving ? 'Adding…' : 'Add Adapter'}
            </button>
          </div>
        )}
      </motion.div>
    </div>
  );
}

// ── Vehicles Page ──────────────────────────────────────────────────────────────
export default function Vehicles() {
  const { user, activeVehicle, setActiveVehicle, removeVehicle, removeAdapter } = useUser();
  const [showAddVehicle, setShowAddVehicle] = useState(false);
  const [showAddAdapter, setShowAddAdapter] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null); // { type: 'vehicle'|'adapter', id }

  const vehicles = user?.vehicles || [];
  const adapters = user?.obdAdapters || [];

  return (
    <div className="dashboard-layout">
      <Sidebar/>
      <main className="dashboard-main">
        <motion.div variants={FADE} custom={0} initial="hidden" animate="visible" className="dash-header">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h1>Vehicles & Adapters</h1>
              <p style={{ color: '#94A3B8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
                Manage your vehicles and OBD-II Bluetooth devices
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button className="btn btn-ghost" onClick={() => setShowAddAdapter(true)}>
                + Add Adapter
              </button>
              <button className="btn btn-primary" onClick={() => setShowAddVehicle(true)}>
                + Add Vehicle
              </button>
            </div>
          </div>
        </motion.div>

        {/* Vehicles */}
        <motion.div variants={FADE} custom={1} initial="hidden" animate="visible">
          <div className="veh-section-header">
            <h2 className="veh-section-title">Your Vehicles</h2>
            <span className="badge badge-gray">{vehicles.length} vehicle{vehicles.length !== 1 ? 's' : ''}</span>
          </div>

          {vehicles.length === 0 ? (
            <div className="veh-empty-card">
              <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>🚗</div>
              <h3 style={{ marginBottom: '0.5rem' }}>No vehicles yet</h3>
              <p style={{ color: '#94A3B8', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                Add your first vehicle to start capturing OBD-II sessions.
              </p>
              <button className="btn btn-primary" onClick={() => setShowAddVehicle(true)}>
                + Add Vehicle
              </button>
            </div>
          ) : (
            <div className="veh-cards-grid">
              {vehicles.map((v, i) => {
                const isActive = v.id === user?.activeVehicleId || (vehicles.length === 1);
                const label = [v.year, v.make, v.model, v.trim].filter(Boolean).join(' ');
                return (
                  <motion.div key={v.id} custom={i} variants={FADE} initial="hidden" animate="visible"
                    className={`veh-card glass-card ${isActive ? 'active' : ''}`}>
                    <div className="veh-card-header">
                      <div className="veh-card-icon">🚗</div>
                      <div style={{ flex: 1 }}>
                        <div className="veh-card-name">{label}</div>
                        <div className="veh-card-meta">{v.drivetrain} · OBD-II</div>
                      </div>
                      {isActive && <span className="badge badge-blue">Active</span>}
                    </div>
                    <div className="veh-card-actions">
                      {!isActive && (
                        <button className="btn btn-ghost btn-sm" onClick={() => setActiveVehicle(v.id)}>
                          Set Active
                        </button>
                      )}
                      <button className="btn btn-ghost btn-sm veh-delete-btn"
                        onClick={() => setConfirmDelete({ type: 'vehicle', id: v.id, label })}>
                        Remove
                      </button>
                    </div>
                  </motion.div>
                );
              })}
              <button className="veh-add-card" onClick={() => setShowAddVehicle(true)}>
                <span style={{ fontSize: '1.5rem', marginBottom: '0.5rem', display: 'block' }}>+</span>
                <span>Add Vehicle</span>
              </button>
            </div>
          )}
        </motion.div>

        {/* OBD Adapters */}
        <motion.div variants={FADE} custom={2} initial="hidden" animate="visible" style={{ marginTop: '2.5rem' }}>
          <div className="veh-section-header">
            <h2 className="veh-section-title">OBD-II Adapters</h2>
            <span className="badge badge-gray">{adapters.length} device{adapters.length !== 1 ? 's' : ''}</span>
          </div>

          {adapters.length === 0 ? (
            <div className="veh-empty-card">
              <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>📶</div>
              <h3 style={{ marginBottom: '0.5rem' }}>No adapters paired</h3>
              <p style={{ color: '#94A3B8', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                Add your OBD-II Bluetooth or Wi-Fi dongle to enable live capture.
              </p>
              <button className="btn btn-primary" onClick={() => setShowAddAdapter(true)}>
                + Add Adapter
              </button>
            </div>
          ) : (
            <div className="veh-adapter-cards">
              {adapters.map((a, i) => {
                const typeInfo = ADAPTER_TYPES.find(t => t.value === a.type) || ADAPTER_TYPES[0];
                return (
                  <motion.div key={a.id} custom={i} variants={FADE} initial="hidden" animate="visible"
                    className="veh-adapter-card glass-card">
                    <div className="veh-adapter-card-icon">{typeInfo.icon}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: '0.9375rem', marginBottom: '0.2rem' }}>{a.name}</div>
                      <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>
                        {typeInfo.label} · {a.protocol}
                        {a.notes && ` · ${a.notes}`}
                      </div>
                    </div>
                    <button className="btn btn-ghost btn-sm veh-delete-btn"
                      onClick={() => setConfirmDelete({ type: 'adapter', id: a.id, label: a.name })}>
                      Remove
                    </button>
                  </motion.div>
                );
              })}
              <button className="veh-adapter-add-btn btn btn-ghost" onClick={() => setShowAddAdapter(true)}>
                + Add Adapter
              </button>
            </div>
          )}
        </motion.div>

        {/* Info box */}
        <motion.div variants={FADE} custom={3} initial="hidden" animate="visible"
          style={{ marginTop: '2rem', padding: '1.25rem 1.5rem', background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 12 }}>
          <p style={{ fontSize: '0.875rem', color: '#1E40AF', lineHeight: 1.65, margin: 0 }}>
            <strong>How to pair your adapter:</strong> Connect your OBD-II dongle to the port under your dashboard, then pair it to your phone via Bluetooth or Wi-Fi settings. Open the Cactus Android app, select your adapter here, and tap Start Session to begin live capture.
          </p>
        </motion.div>
      </main>

      {/* Modals */}
      <AnimatePresence>
        {showAddVehicle && <AddVehicleModal onClose={() => setShowAddVehicle(false)}/>}
        {showAddAdapter && <AddAdapterModal onClose={() => setShowAddAdapter(false)}/>}
        {confirmDelete && (
          <div className="veh-modal-backdrop" onClick={() => setConfirmDelete(null)}>
            <motion.div className="veh-modal veh-confirm-modal" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} onClick={e => e.stopPropagation()}>
              <div className="veh-modal-header">
                <h2>Remove {confirmDelete.type === 'vehicle' ? 'Vehicle' : 'Adapter'}?</h2>
              </div>
              <div className="veh-modal-body">
                <p style={{ color: '#475569' }}>
                  Remove <strong>{confirmDelete.label}</strong>? This cannot be undone.
                </p>
              </div>
              <div className="veh-modal-footer">
                <button className="btn btn-ghost" onClick={() => setConfirmDelete(null)}>Cancel</button>
                <button className="btn btn-danger" onClick={() => {
                  if (confirmDelete.type === 'vehicle') removeVehicle(confirmDelete.id);
                  else removeAdapter(confirmDelete.id);
                  setConfirmDelete(null);
                }}>Remove</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
