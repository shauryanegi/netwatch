"""FastAPI web server for the netwatch local dashboard.

Serves a browser-based UI at http://localhost:8080.
All data stays local — this server only binds to 127.0.0.1.

Endpoints:
  GET  /                    → HTML dashboard
  GET  /api/config          → ISP name, advertised speed, AI enabled flag
  GET  /api/stats           → aggregate statistics
  GET  /api/readings        → recent speed readings as JSON
  POST /api/run-test        → trigger a speed test (blocks until complete)
  GET  /api/ai/summary      → AI weekly summary
  GET  /api/ai/anomalies    → AI anomaly detection
  GET  /api/ai/letter       → AI complaint letter
  POST /api/ai/chat         → AI chat, body: {"question": "..."}
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from netwatch import ai as ai_module
from netwatch.ai import AIError
from netwatch.config import Config
from netwatch.database import get_readings, get_stats, init_db
from netwatch.logger import SpeedTestError, log_speed

_config: Optional[Config] = None
_test_running: bool = False

app = FastAPI(title="netwatch", docs_url=None, redoc_url=None)


def create_app(config: Config) -> FastAPI:
    """Initialise the app with the given config and return it."""
    global _config
    _config = config
    init_db(config.db_path)
    return app


# ─────────────────────────────────────────────────────────────
#  HTML dashboard
# ─────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    template = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(content=template.read_text())


# ─────────────────────────────────────────────────────────────
#  Data API
# ─────────────────────────────────────────────────────────────


@app.get("/api/config")
async def get_app_config():
    return {
        "isp_name": _config.isp_name,
        "advertised_mbps": _config.advertised_mbps,
        "ai_enabled": bool(_config.groq_api_key),
    }


@app.get("/api/stats")
async def stats(days: int = 30):
    result = get_stats(_config.db_path, days=days, advertised_mbps=_config.advertised_mbps)
    if result is None:
        return None
    return {
        "count": result.count,
        "avg_download": result.avg_download,
        "avg_upload": result.avg_upload,
        "avg_ping": result.avg_ping,
        "min_download": result.min_download,
        "max_download": result.max_download,
        "min_upload": result.min_upload,
        "max_upload": result.max_upload,
        "below_threshold_pct": result.below_threshold_pct,
    }


@app.get("/api/readings")
async def readings(limit: int = 200, days: int = 7):
    data = get_readings(_config.db_path, limit=limit, days=days)
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "download_mbps": r.download_mbps,
            "upload_mbps": r.upload_mbps,
            "ping_ms": r.ping_ms,
            "server_name": r.server_name,
            "isp": r.isp,
        }
        for r in data
    ]


@app.post("/api/run-test")
async def run_test():
    global _test_running
    if _test_running:
        raise HTTPException(status_code=409, detail="A speed test is already running.")
    _test_running = True
    try:
        reading = await asyncio.to_thread(log_speed, _config)
        return {
            "download_mbps": reading.download_mbps,
            "upload_mbps": reading.upload_mbps,
            "ping_ms": reading.ping_ms,
            "server_name": reading.server_name,
            "timestamp": reading.timestamp.isoformat(),
        }
    except SpeedTestError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        _test_running = False


# ─────────────────────────────────────────────────────────────
#  AI API
# ─────────────────────────────────────────────────────────────


def _require_ai():
    if not _config.groq_api_key:
        raise HTTPException(
            status_code=403,
            detail="AI features require GROQ_API_KEY. Get a free key at https://console.groq.com",
        )


@app.get("/api/ai/summary")
async def ai_summary(days: int = 7):
    _require_ai()
    data = get_readings(_config.db_path, limit=500, days=days)
    result_stats = get_stats(_config.db_path, days=days, advertised_mbps=_config.advertised_mbps)
    try:
        result = await asyncio.to_thread(ai_module.weekly_summary, data, result_stats, _config)
        return {"result": result}
    except AIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/ai/anomalies")
async def ai_anomalies(days: int = 14):
    _require_ai()
    data = get_readings(_config.db_path, limit=500, days=days)
    try:
        result = await asyncio.to_thread(ai_module.detect_anomalies, data, _config)
        return {"result": result}
    except AIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/ai/letter")
async def ai_letter(days: int = 30):
    _require_ai()
    data = get_readings(_config.db_path, limit=500, days=days)
    result_stats = get_stats(_config.db_path, days=days, advertised_mbps=_config.advertised_mbps)
    try:
        result = await asyncio.to_thread(ai_module.complaint_letter, data, result_stats, _config)
        return {"result": result}
    except AIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class ChatRequest(BaseModel):
    question: str
    days: int = 30


@app.post("/api/ai/chat")
async def ai_chat(body: ChatRequest):
    _require_ai()
    data = get_readings(_config.db_path, limit=500, days=body.days)
    result_stats = get_stats(_config.db_path, days=body.days, advertised_mbps=_config.advertised_mbps)
    try:
        result = await asyncio.to_thread(ai_module.chat, body.question, data, result_stats, _config)
        return {"result": result}
    except AIError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
