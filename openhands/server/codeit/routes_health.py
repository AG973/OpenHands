"""CODEIT health check + structured logging routes."""

import os
import time
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from openhands.server.codeit.database import get_db, get_db_path

router = APIRouter(prefix="/api/codeit", tags=["codeit-health"])

_START_TIME = time.time()


@router.get("/health")
async def codeit_health() -> JSONResponse:
    """Full health check — DB, disk, uptime."""
    checks = {}

    # DB check
    try:
        with get_db() as conn:
            row = conn.execute("SELECT MAX(version) as v FROM schema_version").fetchone()
            checks["database"] = {"status": "ok", "version": row["v"] if row else 0, "path": get_db_path()}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}

    # Disk check
    try:
        data_dir = os.environ.get("CODEIT_DATA_DIR", os.path.expanduser("~/.codeit"))
        stat = os.statvfs(data_dir)
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
        checks["disk"] = {"status": "ok" if free_gb > 1 else "warning", "free_gb": round(free_gb, 2)}
    except Exception as e:
        checks["disk"] = {"status": "error", "error": str(e)}

    # Uptime
    uptime_seconds = time.time() - _START_TIME
    checks["uptime"] = {
        "seconds": int(uptime_seconds),
        "started_at": datetime.fromtimestamp(_START_TIME).isoformat(),
    }

    overall = "ok" if all(c.get("status") == "ok" for c in checks.values() if "status" in c) else "degraded"
    return JSONResponse(content={"status": overall, "checks": checks})


@router.get("/stats")
async def codeit_stats() -> JSONResponse:
    """Quick counts of all CODEIT entities."""
    with get_db() as conn:
        stats = {}
        for table in ["users", "skills", "knowledge", "prompts", "connectors", "deploy_jobs", "file_uploads"]:
            try:
                row = conn.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()
                stats[table] = row["c"] if row else 0
            except Exception:
                stats[table] = -1
    return JSONResponse(content={"stats": stats})
