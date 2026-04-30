import React, { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, CheckCircle2, KeyRound, Languages, ListChecks, Save, Server, SubtitlesIcon, Wifi, XCircle, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { useApp, API } from "../context/AppContext";
import { t } from "../lib/i18n";
import { toast } from "sonner";
import axios from "axios";

const Section = ({ icon: Icon, title, children, testid }) => (
  <section
    className="rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm p-5 sm:p-6"
    data-testid={testid}
  >
    <div className="flex items-center gap-2 mb-5">
      <div className="w-8 h-8 rounded-md bg-amber-500/15 text-amber-400 flex items-center justify-center">
        <Icon className="w-4 h-4" />
      </div>
      <h2 className="font-display font-semibold text-lg sm:text-xl">{title}</h2>
    </div>
    <div className="space-y-4">{children}</div>
  </section>
);

const SettingsPage = () => {
  const { lang, settings, save, loaded } = useApp();
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    if (settings) setDraft(JSON.parse(JSON.stringify(settings)));
  }, [settings]);

  if (!loaded || !draft) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 pb-24">
        <p className="text-slate-400">Carregando...</p>
      </div>
    );
  }

  const update = (path, value) => {
    setDraft((prev) => {
      const next = JSON.parse(JSON.stringify(prev));
      const keys = path.split(".");
      let ref = next;
      for (let i = 0; i < keys.length - 1; i++) {
        ref[keys[i]] = ref[keys[i]] ?? {};
        ref = ref[keys[i]];
      }
      ref[keys[keys.length - 1]] = value;
      return next;
    });
  };

  const movePriority = (sourceKey, dir) => {
    setDraft((prev) => {
      const next = JSON.parse(JSON.stringify(prev));
      const list = Object.entries(next.sources)
        .map(([k, v]) => ({ k, ...v }))
        .sort((a, b) => a.priority - b.priority);
      const idx = list.findIndex((x) => x.k === sourceKey);
      const swap = dir === "up" ? idx - 1 : idx + 1;
      if (swap < 0 || swap >= list.length) return prev;
      [list[idx], list[swap]] = [list[swap], list[idx]];
      list.forEach((item, i) => {
        next.sources[item.k] = { enabled: item.enabled, priority: i + 1 };
      });
      return next;
    });
  };

  const onSave = async () => {
    setSaving(true);
    try {
      await save(draft);
      toast.success(t(lang, "settings.saved"));
    } catch (e) {
      toast.error(t(lang, "settings.saveError"));
    } finally {
      setSaving(false);
    }
  };

  const onTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await axios.get(`${API}/settings/test-connection`, {
        params: { api_key: draft.api_keys.opensubtitles || "" },
      });
      setTestResult(r.data);
      if (r.data.success) toast.success(t(lang, "settings.testOk"));
      else toast.error(`${t(lang, "settings.testFail")}: ${r.data.message}`);
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message;
      setTestResult({ success: false, message: msg });
      toast.error(`${t(lang, "settings.testFail")}: ${msg}`);
    } finally {
      setTesting(false);
    }
  };

  const sortedSources = Object.entries(draft.sources)
    .map(([k, v]) => ({ k, ...v }))
    .sort((a, b) => a.priority - b.priority);

  const sourceLabel = { yts: "YTS", nyaa: "Nyaa", "1337x": "1337x" };

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 pb-32">
      <div className="mb-8">
        <h1 className="font-display font-bold text-3xl sm:text-4xl tracking-tight">
          {t(lang, "settings.title")}
        </h1>
        <p className="text-slate-400 mt-2">{t(lang, "settings.subtitle")}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* API Keys */}
        <Section icon={KeyRound} title={t(lang, "settings.sections.api")} testid="section-api">
          <div>
            <Label className="text-sm">{t(lang, "settings.apiKeys.opensubtitles")}</Label>
            <div className="flex gap-2 mt-1.5">
              <Input
                type="password"
                value={draft.api_keys.opensubtitles || ""}
                onChange={(e) => update("api_keys.opensubtitles", e.target.value)}
                placeholder="xxxxxxxxxxxxxxxxxxxxxxxx"
                className="bg-slate-800/60 border-slate-700"
                data-testid="opensubtitles-key-input"
              />
              <Button
                onClick={onTest}
                disabled={testing || !draft.api_keys.opensubtitles}
                variant="outline"
                className="border-slate-700 hover:bg-slate-800 shrink-0"
                data-testid="test-connection-btn"
              >
                {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wifi className="w-4 h-4" />}
                <span className="ml-1.5 hidden sm:inline">
                  {testing ? t(lang, "settings.testing") : t(lang, "settings.apiKeys.test")}
                </span>
              </Button>
            </div>
            <p className="text-xs text-slate-500 mt-1.5">{t(lang, "settings.apiKeys.opensubtitlesHelp")}</p>
            {testResult && (
              <div
                className={`mt-2 flex items-center gap-2 text-sm ${
                  testResult.success ? "text-emerald-400" : "text-rose-400"
                }`}
                data-testid="test-result"
              >
                {testResult.success ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                {testResult.message}
              </div>
            )}
          </div>
          <div className="border-t border-slate-800 pt-4 space-y-3">
            <p className="text-xs text-slate-500">{t(lang, "settings.apiKeys.qbHelp")}</p>
            <div>
              <Label className="text-sm">{t(lang, "settings.apiKeys.qbUrl")}</Label>
              <Input
                value={draft.api_keys.qbittorrent_url || ""}
                onChange={(e) => update("api_keys.qbittorrent_url", e.target.value)}
                placeholder="http://localhost:8080"
                className="bg-slate-800/60 border-slate-700 mt-1.5"
                data-testid="qb-url-input"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-sm">{t(lang, "settings.apiKeys.qbUser")}</Label>
                <Input
                  value={draft.api_keys.qbittorrent_user || ""}
                  onChange={(e) => update("api_keys.qbittorrent_user", e.target.value)}
                  className="bg-slate-800/60 border-slate-700 mt-1.5"
                  data-testid="qb-user-input"
                />
              </div>
              <div>
                <Label className="text-sm">{t(lang, "settings.apiKeys.qbPass")}</Label>
                <Input
                  type="password"
                  value={draft.api_keys.qbittorrent_pass || ""}
                  onChange={(e) => update("api_keys.qbittorrent_pass", e.target.value)}
                  className="bg-slate-800/60 border-slate-700 mt-1.5"
                  data-testid="qb-pass-input"
                />
              </div>
            </div>
          </div>
        </Section>

        {/* Search Preferences */}
        <Section icon={ListChecks} title={t(lang, "settings.sections.prefs")} testid="section-prefs">
          <div>
            <Label className="text-sm">{t(lang, "settings.prefs.defaultLanguage")}</Label>
            <Select
              value={draft.search_preferences.default_language}
              onValueChange={(v) => update("search_preferences.default_language", v)}
            >
              <SelectTrigger className="bg-slate-800/60 border-slate-700 mt-1.5" data-testid="pref-default-language">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="any">{t(lang, "languages.any")}</SelectItem>
                <SelectItem value="dubbed_pt_br">{t(lang, "languages.dubbed_pt_br")}</SelectItem>
                <SelectItem value="subbed">{t(lang, "languages.subbed")}</SelectItem>
                <SelectItem value="original_en">{t(lang, "languages.original_en")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm">{t(lang, "settings.prefs.defaultQuality")}</Label>
            <Select
              value={draft.search_preferences.default_quality}
              onValueChange={(v) => update("search_preferences.default_quality", v)}
            >
              <SelectTrigger className="bg-slate-800/60 border-slate-700 mt-1.5" data-testid="pref-default-quality">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="any">{t(lang, "qualities.any")}</SelectItem>
                <SelectItem value="4k">4K</SelectItem>
                <SelectItem value="1080p">1080p</SelectItem>
                <SelectItem value="720p">720p</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm">{t(lang, "settings.prefs.defaultType")}</Label>
            <Select
              value={draft.search_preferences.default_type}
              onValueChange={(v) => update("search_preferences.default_type", v)}
            >
              <SelectTrigger className="bg-slate-800/60 border-slate-700 mt-1.5" data-testid="pref-default-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="any">{t(lang, "types.any")}</SelectItem>
                <SelectItem value="movie">{t(lang, "types.movie")}</SelectItem>
                <SelectItem value="series">{t(lang, "types.series")}</SelectItem>
                <SelectItem value="anime">{t(lang, "types.anime")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm">{t(lang, "settings.prefs.maxResults")}</Label>
            <Select
              value={String(draft.search_preferences.max_results)}
              onValueChange={(v) => update("search_preferences.max_results", Number(v))}
            >
              <SelectTrigger className="bg-slate-800/60 border-slate-700 mt-1.5" data-testid="pref-max-results">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10</SelectItem>
                <SelectItem value="20">20</SelectItem>
                <SelectItem value="30">30</SelectItem>
                <SelectItem value="50">50</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </Section>

        {/* Sources */}
        <Section icon={Server} title={t(lang, "settings.sections.sources")} testid="section-sources">
          <p className="text-xs text-slate-500 -mt-2">{t(lang, "settings.sources.intro")}</p>
          <ul className="space-y-2">
            {sortedSources.map((s, idx) => (
              <li
                key={s.k}
                className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2.5"
                data-testid={`source-row-${s.k}`}
              >
                <span className="w-7 h-7 rounded-md bg-slate-800 text-amber-400 font-display font-semibold text-sm flex items-center justify-center">
                  {idx + 1}
                </span>
                <span className="font-medium text-slate-100 flex-1">{sourceLabel[s.k]}</span>
                <Switch
                  checked={s.enabled}
                  onCheckedChange={(v) => update(`sources.${s.k}.enabled`, v)}
                  data-testid={`source-toggle-${s.k}`}
                />
                <div className="flex flex-col">
                  <button
                    onClick={() => movePriority(s.k, "up")}
                    disabled={idx === 0}
                    className="text-slate-400 hover:text-amber-400 disabled:opacity-30 disabled:hover:text-slate-400"
                    aria-label={t(lang, "settings.sources.priorityUp")}
                    data-testid={`source-up-${s.k}`}
                  >
                    <ArrowUp className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => movePriority(s.k, "down")}
                    disabled={idx === sortedSources.length - 1}
                    className="text-slate-400 hover:text-amber-400 disabled:opacity-30 disabled:hover:text-slate-400"
                    aria-label={t(lang, "settings.sources.priorityDown")}
                    data-testid={`source-down-${s.k}`}
                  >
                    <ArrowDown className="w-4 h-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </Section>

        {/* Subtitles */}
        <Section icon={SubtitlesIcon} title={t(lang, "settings.sections.subs")} testid="section-subs">
          <div>
            <Label className="text-sm">{t(lang, "settings.subs.defaultLanguage")}</Label>
            <Select
              value={draft.subtitle_preferences.default_language}
              onValueChange={(v) => update("subtitle_preferences.default_language", v)}
            >
              <SelectTrigger className="bg-slate-800/60 border-slate-700 mt-1.5" data-testid="pref-sub-language">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pt-br">{t(lang, "subtitles.langs.pt-br")}</SelectItem>
                <SelectItem value="pt">{t(lang, "subtitles.langs.pt")}</SelectItem>
                <SelectItem value="en">{t(lang, "subtitles.langs.en")}</SelectItem>
                <SelectItem value="es">{t(lang, "subtitles.langs.es")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm">{t(lang, "settings.subs.format")}</Label>
            <Select
              value={draft.subtitle_preferences.preferred_format}
              onValueChange={(v) => update("subtitle_preferences.preferred_format", v)}
            >
              <SelectTrigger className="bg-slate-800/60 border-slate-700 mt-1.5" data-testid="pref-sub-format">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="srt">.srt</SelectItem>
                <SelectItem value="vtt">.vtt</SelectItem>
                <SelectItem value="any">{t(lang, "settings.subs.formats.any")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </Section>

        {/* Interface */}
        <Section icon={Languages} title={t(lang, "settings.sections.ui")} testid="section-ui">
          <div>
            <Label className="text-sm">{t(lang, "settings.ui.theme")}</Label>
            <Select
              value={draft.interface.theme}
              onValueChange={(v) => update("interface.theme", v)}
            >
              <SelectTrigger className="bg-slate-800/60 border-slate-700 mt-1.5" data-testid="pref-theme">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="dark">{t(lang, "settings.ui.themeDark")}</SelectItem>
                <SelectItem value="light">{t(lang, "settings.ui.themeLight")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-sm">{t(lang, "settings.ui.language")}</Label>
            <Select
              value={draft.interface.language}
              onValueChange={(v) => update("interface.language", v)}
            >
              <SelectTrigger className="bg-slate-800/60 border-slate-700 mt-1.5" data-testid="pref-ui-language">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pt">Português</SelectItem>
                <SelectItem value="en">English</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </Section>
      </div>

      <div className="mt-8 flex justify-end sticky bottom-20 z-20">
        <Button
          onClick={onSave}
          disabled={saving}
          className="bg-amber-500 hover:bg-amber-400 text-slate-900 font-semibold px-6 h-11 shadow-[0_8px_30px_-8px_rgba(245,158,11,0.6)]"
          data-testid="save-settings-btn"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
          {t(lang, "settings.save")}
        </Button>
      </div>
    </div>
  );
};

export default SettingsPage;
