import React, { useEffect, useState } from "react";
import axios from "axios";
import { Search as SearchIcon, Loader2, Sparkles } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Skeleton } from "../components/ui/skeleton";
import { useApp, API } from "../context/AppContext";
import { t } from "../lib/i18n";
import TorrentCard from "../components/TorrentCard";
import SubtitleDialog from "../components/SubtitleDialog";
import { toast } from "sonner";

const SearchPage = () => {
  const { lang, settings, loaded } = useApp();
  const [query, setQuery] = useState("");
  const [type, setType] = useState("any");
  const [language, setLanguage] = useState("any");
  const [quality, setQuality] = useState("any");
  const [maxResults, setMaxResults] = useState(20);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [searched, setSearched] = useState(false);
  const [subOpen, setSubOpen] = useState(false);
  const [subPrefill, setSubPrefill] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (loaded && settings) {
      setType(settings.search_preferences?.default_type || "any");
      setLanguage(settings.search_preferences?.default_language || "any");
      setQuality(settings.search_preferences?.default_quality || "any");
      setMaxResults(settings.search_preferences?.max_results || 20);
    }
  }, [loaded, settings]);

  const doSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const r = await axios.get(`${API}/search/torrents`, {
        params: { query, type, language, quality, max_results: maxResults },
      });
      setResults(r.data.results || []);
      setWarnings(r.data.warnings || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
      setResults([]);
      setWarnings([]);
    } finally {
      setLoading(false);
    }
  };

  const openSubtitles = (result) => {
    setSubPrefill(result);
    setSubOpen(true);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 pb-24">
      {/* Hero search */}
      <section className="text-center mb-10 sm:mb-14">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-amber-500/30 bg-amber-500/5 text-amber-400 text-xs font-medium mb-4">
          <Sparkles className="w-3 h-3" />
          YTS · Nyaa · 1337x · OpenSubtitles
        </div>
        <h1 className="font-display font-bold text-4xl sm:text-5xl lg:text-6xl tracking-tight">
          Encontre <span className="text-amber-500">qualquer</span> mídia
        </h1>
        <p className="text-slate-400 mt-3 text-base sm:text-lg max-w-xl mx-auto">
          {t(lang, "tagline")}
        </p>
      </section>

      {/* Search bar */}
      <div
        className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5 mb-6 backdrop-blur-sm"
        data-testid="search-bar"
      >
        <div className="flex flex-col lg:flex-row gap-3">
          <div className="flex-1">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t(lang, "search.placeholder")}
              onKeyDown={(e) => e.key === "Enter" && doSearch()}
              className="bg-slate-800/60 border-slate-700 h-12 text-base"
              data-testid="search-input"
            />
          </div>
          <Button
            onClick={doSearch}
            disabled={loading || !query.trim()}
            className="h-12 px-6 bg-amber-500 hover:bg-amber-400 text-slate-900 font-semibold lg:w-auto"
            data-testid="search-submit"
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <SearchIcon className="w-5 h-5" />
            )}
            <span className="ml-2">{t(lang, "search.cta")}</span>
          </Button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          <div>
            <Label className="text-xs text-slate-400 mb-1 block">{t(lang, "search.type")}</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger className="bg-slate-800/60 border-slate-700" data-testid="filter-type">
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
            <Label className="text-xs text-slate-400 mb-1 block">{t(lang, "search.language")}</Label>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="bg-slate-800/60 border-slate-700" data-testid="filter-language">
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
            <Label className="text-xs text-slate-400 mb-1 block">{t(lang, "search.quality")}</Label>
            <Select value={quality} onValueChange={setQuality}>
              <SelectTrigger className="bg-slate-800/60 border-slate-700" data-testid="filter-quality">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="any">{t(lang, "qualities.any")}</SelectItem>
                <SelectItem value="4k">{t(lang, "qualities.4k")}</SelectItem>
                <SelectItem value="1080p">{t(lang, "qualities.1080p")}</SelectItem>
                <SelectItem value="720p">{t(lang, "qualities.720p")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs text-slate-400 mb-1 block">{t(lang, "search.maxResults")}</Label>
            <Select value={String(maxResults)} onValueChange={(v) => setMaxResults(Number(v))}>
              <SelectTrigger className="bg-slate-800/60 border-slate-700" data-testid="filter-max">
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
        </div>
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="mb-4 space-y-2">
          {warnings.map((w, i) => (
            <div key={i} className="rounded-lg border border-amber-600/40 bg-amber-500/10 px-3 py-2 text-amber-200 text-sm">{w}</div>
          ))}
        </div>
      )}

      {selected && (
        <div className="mb-5 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <h3 className="font-semibold text-lg">{selected.title}</h3>
          <p className="text-sm text-slate-400 mt-1">
            Fonte: {selected.source} · Qualidade: {selected.quality || "N/A"} · Seeders: {selected.seeders ?? 0} · Leechers: {selected.leechers ?? 0}
          </p>
          {selected.size && <p className="text-sm text-slate-400">Tamanho: {selected.size}</p>}
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 sm:gap-6">
          {[...Array(12)].map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="aspect-[2/3] w-full rounded-xl bg-slate-800 shimmer" />
              <Skeleton className="h-3 w-3/4 bg-slate-800" />
              <Skeleton className="h-3 w-1/2 bg-slate-800" />
            </div>
          ))}
        </div>
      ) : !searched ? (
        <div
          className="rounded-2xl border border-dashed border-slate-800 p-10 sm:p-16 text-center"
          data-testid="empty-state"
        >
          <p className="text-slate-400 text-sm sm:text-base">{t(lang, "search.empty")}</p>
        </div>
      ) : results.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-800 p-10 text-center" data-testid="no-results">
          <p className="text-slate-400">{t(lang, "search.noResults")}</p>
        </div>
      ) : (
        <div
          className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 sm:gap-6"
          data-testid="results-grid"
        >
          {results.map((r) => (
            <TorrentCard key={r.id} result={r} onFindSubtitles={openSubtitles} onSelect={setSelected} />
          ))}
        </div>
      )}

      <SubtitleDialog open={subOpen} onOpenChange={setSubOpen} prefill={subPrefill} />
    </div>
  );
};

export default SearchPage;
