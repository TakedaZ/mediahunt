from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import unicodedata
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import feedparser
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query, Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
DATA_DIR = Path(os.environ.get("MEDIAHUNT_DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_EQUIVALENCES = {
    "bob esponja": "spongebob",
    "como treinar seu dragao": "how to train your dragon",
    "homem aranha": "spider man",
    "velozes e furiosos": "fast and furious",
}

DEFAULT_CONFIG: dict[str, Any] = {
    "api_keys": {"opensubtitles": os.environ.get("OPENSUBTITLES_API_KEY", ""), "qbittorrent_url": "", "qbittorrent_user": "", "qbittorrent_pass": ""},
    "search_preferences": {"default_language": "any", "default_quality": "any", "default_type": "any", "max_results": 20, "aliases": {}, "source_type_categories": {"movie": ["movie"], "series": ["series"], "anime": ["anime"]}},
    "sources": {"yts": {"enabled": True, "priority": 1}, "nyaa": {"enabled": True, "priority": 2}, "1337x": {"enabled": True, "priority": 3}},
    "custom_sources": [],
    "subtitle_preferences": {"default_language": "pt-br", "preferred_format": "any"},
    "interface": {"theme": "dark", "language": "pt"},
}

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
logger = logging.getLogger("mediahunt")
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="MediaHunt", version="1.1.0")
api_router = APIRouter(prefix="/api")

class TorrentResult(BaseModel):
    id: str; title: str; year: Optional[int] = None; quality: Optional[str] = None; size: Optional[str] = None
    seeders: Optional[int] = 0; leechers: Optional[int] = 0; source: str; magnet: Optional[str] = None
    torrent_url: Optional[str] = None; poster: Optional[str] = None; type: Optional[str] = None; language_hint: Optional[str] = None

class SettingsModel(BaseModel):
    api_keys: dict[str, str] = Field(default_factory=dict)
    search_preferences: dict[str, Any] = Field(default_factory=dict)
    sources: dict[str, Any] = Field(default_factory=dict)
    custom_sources: list[dict[str, Any]] = Field(default_factory=list)
    subtitle_preferences: dict[str, Any] = Field(default_factory=dict)
    interface: dict[str, Any] = Field(default_factory=dict)

class SubtitleResult(BaseModel):
    id: str
    file_id: Optional[int] = None
    file_name: str
    language: str
    download_count: int = 0
    rating: float = 0.0
    release: Optional[str] = None
    format: Optional[str] = None
    uploader: Optional[str] = None


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        out[k] = _deep_merge(out.get(k, {}), v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out

async def load_settings() -> dict[str, Any]:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_FILE.exists():
        cfg = _deep_merge(cfg, json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    doc = await db.app_config.find_one({"_id": "singleton"}, {"_id": 0})
    if doc: cfg = _deep_merge(cfg, doc)
    return cfg

async def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_merge(await load_settings(), payload)
    await db.app_config.update_one({"_id": "singleton"}, {"$set": {**merged, "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    CONFIG_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    return merged

USER_AGENT = "Mozilla/5.0"
def http_client(timeout: float = 12.0, browser_like: bool = False) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9,pt;q=0.8"}, follow_redirects=True)

def normalize_query(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "")).encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()

def expand_query(query: str, aliases: dict[str, Any]) -> list[str]:
    base = normalize_query(query)
    vals = {query.strip(), base}
    if base in DEFAULT_EQUIVALENCES: vals.add(DEFAULT_EQUIVALENCES[base])
    for k, v in (aliases or {}).items():
        nk = normalize_query(k)
        vlist = v if isinstance(v, list) else [v]
        if nk == base:
            vals.update([x for x in vlist if isinstance(x, str)])
    return [x for x in vals if x]

def score_result(result: TorrentResult, expanded_queries: list[str], wanted_quality: str, source_priority: int) -> float:
    title = normalize_query(result.title)
    title_boost = max((100 if normalize_query(q) in title else 0) for q in expanded_queries) if expanded_queries else 0
    quality_boost = 20 if wanted_quality != "any" and (result.quality or "").lower() == wanted_quality.lower() else 0
    seeder_boost = min((result.seeders or 0), 500) / 5
    priority_boost = max(0, 25 - source_priority * 4)
    return title_boost + quality_boost + seeder_boost + priority_boost

def dedupe_results(results: list[TorrentResult]) -> list[TorrentResult]:
    best = {}
    for r in results:
        key = normalize_query(f"{r.title} {r.quality or ''} {r.size or ''}")
        if key not in best or (r.seeders or 0) > (best[key].seeders or 0): best[key] = r
    return list(best.values())

async def search_yts(query: str, quality: str, limit: int) -> list[TorrentResult]:
    data = None
    yts_endpoints = [
        "https://yts.mx/api/v2/list_movies.json",
        "https://yts.rs/api/v2/list_movies.json",
        "https://yts.am/api/v2/list_movies.json",
    ]
    last_error: Optional[Exception] = None
    for endpoint in yts_endpoints:
        try:
            async with http_client() as cli:
                r = await cli.get(endpoint, params={"query_term": query, "limit": min(limit, 50)})
                r.raise_for_status()
                data = r.json()
                break
        except Exception as exc:
            last_error = exc
            continue
    if data is None:
        if last_error:
            raise RuntimeError(f"YTS indisponível por erro de rede/DNS: {last_error}")
        raise RuntimeError("YTS indisponível no momento.")
    out=[]
    for m in ((data.get("data", {}) or {}).get("movies") or []):
        for t in m.get("torrents", []):
            out.append(TorrentResult(id=f"yts-{m.get('id')}-{t.get('hash')}", title=m.get("title_long") or m.get("title", "Untitled"), year=m.get("year"), quality=("4k" if t.get("quality")=="2160p" else (t.get("quality") or "").lower()), size=t.get("size"), seeders=t.get("seeds",0), leechers=t.get("peers",0), source="YTS", torrent_url=t.get("url"), type="movie", language_hint="original_en"))
    return out

async def search_nyaa(query: str, limit: int) -> list[TorrentResult]:
    try:
        async with http_client() as cli:
            r = await cli.get("https://nyaa.si/", params={"page":"rss","q":query,"c":"0_0","f":"0"}); r.raise_for_status()
    except Exception as exc: raise RuntimeError(f"Nyaa indisponível: {exc}")
    feed=feedparser.parse(r.text); out=[]
    for i,e in enumerate(feed.entries[:limit]): out.append(TorrentResult(id=f"nyaa-{e.get('id') or i}", title=e.get("title",""), quality=None,size=e.get("nyaa_size",""),seeders=int(e.get("nyaa_seeders",0) or 0),leechers=int(e.get("nyaa_leechers",0) or 0),source="Nyaa",torrent_url=e.get("link"),type="anime"))
    return out

async def search_1337x(query: str, limit: int) -> list[TorrentResult]:
    url=f"https://1337x.to/search/{urllib.parse.quote(query)}/1/"
    try:
        async with http_client(browser_like=True) as cli:
            r=await cli.get(url)
            if r.status_code==403: raise PermissionError("1337x bloqueou a consulta. Desative esta fonte ou use uma fonte RSS/Torznab customizada.")
            r.raise_for_status()
    except PermissionError: raise
    except Exception as exc: raise RuntimeError(f"1337x indisponível: {exc}")
    soup=BeautifulSoup(r.text,"lxml"); out=[]
    for i,row in enumerate(soup.select("table.table-list tbody tr")[:limit]):
        a=row.select_one("td.coll-1.name a:nth-of-type(2)");
        if not a: continue
        out.append(TorrentResult(id=f"1337x-{i}",title=a.get_text(strip=True),seeders=int(row.select_one("td.coll-2").get_text(strip=True) or 0),leechers=int(row.select_one("td.coll-3").get_text(strip=True) or 0),source="1337x"))
    return out

async def search_custom_source(src: dict[str, Any], query: str, limit: int) -> list[TorrentResult]:
    base = (src.get("base_url") or "").strip(); stype = src.get("source_type", "rss")
    if not base: return []
    url = f"{base}&q={urllib.parse.quote(query)}" if stype == "torznab" and "?" in base else (f"{base}?q={urllib.parse.quote(query)}" if stype=="torznab" else base)
    async with http_client() as cli:
        r = await cli.get(url); r.raise_for_status()
    feed = feedparser.parse(r.text); out=[]
    for i,e in enumerate(feed.entries[:limit]): out.append(TorrentResult(id=f"custom-{src.get('name','src')}-{i}", title=e.get("title",""), source=src.get("name","Custom"), seeders=0, leechers=0, torrent_url=e.get("link")))
    return out


async def run_source_with_fallback_queries(
    source_runner,
    queries: list[str],
    source_name: str,
) -> tuple[list[TorrentResult], Optional[str]]:
    """Try expanded queries for one source, stopping after first non-empty result.

    Keeps at most one warning per source to avoid duplicated UI messages.
    """
    last_warning: Optional[str] = None
    for q in queries:
        try:
            results = await source_runner(q)
            if results:
                return results, None
        except Exception as exc:
            last_warning = str(exc)
    if last_warning:
        return [], last_warning
    return [], None

@api_router.get("/settings", response_model=SettingsModel)
async def get_settings_endpoint(): return SettingsModel(**(await load_settings()))
@api_router.post("/settings", response_model=SettingsModel)
async def update_settings_endpoint(payload: SettingsModel): return SettingsModel(**(await save_settings(payload.model_dump(exclude_unset=False))))

@api_router.get("/settings/test-connection")
async def test_opensubtitles(api_key: Optional[str] = None):
    cfg = await load_settings()
    key = (api_key if api_key is not None else cfg["api_keys"].get("opensubtitles", "")).strip()
    if not key:
        raise HTTPException(status_code=400, detail="OpenSubtitles API key não configurada")
    headers = {"Api-Key": key, "User-Agent": "MediaHunt v1.1", "Accept": "application/json"}
    try:
        async with http_client(timeout=8.0) as cli:
            r = await cli.get(
                "https://api.opensubtitles.com/api/v1/subtitles",
                headers=headers,
                params={"query": "test", "languages": "en", "page": 1},
            )
        if r.status_code == 200:
            return {"success": True, "message": "Conexão estabelecida com OpenSubtitles."}
        if r.status_code in (401, 403):
            return {"success": False, "message": "API key inválida ou sem permissão."}
        return {"success": False, "message": f"Falha: HTTP {r.status_code}"}
    except Exception as exc:
        return {"success": False, "message": f"Erro de conexão: {exc}"}

@api_router.get('/search/torrents')
async def search_torrents(query:str=Query(...), type:str="any", language:str="any", quality:str="any", max_results:int=20):
    cfg = await load_settings(); warnings=[]
    expanded = expand_query(query, cfg.get("search_preferences", {}).get("aliases", {}))
    expanded = list(dict.fromkeys([q for q in expanded if q.strip()]))
    sources = cfg.get("sources", {})
    enabled = [(n,c) for n,c in sources.items() if c.get("enabled")]
    enabled.sort(key=lambda x: x[1].get("priority",99))
    results=[]
    for n, _ in enabled:
        if n == "yts":
            src_results, warning = await run_source_with_fallback_queries(
                lambda q: search_yts(q, quality, max_results), expanded, "YTS"
            )
        elif n == "nyaa":
            src_results, warning = await run_source_with_fallback_queries(
                lambda q: search_nyaa(q, max_results), expanded, "Nyaa"
            )
        elif n == "1337x":
            src_results, warning = await run_source_with_fallback_queries(
                lambda q: search_1337x(q, max_results), expanded, "1337x"
            )
        else:
            src_results, warning = [], None
        results.extend(src_results)
        if warning:
            warnings.append(warning)

    for cs in cfg.get("custom_sources", []):
        if not cs.get("enabled"):
            continue
        src_results, warning = await run_source_with_fallback_queries(
            lambda q: search_custom_source(cs, q, max_results),
            expanded,
            cs.get("name", "Fonte customizada"),
        )
        results.extend(src_results)
        if warning:
            warnings.append(warning)

    warnings = list(dict.fromkeys([w.strip() for w in warnings if isinstance(w, str) and w.strip()]))
    deduped = dedupe_results(results)
    prio={k:v.get("priority",99) for k,v in sources.items()}
    deduped.sort(key=lambda r: score_result(r, expanded, quality, prio.get(r.source.lower(),50)), reverse=True)
    return {"query":query,"expanded_queries":expanded,"count":len(deduped[:max_results]),"results":[r.model_dump() for r in deduped[:max_results]],"warnings":warnings}

@api_router.get('/search/subtitles')
async def search_subtitles(query:str, language:str="pt-br"):
    cfg=await load_settings(); key=cfg.get("api_keys",{}).get("opensubtitles","")
    if not key: raise HTTPException(status_code=400, detail="API key do OpenSubtitles não configurada. Configure em Settings ou OPENSUBTITLES_API_KEY.")
    lang_map = {"pt-br": "pt-br", "pt": "pt-pt", "en": "en", "es": "es"}
    lang = lang_map.get(language, language)
    headers = {"Api-Key": key, "User-Agent": "MediaHunt v1.1", "Accept": "application/json"}
    try:
        async with http_client(timeout=12.0) as cli:
            r = await cli.get(
                "https://api.opensubtitles.com/api/v1/subtitles",
                params={"query": query, "languages": lang},
                headers=headers,
            )
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=f"OpenSubtitles: {r.text[:200]}")
        data = r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro de conexão com OpenSubtitles: {exc}")

    out: list[SubtitleResult] = []
    for item in (data.get("data") or [])[:30]:
        attrs = item.get("attributes", {}) or {}
        files = attrs.get("files") or []
        file_id = files[0].get("file_id") if files else None
        file_name = (files[0].get("file_name") if files else None) or attrs.get("release", "subtitle")
        out.append(SubtitleResult(
            id=str(item.get("id", file_id or file_name)),
            file_id=file_id,
            file_name=file_name,
            language=attrs.get("language", lang),
            download_count=attrs.get("download_count", 0) or 0,
            rating=float(attrs.get("ratings", 0) or 0),
            release=attrs.get("release"),
            format=attrs.get("format"),
            uploader=(attrs.get("uploader") or {}).get("name"),
        ))
    return {"query": query, "language": lang, "count": len(out), "results": [s.model_dump() for s in out]}


@api_router.get("/subtitles/download")
async def download_subtitle(file_id: int = Query(...)):
    cfg = await load_settings()
    key = cfg["api_keys"].get("opensubtitles", "")
    if not key:
        raise HTTPException(status_code=400, detail="API key do OpenSubtitles não configurada.")
    headers = {
        "Api-Key": key,
        "User-Agent": "MediaHunt v1.1",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        async with http_client(timeout=15.0) as cli:
            r = await cli.post("https://api.opensubtitles.com/api/v1/download", headers=headers, json={"file_id": file_id})
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=f"OpenSubtitles: {r.text[:200]}")
            payload = r.json()
            link = payload.get("link")
            file_name = payload.get("file_name", f"{file_id}.srt")
            if not link:
                raise HTTPException(status_code=502, detail="Link de download ausente.")
            srt = await cli.get(link)
            srt.raise_for_status()
            content = srt.content
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro de download: {exc}")

    safe_name = re.sub(r"[^A-Za-z0-9_.\\-]", "_", file_name) or f"{file_id}.srt"
    return Response(
        content=content,
        media_type="application/x-subrip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )

app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS","*").split(","), allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def _startup():
    if not CONFIG_FILE.exists(): await save_settings({})

@app.on_event("shutdown")
async def _shutdown(): client.close()
