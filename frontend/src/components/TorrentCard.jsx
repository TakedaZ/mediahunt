import React, { useState } from "react";
import { ArrowDown, ArrowUp, Magnet, Download, MessageSquare, Film } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { toast } from "sonner";
import { useApp, API } from "../context/AppContext";
import { t } from "../lib/i18n";

const PLACEHOLDER =
  "https://images.unsplash.com/photo-1626814026160-2237a95fc5a0?crop=entropy&cs=srgb&fm=jpg&w=400&q=70";

const sourceColor = {
  YTS: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  Nyaa: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  "1337x": "bg-rose-500/15 text-rose-300 border-rose-500/30",
};

const TorrentCard = ({ result, onFindSubtitles }) => {
  const { lang } = useApp();
  const [imgError, setImgError] = useState(false);

  const copyMagnet = async () => {
    if (!result.magnet) {
      toast.error(t(lang, "card.magnetMissing"));
      return;
    }
    try {
      await navigator.clipboard.writeText(result.magnet);
      toast.success(t(lang, "card.magnetCopied"));
    } catch {
      const ta = document.createElement("textarea");
      ta.value = result.magnet;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      toast.success(t(lang, "card.magnetCopied"));
    }
  };

  const downloadTorrent = () => {
    if (!result.torrent_url) {
      toast.error("URL indisponível.");
      return;
    }
    const url = result.torrent_url.startsWith("http")
      ? `${API}/torrent/proxy?url=${encodeURIComponent(result.torrent_url)}`
      : result.torrent_url;
    window.open(url, "_blank", "noopener");
  };

  return (
    <div
      className="group relative rounded-xl overflow-hidden border border-slate-800 bg-slate-900/60 hover:border-amber-500/40 transition-all duration-300 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.5)] hover:shadow-[0_8px_30px_-4px_rgba(245,158,11,0.25)]"
      data-testid={`torrent-card-${result.id}`}
    >
      <div className="aspect-[2/3] relative overflow-hidden bg-slate-800">
        {!imgError && result.poster ? (
          <img
            src={result.poster}
            alt={result.title}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            onError={() => setImgError(true)}
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-800 to-slate-900">
            <Film className="w-16 h-16 text-slate-700" />
          </div>
        )}

        <div className="absolute top-2 left-2 right-2 flex justify-between gap-2 z-10">
          {result.quality && (
            <span
              className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide bg-amber-500 text-slate-900"
              data-testid={`quality-badge-${result.id}`}
            >
              {result.quality}
            </span>
          )}
          <span
            className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${sourceColor[result.source] || "bg-slate-800/80 text-slate-300 border-slate-700"}`}
          >
            {result.source}
          </span>
        </div>

        <div className="absolute inset-0 card-poster-fade pointer-events-none" />

        <div className="absolute bottom-0 left-0 right-0 p-3 z-10">
          <h3 className="font-display font-semibold text-white text-sm leading-tight line-clamp-2">
            {result.title}
            {result.year ? <span className="text-slate-400 font-normal"> · {result.year}</span> : null}
          </h3>
          <div className="mt-2 flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1 text-emerald-400" data-testid={`seeders-${result.id}`}>
              <ArrowUp className="w-3 h-3" />
              {result.seeders ?? 0}
            </span>
            <span className="flex items-center gap-1 text-rose-400" data-testid={`leechers-${result.id}`}>
              <ArrowDown className="w-3 h-3" />
              {result.leechers ?? 0}
            </span>
            {result.size && <span className="text-slate-400 ml-auto">{result.size}</span>}
          </div>
        </div>

        <div className="absolute inset-0 bg-slate-950/90 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col items-stretch justify-center gap-2 p-4 z-20">
          <Button
            size="sm"
            onClick={copyMagnet}
            className="bg-amber-500 hover:bg-amber-400 text-slate-900 font-semibold"
            data-testid={`copy-magnet-${result.id}`}
          >
            <Magnet className="w-4 h-4 mr-1.5" />
            {t(lang, "card.copyMagnet")}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={downloadTorrent}
            className="border-slate-600 hover:bg-slate-800 text-slate-100 hover:text-white"
            data-testid={`download-torrent-${result.id}`}
          >
            <Download className="w-4 h-4 mr-1.5" />
            {t(lang, "card.downloadTorrent")}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onFindSubtitles(result)}
            className="text-slate-300 hover:text-amber-400 hover:bg-slate-800/60"
            data-testid={`find-subtitles-${result.id}`}
          >
            <MessageSquare className="w-4 h-4 mr-1.5" />
            {t(lang, "card.findSubtitles")}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default TorrentCard;
