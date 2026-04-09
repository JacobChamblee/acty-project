import React, { createContext, useContext, useState, useCallback } from 'react';

const UserContext = createContext(null);

// ── Default state shapes ──────────────────────────────────────────────────────

export const DEFAULT_MAINTENANCE = {
  currentOdometer:   null,   // miles (user enters this)
  // Each service: { lastMi: number|null, intervalMi: number }
  oilChange:         { lastMi: null, intervalMi: 5000 },
  cabinAirFilter:    { lastMi: null, intervalMi: 20000 },
  brakes:            { lastMi: null, intervalMi: 50000 },
  transmissionFluid: { lastMi: null, intervalMi: 45000 },
  coolantFlush:      { lastMi: null, intervalMi: 30000 },
};

export const DEFAULT_INSIGHT_PREFS = {
  maintenanceCountdown: true,
  oilChange:    true,
  ltft:         true,
  thermal:      true,
  charging:     true,
  dtcs:         true,
};

export const DEFAULT_DASH_PREFS = {
  healthRing:   true,
  ltftChart:    true,
  mpgChart:     true,
  sessionTable: true,
  quickActions: true,
};

// ── Persistence helpers ───────────────────────────────────────────────────────

function load() {
  try { const r = localStorage.getItem('cactus_user'); return r ? JSON.parse(r) : null; }
  catch { return null; }
}
function save(u) { localStorage.setItem('cactus_user', JSON.stringify(u)); }

// ── Maintenance calculation ───────────────────────────────────────────────────

const SERVICE_META = {
  oilChange:         { label: 'Oil Change',          icon: '🔧', urgentMi: 500  },
  cabinAirFilter:    { label: 'Cabin Air Filter',    icon: '💨', urgentMi: 1000 },
  brakes:            { label: 'Brake Inspection',    icon: '🛑', urgentMi: 2000 },
  transmissionFluid: { label: 'Transmission Fluid',  icon: '⚙️', urgentMi: 2000 },
  coolantFlush:      { label: 'Coolant Flush',       icon: '🧊', urgentMi: 2000 },
};

export function computeMaintenanceItems(maintenance) {
  const odo = maintenance?.currentOdometer;
  return Object.entries(SERVICE_META).map(([key, meta]) => {
    const svc = maintenance?.[key] || DEFAULT_MAINTENANCE[key];
    let miRemaining = null;
    let pctUsed = null;
    let status = 'unknown'; // unknown | ok | watch | due_soon | overdue

    if (odo != null && svc.lastMi != null) {
      const miSince = odo - svc.lastMi;
      miRemaining = svc.intervalMi - miSince;
      pctUsed = Math.min(100, Math.round((miSince / svc.intervalMi) * 100));
      if (miRemaining <= 0)             status = 'overdue';
      else if (miRemaining <= meta.urgentMi) status = 'due_soon';
      else if (pctUsed >= 70)           status = 'watch';
      else                              status = 'ok';
    } else if (odo != null) {
      status = 'unknown'; // odo known but no last-service baseline
    }

    return {
      key,
      label:       meta.label,
      icon:        meta.icon,
      intervalMi:  svc.intervalMi,
      lastMi:      svc.lastMi,
      miRemaining,
      pctUsed,
      status,
    };
  });
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function UserProvider({ children }) {
  const [user, setUserRaw] = useState(load);

  const setUser = useCallback((u) => {
    setUserRaw(u);
    if (u) save(u); else localStorage.removeItem('cactus_user');
  }, []);

  const updateUser = useCallback((patch) => {
    setUserRaw(prev => { const next = { ...prev, ...patch }; save(next); return next; });
  }, []);

  // ── Vehicles ────────────────────────────────────────────────────────────────

  const addVehicle = useCallback((vehicle) => {
    setUserRaw(prev => {
      const v = { ...vehicle, id: `v${Date.now()}` };
      const vehicles = [...(prev.vehicles || []), v];
      const next = { ...prev, vehicles, activeVehicleId: prev.activeVehicleId || v.id };
      save(next); return next;
    });
  }, []);

  const removeVehicle = useCallback((id) => {
    setUserRaw(prev => {
      const vehicles = (prev.vehicles || []).filter(v => v.id !== id);
      const activeVehicleId = prev.activeVehicleId === id ? (vehicles[0]?.id || null) : prev.activeVehicleId;
      const next = { ...prev, vehicles, activeVehicleId };
      save(next); return next;
    });
  }, []);

  const setActiveVehicle = useCallback((id) => {
    setUserRaw(prev => { const next = { ...prev, activeVehicleId: id }; save(next); return next; });
  }, []);

  // ── OBD Adapters ────────────────────────────────────────────────────────────

  const addAdapter = useCallback((adapter) => {
    setUserRaw(prev => {
      const obdAdapters = [...(prev.obdAdapters || []), { ...adapter, id: `a${Date.now()}` }];
      const next = { ...prev, obdAdapters }; save(next); return next;
    });
  }, []);

  const removeAdapter = useCallback((id) => {
    setUserRaw(prev => {
      const obdAdapters = (prev.obdAdapters || []).filter(a => a.id !== id);
      const next = { ...prev, obdAdapters }; save(next); return next;
    });
  }, []);

  // ── Maintenance ─────────────────────────────────────────────────────────────

  const updateMaintenance = useCallback((patch) => {
    setUserRaw(prev => {
      const maintenance = { ...(prev.maintenance || DEFAULT_MAINTENANCE), ...patch };
      const next = { ...prev, maintenance }; save(next); return next;
    });
  }, []);

  const updateServiceRecord = useCallback((serviceKey, patch) => {
    setUserRaw(prev => {
      const maintenance = {
        ...(prev.maintenance || DEFAULT_MAINTENANCE),
        [serviceKey]: {
          ...(DEFAULT_MAINTENANCE[serviceKey]),
          ...(prev.maintenance?.[serviceKey] || {}),
          ...patch,
        },
      };
      const next = { ...prev, maintenance }; save(next); return next;
    });
  }, []);

  // ── Preferences ─────────────────────────────────────────────────────────────

  const updateInsightPrefs = useCallback((patch) => {
    setUserRaw(prev => {
      const insightPrefs = { ...DEFAULT_INSIGHT_PREFS, ...(prev.insightPrefs || {}), ...patch };
      const next = { ...prev, insightPrefs }; save(next); return next;
    });
  }, []);

  const updateDashPrefs = useCallback((patch) => {
    setUserRaw(prev => {
      const dashPrefs = { ...DEFAULT_DASH_PREFS, ...(prev.dashPrefs || {}), ...patch };
      const next = { ...prev, dashPrefs }; save(next); return next;
    });
  }, []);

  // ── Auth ────────────────────────────────────────────────────────────────────

  const logout = useCallback(() => {
    localStorage.removeItem('cactus_user');
    setUserRaw(null);
  }, []);

  const deleteAccount = useCallback(() => {
    localStorage.removeItem('cactus_user');
    setUserRaw(null);
  }, []);

  // ── Derived ─────────────────────────────────────────────────────────────────

  const activeVehicle =
    user?.vehicles?.find(v => v.id === user.activeVehicleId) ||
    user?.vehicles?.[0] ||
    null;

  const insightPrefs = { ...DEFAULT_INSIGHT_PREFS, ...(user?.insightPrefs || {}) };
  const dashPrefs    = { ...DEFAULT_DASH_PREFS,    ...(user?.dashPrefs    || {}) };
  const maintenance  = { ...DEFAULT_MAINTENANCE,   ...(user?.maintenance  || {}) };

  return (
    <UserContext.Provider value={{
      user, setUser, updateUser, logout, deleteAccount,
      addVehicle, removeVehicle, setActiveVehicle,
      addAdapter, removeAdapter,
      updateMaintenance, updateServiceRecord,
      updateInsightPrefs, updateDashPrefs,
      activeVehicle,
      insightPrefs,
      dashPrefs,
      maintenance,
    }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
