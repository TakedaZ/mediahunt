import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const AppContext = createContext(null);

export const AppProvider = ({ children }) => {
  const [settings, setSettings] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/settings`);
      setSettings(r.data);
    } catch (e) {
      console.error("Settings load error", e);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!settings) return;
    const theme = settings.interface?.theme || "dark";
    const root = document.documentElement;
    if (theme === "light") {
      root.classList.add("light");
      root.classList.remove("dark");
    } else {
      root.classList.add("dark");
      root.classList.remove("light");
    }
  }, [settings]);

  const save = async (patch) => {
    const r = await axios.post(`${API}/settings`, patch);
    setSettings(r.data);
    return r.data;
  };

  const lang = settings?.interface?.language || "pt";

  return (
    <AppContext.Provider value={{ settings, setSettings, save, loaded, lang, reload: load }}>
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be inside AppProvider");
  return ctx;
};
