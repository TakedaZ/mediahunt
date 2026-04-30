#!/usr/bin/env sh
set -e

# Run a tiny static server in front of FastAPI is overkill — use FastAPI itself
# via uvicorn, with a small wrapper that mounts the static build at "/".

cat > /app/backend/_static_mount.py <<'PY'
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from server import app

BUILD_DIR = Path("/app/frontend/build")
if BUILD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(BUILD_DIR / "static")), name="static")

    @app.get("/{full_path:path}")
    async def spa_catchall(full_path: str):
        candidate = BUILD_DIR / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(BUILD_DIR / "index.html"))
PY

exec uvicorn _static_mount:app --host 0.0.0.0 --port "${PORT:-5556}" --app-dir /app/backend
