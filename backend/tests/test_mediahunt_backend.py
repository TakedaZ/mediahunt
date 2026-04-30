"""MediaHunt backend tests — covers root, settings persistence, search, subtitles, proxy."""

import json
import os
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://media-seeker-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
CONFIG_FILE = Path("/app/data/config.json")


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module", autouse=True)
def _reset_key_after(client):
    """Ensure key is empty before & after the module run."""
    try:
        client.post(f"{API}/settings", json={"api_keys": {"opensubtitles": ""}}, timeout=20)
    except Exception:
        pass
    yield
    try:
        client.post(f"{API}/settings", json={"api_keys": {"opensubtitles": ""}}, timeout=20)
    except Exception:
        pass


# ---------- Root ----------
def test_root(client):
    r = client.get(f"{API}/", timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert data == {"app": "MediaHunt", "status": "ok"}


# ---------- Settings ----------
def test_settings_default_shape(client):
    r = client.get(f"{API}/settings", timeout=20)
    assert r.status_code == 200
    data = r.json()
    for key in ["api_keys", "search_preferences", "sources", "subtitle_preferences", "interface"]:
        assert key in data, f"missing key {key}"
    # sources must contain yts/nyaa/1337x with priority+enabled
    for src in ["yts", "nyaa", "1337x"]:
        assert src in data["sources"]
        assert "priority" in data["sources"][src]
        assert "enabled" in data["sources"][src]


def test_settings_deep_merge_and_disk_persistence(client):
    # POST partial payload — only update interface.theme, keep other keys intact
    payload = {"interface": {"theme": "dark", "language": "pt"},
               "search_preferences": {"max_results": 25}}
    r = client.post(f"{API}/settings", json=payload, timeout=20)
    assert r.status_code == 200
    merged = r.json()
    assert merged["interface"]["theme"] == "dark"
    assert merged["interface"]["language"] == "pt"
    assert merged["search_preferences"]["max_results"] == 25
    # Other defaults preserved
    assert "yts" in merged["sources"]

    # GET reflects merge
    r2 = client.get(f"{API}/settings", timeout=20)
    assert r2.status_code == 200
    assert r2.json()["search_preferences"]["max_results"] == 25

    # Disk file mirror
    assert CONFIG_FILE.exists(), f"{CONFIG_FILE} should exist"
    disk = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    assert disk["interface"]["theme"] == "dark"
    assert disk["search_preferences"]["max_results"] == 25


def test_settings_persistence_api_key_then_reset(client):
    # Persist key
    r = client.post(f"{API}/settings",
                    json={"api_keys": {"opensubtitles": "persistent_test_key_999"}},
                    timeout=20)
    assert r.status_code == 200
    assert r.json()["api_keys"]["opensubtitles"] == "persistent_test_key_999"

    # GET reflects
    g = client.get(f"{API}/settings", timeout=20)
    assert g.json()["api_keys"]["opensubtitles"] == "persistent_test_key_999"

    # Disk reflects
    disk = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    assert disk["api_keys"]["opensubtitles"] == "persistent_test_key_999"

    # Reset to empty
    r2 = client.post(f"{API}/settings",
                     json={"api_keys": {"opensubtitles": ""}}, timeout=20)
    assert r2.status_code == 200
    assert r2.json()["api_keys"]["opensubtitles"] == ""
    disk2 = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    assert disk2["api_keys"]["opensubtitles"] == ""


# ---------- Search torrents ----------
def test_search_missing_query_422(client):
    r = client.get(f"{API}/search/torrents", timeout=20)
    assert r.status_code == 422


def test_search_anime_nyaa_returns_results(client):
    r = client.get(f"{API}/search/torrents",
                   params={"query": "naruto", "type": "anime", "max_results": 5},
                   timeout=60)
    assert r.status_code == 200
    data = r.json()
    assert data["query"] == "naruto"
    assert "count" in data
    assert isinstance(data["results"], list)
    # Nyaa is reachable from this pod — expect at least 1 result
    assert data["count"] >= 1, f"Expected >=1 results from Nyaa, got {data}"
    first = data["results"][0]
    for k in ["id", "title", "source"]:
        assert k in first
    # at least one result should have a magnet link
    assert any(r.get("magnet") for r in data["results"]), "No magnet on any anime result"


def test_search_movie_yts_graceful(client):
    """yts.mx DNS may be blocked — endpoint must still 200."""
    r = client.get(f"{API}/search/torrents",
                   params={"query": "matrix", "type": "movie", "max_results": 5},
                   timeout=60)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert isinstance(data["results"], list)


def test_search_series_1337x_graceful(client):
    """1337x may return 403 Cloudflare — endpoint must still 200."""
    r = client.get(f"{API}/search/torrents",
                   params={"query": "breaking bad", "type": "series", "max_results": 5},
                   timeout=60)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["results"], list)


# ---------- OpenSubtitles ----------
def test_test_connection_no_key(client):
    r = client.get(f"{API}/settings/test-connection", timeout=20)
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "configurada" in detail.lower() or "n\u00e3o configurada" in detail.lower()


def test_test_connection_invalid_key(client):
    r = client.get(f"{API}/settings/test-connection",
                   params={"api_key": "invalid_dummy_key_xyz123"}, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is False


def test_search_subtitles_no_key(client):
    r = client.get(f"{API}/search/subtitles",
                   params={"query": "inception", "language": "pt-br"}, timeout=20)
    assert r.status_code == 400
    assert "OpenSubtitles" in r.json().get("detail", "")


def test_download_subtitle_no_key(client):
    r = client.get(f"{API}/subtitles/download", params={"file_id": 1}, timeout=20)
    assert r.status_code == 400
    assert "OpenSubtitles" in r.json().get("detail", "")


# ---------- Torrent proxy ----------
def test_torrent_proxy_ok(client):
    r = client.get(f"{API}/torrent/proxy",
                   params={"url": "https://httpbin.org/robots.txt"}, timeout=30)
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "").lower()
    assert b"User-agent" in r.content or len(r.content) > 0


def test_torrent_proxy_invalid_scheme(client):
    r = client.get(f"{API}/torrent/proxy",
                   params={"url": "ftp://invalid"}, timeout=20)
    assert r.status_code == 400
    assert "URL inv" in r.json().get("detail", "")
