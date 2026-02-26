# api/routes.py
# FastAPI REST router for Daniela — all endpoints return JSON with timestamp

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from core.config import Config
from core.logger import ai_logger
from core.database import db, Alerta
from ai.context_builder import get_context_builder
from ai.claude_agent import get_agent

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    language: Optional[str] = "es"


class ChatResponse(BaseModel):
    response: str
    language: str
    timestamp: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat()


def _query_alerts_sync(limit: int = 100, hours: int = 24) -> List[Dict[str, Any]]:
    """
    Synchronous DB query for alerts within the last `hours` hours.
    Returns plain dicts (session is closed before returning).
    """
    try:
        cutoff = datetime.now() - timedelta(hours=hours)
        with db.session_scope() as session:
            rows = (
                session.query(Alerta)
                .filter(Alerta.timestamp >= cutoff)
                .order_by(Alerta.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "alert_id":     r.alerta_id,
                    "tipo":         r.tipo,
                    "severidad":    r.severidad,
                    "dispositivo_id": r.dispositivo_id,
                    "mensaje":      r.mensaje,
                    "recomendacion": r.recomendacion,
                    "datos":        r.datos or {},
                    "timestamp":    r.timestamp.isoformat() if r.timestamp else None,
                    "resuelta":     r.resuelta,
                }
                for r in rows
            ]
    except Exception as exc:
        ai_logger.error(f"DB query error in _query_alerts_sync: {exc}")
        return []


def _db_ping_sync() -> bool:
    """Lightweight DB connectivity check."""
    try:
        with db.session_scope() as session:
            session.execute(db.engine.dialect.statement_compiler(
                db.engine.dialect, None
            ).__class__.__mro__[0]  # just importing to force connection
            )
    except Exception:
        pass
    try:
        with db.session_scope() as session:
            session.query(Alerta).limit(1).all()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------

@router.get("/status", summary="Global resort status")
async def get_status() -> Dict[str, Any]:
    """
    Aggregated real-time context from ContextBuilder (30-second TTL cache).
    Includes occupancy, active leaks, electrical and water consumption totals.
    """
    try:
        ctx = await run_in_threadpool(get_context_builder().get_realtime_context)
        return {"timestamp": _now(), "data": ctx}
    except Exception as exc:
        ai_logger.error(f"/status error: {exc}")
        raise HTTPException(status_code=503, detail="Context builder unavailable")


# ---------------------------------------------------------------------------
# GET /chillers
# ---------------------------------------------------------------------------

@router.get("/chillers", summary="All 3 RTAG chillers")
async def get_chillers() -> Dict[str, Any]:
    """
    Returns COP, power_kw, operating status, and degradation flag for each
    of the 3 RTAG chillers (2CH-1, 2CH-2, 2CH-3).

    Degradation flag is True when COP < Config.UMBRAL_COP_MINIMO (3.5).
    Source is 'simulator' when the simulation is running, 'database' otherwise.
    """
    cb = get_context_builder()
    await run_in_threadpool(cb._ensure_and_step_simulator)

    chillers_out: List[Dict[str, Any]] = []
    source = "simulator"

    if cb.simulator:
        try:
            status = await run_in_threadpool(cb.simulator.get_global_status)
            for ch in status.get("chillers", []):
                cop = float(ch.get("cop") or 0.0)
                power_kw = float(ch.get("power_kw") or 0.0)
                chillers_out.append({
                    "id":           ch.get("id"),
                    "cop":          round(cop, 2),
                    "power_kw":     round(power_kw, 1),
                    "status":       ch.get("estado", "unknown"),
                    "degradacion":  bool(0 < cop < Config.UMBRAL_COP_MINIMO),
                    "cop_minimo":   Config.UMBRAL_COP_MINIMO,
                })
        except Exception as exc:
            ai_logger.error(f"/chillers simulator error: {exc}")
            source = "error"
    else:
        # Fallback: last DB reading per chiller
        source = "database"
        for cid in ("2CH-1", "2CH-2", "2CH-3"):
            try:
                rows = await run_in_threadpool(db.get_historico_chiller, cid, 1)
                if rows:
                    r = rows[-1]
                    cop = float(r.cop or 0.0)
                    chillers_out.append({
                        "id":          cid,
                        "cop":         round(cop, 2),
                        "power_kw":    round(float(r.power_kw or 0), 1),
                        "status":      "last_known",
                        "degradacion": bool(0 < cop < Config.UMBRAL_COP_MINIMO),
                        "cop_minimo":  Config.UMBRAL_COP_MINIMO,
                    })
            except Exception as exc:
                ai_logger.warning(f"/chillers DB fallback error for {cid}: {exc}")

    return {
        "timestamp": _now(),
        "source":    source,
        "chillers":  chillers_out,
    }


# ---------------------------------------------------------------------------
# GET /leaks
# ---------------------------------------------------------------------------

@router.get("/leaks", summary="Active water leak alerts")
async def get_leaks() -> Dict[str, Any]:
    """
    Active (unresolved) leak alerts from the last 24 hours, queried from the
    database. Each entry includes room_id, building, flow_lph, and confidence.
    """
    all_alerts = await run_in_threadpool(_query_alerts_sync, 100, 24)
    fugas = [a for a in all_alerts if a["tipo"] == "fuga" and not a["resuelta"]]

    leaks_out = [
        {
            "alert_id":   f["alert_id"],
            "room_id":    f["dispositivo_id"],
            "building":   (f["dispositivo_id"] or "?")[0].upper(),
            "flow_lph":   float((f["datos"] or {}).get("caudal_lph", 0)),
            "confidence": float((f["datos"] or {}).get("confianza", 0)),
            "severity":   f["severidad"],
            "message":    f["mensaje"],
            "timestamp":  f["timestamp"],
        }
        for f in fugas
    ]

    return {
        "timestamp": _now(),
        "leaks":     leaks_out,
        "total":     len(leaks_out),
    }


# ---------------------------------------------------------------------------
# GET /alerts
# ---------------------------------------------------------------------------

@router.get("/alerts", summary="Last 24 h alerts (all types)")
async def get_alerts() -> Dict[str, Any]:
    """
    All alerts generated in the last 24 hours (leaks, chiller, panel,
    maintenance), ordered newest-first. Max 100 records.
    """
    all_alerts = await run_in_threadpool(_query_alerts_sync, 100, 24)
    return {
        "timestamp":    _now(),
        "alerts":       all_alerts,
        "total":        len(all_alerts),
        "window_hours": 24,
    }


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@router.get("/health", summary="System health check")
async def get_health() -> Dict[str, Any]:
    """
    Returns operational status of the three key subsystems:
      - simulator_running : ResortSimulator is initialised
      - db_connected      : database responds to a simple query
      - api_key_configured: ANTHROPIC_API_KEY is present in the environment
    """
    cb = get_context_builder()
    simulator_ok = cb.simulator is not None
    api_key_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
    db_ok = await run_in_threadpool(_db_ping_sync)

    overall = "healthy" if (db_ok and simulator_ok) else "degraded"

    return {
        "timestamp": _now(),
        "status":    overall,
        "checks": {
            "simulator_running":  simulator_ok,
            "db_connected":       db_ok,
            "api_key_configured": api_key_ok,
        },
        "version": Config.PROYECTO_VERSION,
        "project": Config.PROYECTO_NOMBRE,
    }


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse, summary="Chat with Daniela")
async def post_chat(body: ChatRequest) -> ChatResponse:
    """
    Sends a message to the DanielaAgent (Claude-backed) and returns the
    response text. The agent automatically detects language from the message;
    the `language` field in the request body is echoed back in the response.

    Body: { "message": "...", "language": "en" | "es" }
    """
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=422, detail="message must not be empty")

    agent = get_agent()
    try:
        response_text = await run_in_threadpool(agent.chat, body.message.strip())
    except Exception as exc:
        ai_logger.error(f"/chat error: {exc}")
        raise HTTPException(status_code=503, detail="Daniela agent unavailable")

    return ChatResponse(
        response=response_text,
        language=body.language or "es",
        timestamp=_now(),
    )
