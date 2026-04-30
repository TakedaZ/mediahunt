"""MediaHunt backend - FastAPI server.

Provides torrent search (YTS, Nyaa, 1337x), subtitle search via OpenSubtitles,
and persistent configuration stored both in MongoDB and a mirrored
config.json file for Docker volume compatibility.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import feedparser
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ---------------------------------------------------------------------------
# Configuration paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(os.environ.get("MEDIAHUNT_DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "api_keys": {
        "opensubtitles": os.environ.get("OPENSUBTITLES_API_KEY", ""),
        "qbittorrent_url": "",
        "qbittorrent_user": "",
        "qbittorrent_pass": "",
    },
    "search_preferences": {
        "default_language": "any",
        "default_quality": "any",
        "default_type": "any",
        "max_results": 20,
    },
    "sources": {
        "yts": {"enabled": True, "priority": 1},
        "nyaa": {"enabled": True, "priority": 2},
        "1337x": {"enabled": True, "priority": 3},
    },
    "subtitle_preferences": {
        "default_language": "pt-br",
        "preferred_format": "any",
    },
    "interface": {
        "theme": "dark",
        "language": "pt",
    },
}

# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

logger = logging.getLogger("mediahunt")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="MediaHunt", version="1.0.0")
api_router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TorrentResult(BaseModel):
    id: str
    title: str
    year: Optional[int] = None
    quality: Optional[str] = None
    size: Optional[str] = None
    seeders: Optional[int] = 0
    leechers: Optional[int] = 0
    source: str
    magnet: Optional[str] = None
    torrent_url: Optional[str] = None
    poster: Optional[str] = None
    type: Optional[str] = None
    language_hint: Optional[str] = None


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


class SettingsModel(BaseModel):
    api_keys: dict[str, str] = Field(default_factory=dict)
    search_preferences: dict[str, Any] = Field(default_factory=dict)
    sources: dict[str, Any] = Field(default_factory=dict)
    subtitle_preferences: dict[str, Any] = Field(default_factory=dict)
    interface: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


async def load_settings() -> dict[str, Any]:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    # Read from disk first (Docker volume canonical source)
    if CONFIG_FILE.exists():
        try:
            cfg = _deep_merge(cfg, json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed reading config.json: %s", exc)
    # Then override with Mongo (for hosted env where volume isn't shared)
    doc = await db.app_config.find_one({"_id": "singleton"}, {"_id": 0})
    if doc:
        cfg = _deep_merge(cfg, doc)
    return cfg


async def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = await load_settings()
    merged = _deep_merge(current, payload)
    # Persist to Mongo
    await db.app_config.update_one(
        {"_id": "singleton"},
        {"$set": {**merged, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    # Mirror to disk for Docker volume parity
    try:
        CONFIG_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed writing config.json: %s", exc)
    return merged


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def http_client(timeout: float = 12.0, browser_like: bool = False) -> httpx.AsyncClient:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9,pt;q=0.8",
    }
    if browser_like:
        headers.update({
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })
    return httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# Quality / language helpers
# ---------------------------------------------------------------------------

QUALITY_PATTERNS = {
    "4k": ["2160p", "4k", "uhd"],
    "1080p": ["1080p", "fullhd", "full hd"],
    "720p": ["720p", "hd"],
}

LANGUAGE_PATTERNS = {
    "dubbed_pt_br": ["dublado", "dub pt", "pt-br dub", "dual áudio", "dual audio", "dual.audio", "nacional"],
    "subbed": ["legendado", "subbed", "softsub", "hardsub", "sub pt", "leg pt"],
    "original_en": ["english", "eng", "original"],
}


def detect_quality(text: str) -> Optional[str]:
    t = text.lower()
    for label, patterns in QUALITY_PATTERNS.items():
        for p in patterns:
            if p in t:
                return label
    return None


def matches_quality(text: str, wanted: str) -> bool:
    if not wanted or wanted == "any":
        return True
    detected = detect_quality(text)
    return detected == wanted


def matches_language(text: str, wanted: str) -> bool:
    if not wanted or wanted == "any":
        return True
    t = text.lower()
    patterns = LANGUAGE_PATTERNS.get(wanted, [])
    if wanted == "original_en":
        # Heuristic: if no explicit dubbed/subbed marker, assume original english
        if any(p in t for p in LANGUAGE_PATTERNS["dubbed_pt_br"] + LANGUAGE_PATTERNS["subbed"]):
            return False
        return True
    return any(p in t for p in patterns)


# ---------------------------------------------------------------------------
# Source: YTS
# ---------------------------------------------------------------------------


async def search_yts(query: str, quality: str, limit: int) -> list[TorrentResult]:
    params = {"query_term": query, "limit": min(limit, 50)}
    if quality and quality != "any":
        yts_q = {"4k": "2160p", "1080p": "1080p", "720p": "720p"}.get(quality)
        if yts_q:
            params["quality"] = yts_q
    url = "https://yts.mx/api/v2/list_movies.json"
    try:
        async with http_client() as cli:
            r = await cli.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.warning("YTS error: %s", exc)
        return []

    results: list[TorrentResult] = []
    movies = (data.get("data", {}) or {}).get("movies") or []
    for m in movies:
        poster = m.get("medium_cover_image") or m.get("large_cover_image")
        for t in m.get("torrents", []):
            qlabel = t.get("quality", "")
            normalized_q = "4k" if qlabel == "2160p" else qlabel.lower()
            magnet = build_magnet(t.get("hash"), m.get("title_long") or m.get("title"),
                                  ["udp://open.demonii.com:1337/announce",
                                   "udp://tracker.openbittorrent.com:80",
                                   "udp://tracker.coppersurfer.tk:6969",
                                   "udp://glotorrents.pw:6969/announce",
                                   "udp://tracker.opentrackr.org:1337/announce"])
            results.append(TorrentResult(
                id=f"yts-{m.get('id')}-{t.get('hash')}",
                title=m.get("title_long") or m.get("title", "Untitled"),
                year=m.get("year"),
                quality=normalized_q,
                size=t.get("size"),
                seeders=t.get("seeds", 0),
                leechers=t.get("peers", 0),
                source="YTS",
                magnet=magnet,
                torrent_url=t.get("url"),
                poster=poster,
                type="movie",
                language_hint="original_en",
            ))
    return results


def build_magnet(infohash: str, name: str, trackers: list[str]) -> str:
    if not infohash:
        return ""
    encoded_name = urllib.parse.quote(name or "")
    base = f"magnet:?xt=urn:btih:{infohash}&dn={encoded_name}"
    for t in trackers:
        base += f"&tr={urllib.parse.quote(t)}"
    return base


# ---------------------------------------------------------------------------
# Source: Nyaa.si (RSS)
# ---------------------------------------------------------------------------


async def search_nyaa(query: str, limit: int) -> list[TorrentResult]:
    params = {"page": "rss", "q": query, "c": "1_2", "f": "0"}
    url = "https://nyaa.si/"
    try:
        async with http_client() as cli:
            r = await cli.get(url, params=params)
            r.raise_for_status()
            text = r.text
    except Exception as exc:
        logger.warning("Nyaa error: %s", exc)
        return []

    feed = feedparser.parse(text)
    results: list[TorrentResult] = []
    for i, entry in enumerate(feed.entries[: limit * 2]):
        title = entry.get("title", "")
        seeders = int(entry.get("nyaa_seeders", 0) or 0)
        leechers = int(entry.get("nyaa_leechers", 0) or 0)
        size = entry.get("nyaa_size", "")
        link = entry.get("link", "")
        info_hash = entry.get("nyaa_infohash", "")
        guid = entry.get("guid") or entry.get("id") or f"nyaa-{i}"
        magnet = build_magnet(info_hash, title, [
            "udp://tracker.opentrackr.org:1337/announce",
            "udp://exodus.desync.com:6969/announce",
            "udp://tracker.coppersurfer.tk:6969/announce",
        ]) if info_hash else None
        results.append(TorrentResult(
            id=f"nyaa-{guid}",
            title=title,
            quality=detect_quality(title),
            size=size,
            seeders=seeders,
            leechers=leechers,
            source="Nyaa",
            magnet=magnet,
            torrent_url=link,
            poster=None,
            type="anime",
            language_hint=None,
        ))
        if len(results) >= limit:
            break
    return results


# ---------------------------------------------------------------------------
# Source: 1337x (scraping)
# ---------------------------------------------------------------------------

X1337_BASE = "https://1337x.to"


async def search_1337x(query: str, limit: int) -> list[TorrentResult]:
    q = urllib.parse.quote(query)
    url = f"{X1337_BASE}/search/{q}/1/"
    try:
        async with http_client(browser_like=True) as cli:
            r = await cli.get(url)
            if r.status_code != 200:
                return []
            soup = BeautifulSoup(r.text, "lxml")
    except Exception as exc:
        logger.warning("1337x list error: %s", exc)
        return []

    rows = soup.select("table.table-list tbody tr")[:limit]
    if not rows:
        return []

    async def fetch_detail(row) -> Optional[TorrentResult]:
        try:
            name_a = row.select_one("td.coll-1.name a:nth-of-type(2)")
            if not name_a:
                return None
            title = name_a.get_text(strip=True)
            href = name_a.get("href", "")
            seeders = int(row.select_one("td.coll-2").get_text(strip=True) or 0)
            leechers = int(row.select_one("td.coll-3").get_text(strip=True) or 0)
            size_cell = row.select_one("td.coll-4")
            size_text = size_cell.contents[0].strip() if size_cell and size_cell.contents else ""
            detail_url = X1337_BASE + href
            async with http_client(browser_like=True) as cli:
                dr = await cli.get(detail_url)
                if dr.status_code != 200:
                    return None
                dsoup = BeautifulSoup(dr.text, "lxml")
            magnet_link = None
            for a in dsoup.select("a"):
                h = a.get("href", "")
                if h.startswith("magnet:"):
                    magnet_link = h
                    break
            poster = None
            poster_img = dsoup.select_one(".torrent-image img") or dsoup.select_one("div.torrent-detail img")
            if poster_img and poster_img.get("src"):
                src = poster_img["src"]
                poster = src if src.startswith("http") else "https:" + src
            return TorrentResult(
                id=f"1337x-{href.strip('/').replace('/', '-')}",
                title=title,
                quality=detect_quality(title),
                size=size_text,
                seeders=seeders,
                leechers=leechers,
                source="1337x",
                magnet=magnet_link,
                torrent_url=detail_url,
                poster=poster,
                type=None,
                language_hint=None,
            )
        except Exception as exc:
            logger.debug("1337x detail error: %s", exc)
            return None

    coros = [fetch_detail(row) for row in rows]
    detailed = await asyncio.gather(*coros)
    return [d for d in detailed if d is not None]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@api_router.get("/")
async def root():
    return {"app": "MediaHunt", "status": "ok"}


@api_router.get("/settings", response_model=SettingsModel)
async def get_settings_endpoint():
    cfg = await load_settings()
    return SettingsModel(**cfg)


@api_router.post("/settings", response_model=SettingsModel)
async def update_settings_endpoint(payload: SettingsModel):
    merged = await save_settings(payload.model_dump(exclude_unset=False))
    return SettingsModel(**merged)


@api_router.get("/settings/test-connection")
async def test_opensubtitles(api_key: Optional[str] = None):
    cfg = await load_settings()
    raw = api_key if api_key is not None else cfg["api_keys"].get("opensubtitles", "")
    key = (raw or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="OpenSubtitles API key não configurada")
    headers = {
        "Api-Key": key,
        "User-Agent": "MediaHunt v1.0",
        "Accept": "application/json",
    }
    # Use an endpoint that actually validates the Api-Key. /subtitles requires a
    # valid key and returns 401 for invalid ones (the /infos/* endpoints are
    # public and would always succeed).
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
            return {"success": False, "message": f"Falha: HTTP {r.status_code}", "detail": r.text[:200]}
    except Exception as exc:
        return {"success": False, "message": f"Erro de conexão: {exc}"}


@api_router.get("/search/torrents")
async def search_torrents(
    query: str = Query(..., min_length=1),
    type: str = Query("any"),
    language: str = Query("any"),
    quality: str = Query("any"),
    max_results: int = Query(20, ge=1, le=100),
):
    cfg = await load_settings()
    sources = cfg["sources"]
    enabled = [(name, conf) for name, conf in sources.items() if conf.get("enabled")]
    enabled.sort(key=lambda x: x[1].get("priority", 99))

    per_source = max(5, max_results)
    tasks = []
    routing = {
        "yts": lambda: search_yts(query, quality, per_source),
        "nyaa": lambda: search_nyaa(query, per_source),
        "1337x": lambda: search_1337x(query, per_source),
    }

    # Type-aware routing
    type_lc = (type or "any").lower()
    selected_names: list[str] = []
    for name, _ in enabled:
        if type_lc == "movie" and name == "nyaa":
            continue
        if type_lc == "anime" and name not in ("nyaa",):
            # prefer nyaa for anime
            continue
        if type_lc == "series" and name == "yts":
            continue
        selected_names.append(name)
    # Fallback if filtering left nothing
    if not selected_names:
        selected_names = [n for n, _ in enabled]

    for name in selected_names:
        if name in routing:
            tasks.append(routing[name]())

    gathered = await asyncio.gather(*tasks, return_exceptions=True)
    results: list[TorrentResult] = []
    for g in gathered:
        if isinstance(g, list):
            results.extend(g)

    # Apply quality + language filters (if not already strict)
    def keep(r: TorrentResult) -> bool:
        text = f"{r.title} {r.quality or ''}"
        if quality != "any" and not matches_quality(text, quality):
            return False
        if language != "any" and r.source == "YTS" and language != "original_en":
            return False
        if language != "any" and r.source != "YTS":
            if not matches_language(r.title, language):
                return False
        return True

    filtered = [r for r in results if keep(r)]
    # Sort by seeders desc within source priority
    priority_map = {name: conf.get("priority", 99) for name, conf in sources.items()}
    src_key = {"YTS": "yts", "Nyaa": "nyaa", "1337x": "1337x"}
    filtered.sort(key=lambda r: (priority_map.get(src_key.get(r.source, ""), 99),
                                 -(r.seeders or 0)))
    filtered = filtered[:max_results]
    return {"query": query, "count": len(filtered), "results": [r.model_dump() for r in filtered]}


# ---------------------------------------------------------------------------
# Subtitles
# ---------------------------------------------------------------------------

OS_LANG_MAP = {
    "pt-br": "pt-br",
    "pt": "pt-pt",
    "en": "en",
    "es": "es",
}


@api_router.get("/search/subtitles")
async def search_subtitles(
    query: str = Query(..., min_length=1),
    language: str = Query("pt-br"),
):
    cfg = await load_settings()
    key = cfg["api_keys"].get("opensubtitles", "")
    if not key:
        raise HTTPException(status_code=400,
                            detail="API key do OpenSubtitles não configurada. Vá em Configurações.")
    lang = OS_LANG_MAP.get(language, language)
    params = {"query": query, "languages": lang}
    headers = {
        "Api-Key": key,
        "User-Agent": "MediaHunt v1.0",
        "Accept": "application/json",
    }
    try:
        async with http_client(timeout=12.0) as cli:
            r = await cli.get("https://api.opensubtitles.com/api/v1/subtitles",
                              params=params, headers=headers)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code,
                                    detail=f"OpenSubtitles: {r.text[:200]}")
            data = r.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro: {exc}")

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
    return {"query": query, "language": lang, "count": len(out),
            "results": [s.model_dump() for s in out]}


@api_router.get("/subtitles/download")
async def download_subtitle(file_id: int = Query(...)):
    cfg = await load_settings()
    key = cfg["api_keys"].get("opensubtitles", "")
    if not key:
        raise HTTPException(status_code=400, detail="API key do OpenSubtitles não configurada.")
    headers = {
        "Api-Key": key,
        "User-Agent": "MediaHunt v1.0",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        async with http_client(timeout=15.0) as cli:
            r = await cli.post("https://api.opensubtitles.com/api/v1/download",
                               headers=headers, json={"file_id": file_id})
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code,
                                    detail=f"OpenSubtitles: {r.text[:200]}")
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

    safe_name = re.sub(r"[^A-Za-z0-9_.\-]", "_", file_name) or f"{file_id}.srt"
    return Response(
        content=content,
        media_type="application/x-subrip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@api_router.get("/torrent/proxy")
async def proxy_torrent(url: str = Query(...)):
    """Proxy a .torrent file download to bypass CORS for direct download buttons."""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL inválida.")
    try:
        async with http_client(timeout=15.0) as cli:
            r = await cli.get(url)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail="Falha no upstream.")
            content_type = r.headers.get("content-type", "application/x-bittorrent")
            filename = url.rsplit("/", 1)[-1].split("?")[0] or "file.torrent"
            safe_name = re.sub(r"[^A-Za-z0-9_.\-]", "_", filename)
            return Response(
                content=r.content,
                media_type=content_type,
                headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro: {exc}")


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    # Ensure config exists on disk
    if not CONFIG_FILE.exists():
        await save_settings({})
    logger.info("MediaHunt ready. Config: %s", CONFIG_FILE)


@app.on_event("shutdown")
async def _shutdown():
    client.close()
