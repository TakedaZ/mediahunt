import React, { useState, useEffect } from "react";
import { AlertTriangle, X } from "lucide-react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const KEY = "mediahunt_disclaimer_dismissed";

const DisclaimerBanner = () => {
  const { lang } = useApp();
  const [show, setShow] = useState(false);

  useEffect(() => {
    const dismissed = localStorage.getItem(KEY);
    if (!dismissed) setShow(true);
  }, []);

  const dismiss = () => {
    localStorage.setItem(KEY, "1");
    setShow(false);
  };

  if (!show) return null;
  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-amber-500/30 bg-slate-900/95 backdrop-blur-md"
      data-testid="disclaimer-banner"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-start sm:items-center gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5 sm:mt-0" />
        <p className="text-xs sm:text-sm text-slate-300 leading-relaxed flex-1">
          {t(lang, "disclaimer")}
        </p>
        <button
          onClick={dismiss}
          data-testid="disclaimer-dismiss"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-amber-500 hover:bg-amber-400 text-slate-900 text-xs font-semibold transition-colors flex-shrink-0"
        >
          <X className="w-3.5 h-3.5" />
          {t(lang, "dismiss")}
        </button>
      </div>
    </div>
  );
};

export default DisclaimerBanner;
