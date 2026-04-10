import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { supabase } from '../supabaseClient';
import { syncProfileToBackend } from '../authApi';
import { API_BASE } from '../config';

const UserContext = createContext(null);

// ── Storage keys ──────────────────────────────────────────────────────────────
// cactus_accounts: { [email]: userObject } — vehicle/prefs data, isolated per user
// cactus_session:  email of current logged-in user
const ACCOUNTS_KEY = 'cactus_accounts';
const SESSION_KEY  = 'cactus_session';

// ── Account registry helpers ──────────────────────────────────────────────────
function loadAccounts() {
  try { return JSON.parse(localStorage.getItem(ACCOUNTS_KEY)) || {}; }
  catch { return {}; }
}
function saveAccounts(accounts) {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
}
function loadCurrentEmail() {
  return localStorage.getItem(SESSION_KEY) || null;
}
function saveCurrentEmail(email) {
  if (email) localStorage.setItem(SESSION_KEY, email);
  else localStorage.removeItem(SESSION_KEY);
}

function persistAccount(account) {
  if (!account?.email) return;
  const accounts = loadAccounts();
  accounts[account.email.toLowerCase()] = account;
  saveAccounts(accounts);
  saveCurrentEmail(account.email.toLowerCase());
}

// ── Load initial user from local registry ─────────────────────────────────────
function loadInitialUser() {
  const email = loadCurrentEmail();
  if (!email) return null;
  return loadAccounts()[email] || null;
}

// ── Map a Supabase user object to the local account shape ─────────────────────
function accountFromSupabaseUser(sbUser) {
  const email = sbUser.email.toLowerCase();
  const meta  = sbUser.user_metadata || {};
  return {
    username:        meta.username || email.split('@')[0],
    displayName:     meta.full_name || meta.display_name || meta.username || email.split('@')[0],
    email,
    avatarUrl:       meta.avatar_url || null,
    provider:        sbUser.app_metadata?.provider || null,
    vehicles:        [],
    obdAdapters:     [],
    activeVehicleId: null,
  };
}

// ── Apply a Supabase user into the local registry + React state ───────────────
// If no local account exists, fetches from the backend first so that vehicles
// added on another device/browser are restored before setting state.
async function applySupabaseUser(sbUser, setUserRaw) {
  const email    = sbUser.email.toLowerCase();
  const accounts = loadAccounts();

  if (!accounts[email]) {
    // Attempt to restore saved profile from the API backend
    let restored = false;
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        const resp = await fetch(`${API_BASE}/api/v1/auth/me`, {
          headers: { 'Authorization': `Bearer ${session.access_token}` },
        });
        if (resp.ok) {
          const json = await resp.json();
          const backendAccount = json?.account;
          // Only use backend data if it has meaningful content beyond a bare stub
          if (backendAccount && (backendAccount.vehicles?.length > 0 || backendAccount.username)) {
            accounts[email] = {
              ...accountFromSupabaseUser(sbUser),
              ...backendAccount,
              email,
              avatarUrl: sbUser.user_metadata?.avatar_url || backendAccount.avatarUrl || null,
            };
            saveAccounts(accounts);
            restored = true;
          }
        }
      }
    } catch (_) { /* network error — fall through to fresh account */ }

    if (!restored) {
      accounts[email] = accountFromSupabaseUser(sbUser);
      saveAccounts(accounts);
    }
  }

  saveCurrentEmail(email);
  setUserRaw(accounts[email]);
}

// ── Default state shapes ──────────────────────────────────────────────────────
export const DEFAULT_MAINTENANCE = {
  currentOdometer:   null,
  oilChange:         { lastMi: null, intervalMi: 5000  },
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

// ── Maintenance calculation ───────────────────────────────────────────────────
const SERVICE_META = {
  oilChange:         { label: 'Oil Change',         icon: '🔧', urgentMi: 500  },
  cabinAirFilter:    { label: 'Cabin Air Filter',   icon: '💨', urgentMi: 1000 },
  brakes:            { label: 'Brake Inspection',   icon: '🛑', urgentMi: 2000 },
  transmissionFluid: { label: 'Transmission Fluid', icon: '⚙️', urgentMi: 2000 },
  coolantFlush:      { label: 'Coolant Flush',      icon: '🧊', urgentMi: 2000 },
};

export function computeMaintenanceItems(maintenance) {
  const odo = maintenance?.currentOdometer;
  return Object.entries(SERVICE_META).map(([key, meta]) => {
    const svc = maintenance?.[key] || DEFAULT_MAINTENANCE[key];
    let miRemaining = null;
    let pctUsed = null;
    let status = 'unknown';

    if (odo != null && svc.lastMi != null) {
      const miSince = odo - svc.lastMi;
      miRemaining = svc.intervalMi - miSince;
      pctUsed = Math.min(100, Math.round((miSince / svc.intervalMi) * 100));
      if (miRemaining <= 0)                  status = 'overdue';
      else if (miRemaining <= meta.urgentMi) status = 'due_soon';
      else if (pctUsed >= 70)                status = 'watch';
      else                                   status = 'ok';
    } else if (odo != null) {
      status = 'unknown';
    }

    return { key, label: meta.label, icon: meta.icon, intervalMi: svc.intervalMi, lastMi: svc.lastMi, miRemaining, pctUsed, status };
  });
}

// ── Auth helpers (exposed so Auth.js can call them without context) ────────────
export const authStore = {
  getAccount: (email) => loadAccounts()[email?.toLowerCase()] || null,
  createAccount: (userData) => {
    const accounts = loadAccounts();
    const key = userData.email.toLowerCase();
    accounts[key] = { ...userData, email: key };
    saveAccounts(accounts);
    saveCurrentEmail(key);
  },
  updateAccount: (email, patch) => {
    const accounts = loadAccounts();
    const key = email.toLowerCase();
    if (accounts[key]) {
      accounts[key] = { ...accounts[key], ...patch };
      saveAccounts(accounts);
    }
  },
  setSession: (email) => saveCurrentEmail(email?.toLowerCase() || null),
  clearSession: () => saveCurrentEmail(null),
  deleteAccount: (email) => {
    const accounts = loadAccounts();
    delete accounts[email.toLowerCase()];
    saveAccounts(accounts);
    saveCurrentEmail(null);
  },
};

// ── Provider ──────────────────────────────────────────────────────────────────
export function UserProvider({ children }) {
  const [user, setUserRaw] = useState(loadInitialUser);
  const [hasHydratedRemote, setHasHydratedRemote] = useState(false);
  // Tracks the user object at hydration time so we can skip syncing on initial load
  const hydratedUserRef = useRef(undefined);

  // ── Supabase session listener ─────────────────────────────────────────────
  useEffect(() => {
    // Restore session on page load
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.user) applySupabaseUser(session.user, setUserRaw);
      setHasHydratedRemote(true);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_IN' && session?.user) {
        applySupabaseUser(session.user, setUserRaw);
      } else if (event === 'SIGNED_OUT') {
        saveCurrentEmail(null);
        setUserRaw(null);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  // ── Sync profile to FastAPI backend after user-initiated changes ─────────
  // We intentionally skip the first fire (hydration) to avoid overwriting
  // backend data with a stale local snapshot on login from a new device.
  useEffect(() => {
    if (!hasHydratedRemote || !user?.email) return;
    if (hydratedUserRef.current === undefined) {
      // Record the user object at hydration time — don't sync it
      hydratedUserRef.current = user;
      return;
    }
    if (user === hydratedUserRef.current) return; // unchanged
    void syncProfileToBackend(user);
  }, [hasHydratedRemote, user]);

  // Write to registry + update session pointer + local state
  const setUser = useCallback((u) => {
    setUserRaw(u);
    if (u) {
      persistAccount(u);
    } else {
      saveCurrentEmail(null);
    }
  }, []);

  // Partial update — writes to registry
  const updateUser = useCallback((patch) => {
    setUserRaw(prev => {
      if (!prev) return prev;
      const next = { ...prev, ...patch };
      const accounts = loadAccounts();
      accounts[next.email.toLowerCase()] = next;
      saveAccounts(accounts);
      return next;
    });
  }, []);

  // ── Vehicles ────────────────────────────────────────────────────────────────
  const addVehicle = useCallback((vehicle) => {
    setUserRaw(prev => {
      if (!prev) return prev;
      const v = { ...vehicle, id: `v${Date.now()}` };
      const vehicles = [...(prev.vehicles || []), v];
      const next = { ...prev, vehicles, activeVehicleId: prev.activeVehicleId || v.id };
      const accounts = loadAccounts();
      accounts[next.email.toLowerCase()] = next;
      saveAccounts(accounts);
      return next;
    });
  }, []);

  const removeVehicle = useCallback((id) => {
    setUserRaw(prev => {
      if (!prev) return prev;
      const vehicles = (prev.vehicles || []).filter(v => v.id !== id);
      const activeVehicleId = prev.activeVehicleId === id ? (vehicles[0]?.id || null) : prev.activeVehicleId;
      const next = { ...prev, vehicles, activeVehicleId };
      const accounts = loadAccounts();
      accounts[next.email.toLowerCase()] = next;
      saveAccounts(accounts);
      return next;
    });
  }, []);

  const setActiveVehicle = useCallback((id) => {
    setUserRaw(prev => {
      if (!prev) return prev;
      const next = { ...prev, activeVehicleId: id };
      const accounts = loadAccounts();
      accounts[next.email.toLowerCase()] = next;
      saveAccounts(accounts);
      return next;
    });
  }, []);

  // ── OBD Adapters ────────────────────────────────────────────────────────────
  const addAdapter = useCallback((adapter) => {
    setUserRaw(prev => {
      if (!prev) return prev;
      const obdAdapters = [...(prev.obdAdapters || []), { ...adapter, id: `a${Date.now()}` }];
      const next = { ...prev, obdAdapters };
      const accounts = loadAccounts();
      accounts[next.email.toLowerCase()] = next;
      saveAccounts(accounts);
      return next;
    });
  }, []);

  const removeAdapter = useCallback((id) => {
    setUserRaw(prev => {
      if (!prev) return prev;
      const obdAdapters = (prev.obdAdapters || []).filter(a => a.id !== id);
      const next = { ...prev, obdAdapters };
      const accounts = loadAccounts();
      accounts[next.email.toLowerCase()] = next;
      saveAccounts(accounts);
      return next;
    });
  }, []);

  // ── Maintenance ─────────────────────────────────────────────────────────────
  const updateMaintenance = useCallback((patch) => {
    setUserRaw(prev => {
      if (!prev) return prev;
      const maintenance = { ...(prev.maintenance || DEFAULT_MAINTENANCE), ...patch };
      const next = { ...prev, maintenance };
      const accounts = loadAccounts();
      accounts[next.email.toLowerCase()] = next;
      saveAccounts(accounts);
      return next;
    });
  }, []);

  const updateServiceRecord = useCallback((serviceKey, patch) => {
    setUserRaw(prev => {
      if (!prev) return prev;
      const maintenance = {
        ...(prev.maintenance || DEFAULT_MAINTENANCE),
        [serviceKey]: {
          ...(DEFAULT_MAINTENANCE[serviceKey]),
          ...(prev.maintenance?.[serviceKey] || {}),
          ...patch,
        },
      };
      const next = { ...prev, maintenance };
      const accounts = loadAccounts();
      accounts[next.email.toLowerCase()] = next;
      saveAccounts(accounts);
      return next;
    });
  }, []);

  // ── Preferences ─────────────────────────────────────────────────────────────
  const updateInsightPrefs = useCallback((patch) => {
    setUserRaw(prev => {
      if (!prev) return prev;
      const insightPrefs = { ...DEFAULT_INSIGHT_PREFS, ...(prev.insightPrefs || {}), ...patch };
      const next = { ...prev, insightPrefs };
      const accounts = loadAccounts();
      accounts[next.email.toLowerCase()] = next;
      saveAccounts(accounts);
      return next;
    });
  }, []);

  const updateDashPrefs = useCallback((patch) => {
    setUserRaw(prev => {
      if (!prev) return prev;
      const dashPrefs = { ...DEFAULT_DASH_PREFS, ...(prev.dashPrefs || {}), ...patch };
      const next = { ...prev, dashPrefs };
      const accounts = loadAccounts();
      accounts[next.email.toLowerCase()] = next;
      saveAccounts(accounts);
      return next;
    });
  }, []);

  // ── Auth ────────────────────────────────────────────────────────────────────
  const logout = useCallback(() => {
    saveCurrentEmail(null);
    setUserRaw(null);
    supabase.auth.signOut().catch(() => {}); // fire-and-forget
  }, []);

  const deleteAccount = useCallback(() => {
    if (user) {
      const accounts = loadAccounts();
      delete accounts[user.email.toLowerCase()];
      saveAccounts(accounts);
    }
    saveCurrentEmail(null);
    setUserRaw(null);
    supabase.auth.signOut().catch(() => {});
  }, [user]);

  // ── Derived values ───────────────────────────────────────────────────────────
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
      activeVehicle, insightPrefs, dashPrefs, maintenance,
    }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
