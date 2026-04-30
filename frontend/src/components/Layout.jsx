import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Search, Settings as SettingsIcon, Film } from "lucide-react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import DisclaimerBanner from "./DisclaimerBanner";

export const Layout = ({ children }) => {
  const { lang } = useApp();
  const location = useLocation();
  const isActive = (p) => location.pathname === p;

  return (
    <div className="min-h-screen flex flex-col grain">
      <header
        className="sticky top-0 z-30 backdrop-blur-xl bg-[#0B0F19]/80 border-b border-slate-800"
        data-testid="app-header"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-2 group"
            data-testid="logo-link"
          >
            <div className="relative">
              <div className="absolute inset-0 bg-amber-500/30 blur-xl group-hover:blur-2xl transition-all" />
              <div className="relative w-9 h-9 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
                <Film className="w-5 h-5 text-slate-900" strokeWidth={2.5} />
              </div>
            </div>
            <div className="font-display font-bold text-xl tracking-tight">
              Media<span className="text-amber-500">Hunt</span>
            </div>
          </Link>
          <nav className="flex items-center gap-1">
            <Link
              to="/"
              data-testid="nav-search"
              className={`px-3 sm:px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 transition-colors ${
                isActive("/")
                  ? "bg-slate-800 text-amber-400"
                  : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
              }`}
            >
              <Search className="w-4 h-4" />
              <span className="hidden sm:inline">{t(lang, "nav.search")}</span>
            </Link>
            <Link
              to="/settings"
              data-testid="nav-settings"
              className={`px-3 sm:px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 transition-colors ${
                isActive("/settings")
                  ? "bg-slate-800 text-amber-400"
                  : "text-slate-300 hover:bg-slate-800/60 hover:text-white"
              }`}
            >
              <SettingsIcon className="w-4 h-4" />
              <span className="hidden sm:inline">{t(lang, "nav.settings")}</span>
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 relative z-10">{children}</main>

      <DisclaimerBanner />
    </div>
  );
};

export default Layout;
