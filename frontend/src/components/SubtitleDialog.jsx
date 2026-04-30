import React, { useEffect, useState } from "react";
import axios from "axios";
import { Download, Search as SearchIcon, Loader2, Star } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Badge } from "./ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Skeleton } from "./ui/skeleton";
import { toast } from "sonner";
import { useApp, API } from "../context/AppContext";
import { t } from "../lib/i18n";

const cleanTitle = (title = "") =>
  title
    .replace(/\.(mkv|mp4|avi|srt|zip)$/i, "")
    .replace(/[\.\-_]/g, " ")
    .replace(/\b(1080p|720p|2160p|4k|hdrip|webrip|web-dl|bluray|x264|x265|hevc|aac|dual|audio|dublado|legendado)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();

const SubtitleDialog = ({ open, onOpenChange, prefill }) => {
  const { lang, settings } = useApp();
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState(settings?.subtitle_preferences?.default_language || "pt-br");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    if (open) {
      const initial = prefill ? cleanTitle(prefill.title) : "";
      setQuery(initial);
      setResults([]);
      setSearched(false);
      setLanguage(settings?.subtitle_preferences?.default_language || "pt-br");
      if (initial) {
        // auto-search
        setTimeout(() => doSearch(initial, settings?.subtitle_preferences?.default_language || "pt-br"), 50);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, prefill]);

  const doSearch = async (q = query, l = language) => {
    if (!q.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const r = await axios.get(`${API}/search/subtitles`, {
        params: { query: q, language: l },
      });
      setResults(r.data.results || []);
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message;
      if (e?.response?.status === 400) {
        toast.error(t(lang, "subtitles.needsKey"));
      } else {
        toast.error(msg);
      }
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const downloadSub = async (s) => {
    if (!s.file_id) {
      toast.error("file_id ausente.");
      return;
    }
    try {
      const r = await axios.get(`${API}/subtitles/download`, {
        params: { file_id: s.file_id },
        responseType: "blob",
      });
      const blob = new Blob([r.data], { type: "application/x-subrip" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = s.file_name || `${s.file_id}.srt`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Download iniciado.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl bg-slate-900 border-slate-800 text-slate-100"
        data-testid="subtitle-dialog"
      >
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">
            {t(lang, "subtitles.title")}
          </DialogTitle>
          <DialogDescription className="text-slate-400">
            OpenSubtitles
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 sm:grid-cols-[1fr_180px_auto] gap-3 mt-2">
          <div>
            <Label className="text-xs text-slate-400">{t(lang, "subtitles.query")}</Label>
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ex: Inception"
              onKeyDown={(e) => e.key === "Enter" && doSearch()}
              className="bg-slate-800/60 border-slate-700"
              data-testid="subtitle-query-input"
            />
          </div>
          <div>
            <Label className="text-xs text-slate-400">{t(lang, "subtitles.language")}</Label>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger
                className="bg-slate-800/60 border-slate-700"
                data-testid="subtitle-language-select"
              >
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
          <div className="flex items-end">
            <Button
              onClick={() => doSearch()}
              disabled={loading || !query.trim()}
              className="w-full bg-amber-500 hover:bg-amber-400 text-slate-900 font-semibold"
              data-testid="subtitle-search-btn"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <SearchIcon className="w-4 h-4" />}
              <span className="ml-1.5">{t(lang, "subtitles.cta")}</span>
            </Button>
          </div>
        </div>

        <div className="mt-4 max-h-[55vh] overflow-y-auto pr-1">
          {loading ? (
            <div className="space-y-2">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-16 w-full bg-slate-800" />
              ))}
            </div>
          ) : !searched ? (
            <p className="text-slate-500 text-sm py-8 text-center">
              {t(lang, "subtitles.empty")}
            </p>
          ) : results.length === 0 ? (
            <p className="text-slate-500 text-sm py-8 text-center" data-testid="subtitle-empty">
              {t(lang, "subtitles.noResults")}
            </p>
          ) : (
            <ul className="space-y-2" data-testid="subtitle-results">
              {results.map((s) => (
                <li
                  key={s.id}
                  className="border border-slate-800 rounded-lg p-3 flex items-center gap-3 hover:border-amber-500/40 transition-colors"
                  data-testid={`subtitle-item-${s.id}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline" className="border-slate-700 text-slate-300 text-[10px] uppercase">
                        {s.language}
                      </Badge>
                      <p className="font-medium text-sm text-slate-100 truncate">{s.file_name}</p>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-400 mt-1">
                      <span>{s.download_count} {t(lang, "subtitles.downloads")}</span>
                      {s.rating > 0 && (
                        <span className="flex items-center gap-1">
                          <Star className="w-3 h-3" /> {s.rating.toFixed(1)}
                        </span>
                      )}
                      {s.uploader && <span className="truncate">@{s.uploader}</span>}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => downloadSub(s)}
                    disabled={!s.file_id}
                    className="bg-amber-500 hover:bg-amber-400 text-slate-900 font-semibold"
                    data-testid={`subtitle-download-${s.id}`}
                  >
                    <Download className="w-4 h-4 mr-1" />
                    {t(lang, "subtitles.download")}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SubtitleDialog;
