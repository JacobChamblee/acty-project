import React, { createContext, useContext, useState, useCallback } from 'react';

const UserContext = createContext(null);

function load() {
  try { const r = localStorage.getItem('cactus_user'); return r ? JSON.parse(r) : null; }
  catch { return null; }
}
function save(u) { localStorage.setItem('cactus_user', JSON.stringify(u)); }

export function UserProvider({ children }) {
  const [user, setUserRaw] = useState(load);

  const setUser = useCallback((u) => {
    setUserRaw(u);
    if (u) save(u); else localStorage.removeItem('cactus_user');
  }, []);

  const updateUser = useCallback((patch) => {
    setUserRaw(prev => { const next = { ...prev, ...patch }; save(next); return next; });
  }, []);

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

  const logout = useCallback(() => {
    localStorage.removeItem('cactus_user');
    setUserRaw(null);
  }, []);

  const activeVehicle =
    user?.vehicles?.find(v => v.id === user.activeVehicleId) ||
    user?.vehicles?.[0] ||
    null;

  return (
    <UserContext.Provider value={{
      user, setUser, updateUser, logout,
      addVehicle, removeVehicle, setActiveVehicle,
      addAdapter, removeAdapter,
      activeVehicle,
    }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
