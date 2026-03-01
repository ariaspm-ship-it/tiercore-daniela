# api/routes.py
# FastAPI REST router for Daniela — all endpoints return JSON with timestamp

import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import text as sa_text

from core.config import Config
from core.logger import ai_logger
from core.database import db, Alerta
from ai.context_builder import get_context_builder
from ai.claude_agent import get_agent
from ai.briefing import generate_briefing, get_latest_briefing
from ai.chiller_optimizer import ChillerOptimizer
from ai.proactive_monitor import alert_store, get_monitor

_chiller_optimizer: Optional[ChillerOptimizer] = None

def _get_optimizer() -> ChillerOptimizer:
    global _chiller_optimizer
    if _chiller_optimizer is None:
        _chiller_optimizer = ChillerOptimizer()
    return _chiller_optimizer

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
    """Synchronous DB query for alerts within the last hours."""
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
                    "alert_id": r.alerta_id,
                    "tipo": r.tipo,
                    "severidad": r.severidad,
                    "dispositivo_id": r.dispositivo_id,
                    "mensaje": r.mensaje,
                    "recomendacion": r.recomendacion,
                    "datos": r.datos or {},
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "resuelta": r.resuelta,
                }
                for r in rows
            ]
    except Exception as exc:
        ai_logger.error(f"DB query error: {exc}")
        return []


def _db_ping_sync() -> bool:
    """Lightweight DB connectivity check."""
    try:
        with db.session_scope() as session:
            session.execute(sa_text("SELECT 1"))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# GET /status — Global resort status
# ---------------------------------------------------------------------------

@router.get("/status", summary="Global resort status")
async def get_status() -> Dict[str, Any]:
    """Aggregated real-time context from ContextBuilder (30s TTL cache)."""
    try:
        ctx = await run_in_threadpool(get_context_builder().get_realtime_context)
        return {"timestamp": _now(), "data": ctx}
    except Exception as exc:
        ai_logger.error(f"/status error: {exc}")
        raise HTTPException(status_code=503, detail="Context builder unavailable")


# ---------------------------------------------------------------------------
# GET /buildings — Per-building consumption and status
# ---------------------------------------------------------------------------

@router.get("/buildings", summary="Per-building consumption and status")
async def get_buildings() -> Dict[str, Any]:
    """Consumption and leak status per building from the simulator."""
    try:
        cb = get_context_builder()
        buildings = await run_in_threadpool(cb.get_consumption_by_building)
        return {"timestamp": _now(), "buildings": buildings}
    except Exception as exc:
        ai_logger.error(f"/buildings error: {exc}")
        raise HTTPException(status_code=503, detail="Building data unavailable")


# ---------------------------------------------------------------------------
# GET /chillers — All 3 RTAG chillers
# ---------------------------------------------------------------------------

@router.get("/chillers", summary="All 3 RTAG chillers")
async def get_chillers() -> Dict[str, Any]:
    """COP, power, status, and degradation flag for each chiller."""
    cb = get_context_builder()
    await run_in_threadpool(cb._ensure_and_step_simulator)

    chillers_out: List[Dict[str, Any]] = []
    source = "simulator"

    if cb.simulator:
        try:
            optimizer = _get_optimizer()
            status = await run_in_threadpool(cb.simulator.get_global_status)
            for ch in status.get("chillers", []):
                cop = float(ch.get("cop") or 0.0)
                power_kw = float(ch.get("power_kw") or 0.0)
                chiller_id = ch.get("id")

                # Find device object for prediction
                dtt = None
                for dev in cb.simulator.chillers:
                    if dev.id == chiller_id:
                        dtt = await run_in_threadpool(optimizer.predict_days_to_threshold, dev)
                        break

                chillers_out.append({
                    "id": chiller_id,
                    "cop": round(cop, 2),
                    "power_kw": round(power_kw, 1),
                    "status": ch.get("estado", "unknown"),
                    "degraded": bool(0 < cop < Config.UMBRAL_COP_MINIMO),
                    "cop_minimum": Config.UMBRAL_COP_MINIMO,
                    "days_to_threshold": dtt,
                })
        except Exception as exc:
            ai_logger.error(f"/chillers simulator error: {exc}")
            source = "error"
    else:
        source = "database"
        for cid in ("2CH-1", "2CH-2", "2CH-3"):
            try:
                rows = await run_in_threadpool(db.get_historico_chiller, cid, 1)
                if rows:
                    r = rows[-1]
                    cop = float(r.cop or 0.0)
                    chillers_out.append({
                        "id": cid,
                        "cop": round(cop, 2),
                        "power_kw": round(float(r.power_kw or 0), 1),
                        "status": "last_known",
                        "degraded": bool(0 < cop < Config.UMBRAL_COP_MINIMO),
                        "cop_minimum": Config.UMBRAL_COP_MINIMO,
                    })
            except Exception as exc:
                ai_logger.warning(f"/chillers DB fallback error {cid}: {exc}")

    return {
        "timestamp": _now(),
        "source": source,
        "chillers": chillers_out,
    }


# ---------------------------------------------------------------------------
# GET /leaks — Active water leak alerts
# ---------------------------------------------------------------------------

@router.get("/leaks", summary="Active water leak alerts")
async def get_leaks() -> Dict[str, Any]:
    """Active (unresolved) leak alerts from the last 24 hours,
    including in-flight leaks detected by the simulator in real time."""
    # 1. DB-persisted leaks (existing behaviour)
    all_alerts = await run_in_threadpool(_query_alerts_sync, 100, 24)
    fugas = [a for a in all_alerts if a["tipo"] == "fuga" and not a["resuelta"]]

    leaks_out: List[Dict[str, Any]] = [
        {
            "alert_id": f["alert_id"],
            "room_id": f["dispositivo_id"],
            "building": (f["dispositivo_id"] or "?")[0].upper(),
            "flow_lph": float((f["datos"] or {}).get("caudal_lph", 0)),
            "confidence": float((f["datos"] or {}).get("confianza", 0)),
            "severity": f["severidad"],
            "message": f["mensaje"],
            "timestamp": f["timestamp"],
            "source": "database",
        }
        for f in fugas
    ]

    db_room_ids = {l["room_id"] for l in leaks_out}

    # 2. In-flight simulator leaks (same source as /status)
    cb = get_context_builder()
    await run_in_threadpool(cb._ensure_and_step_simulator)

    if cb.simulator:
        for room in cb.simulator.habitaciones:
            if not getattr(room, "fuga_activa", False):
                continue
            if room.id in db_room_ids:
                continue
            night_flow = room.get_night_flow()
            leaks_out.append({
                "alert_id": f"SIM-{room.id}",
                "room_id": room.id,
                "building": room.edificio,
                "flow_lph": round(night_flow, 1),
                "confidence": 0.0,
                "severity": "media",
                "message": f"Posible fuga detectada en {room.id} (simulador)",
                "timestamp": _now(),
                "source": "simulator",
            })

    return {
        "timestamp": _now(),
        "leaks": leaks_out,
        "total": len(leaks_out),
    }


# ---------------------------------------------------------------------------
# GET /alerts — Last 24h alerts (all types)
# ---------------------------------------------------------------------------

@router.get("/alerts", summary="Last 24h alerts (all types)")
async def get_alerts() -> Dict[str, Any]:
    """All alerts generated in the last 24 hours, newest first."""
    all_alerts = await run_in_threadpool(_query_alerts_sync, 100, 24)
    return {
        "timestamp": _now(),
        "alerts": all_alerts,
        "total": len(all_alerts),
        "window_hours": 24,
    }


# ---------------------------------------------------------------------------
# GET /health — System health check
# ---------------------------------------------------------------------------

@router.get("/health", summary="System health check")
async def get_health() -> Dict[str, Any]:
    """Operational status of key subsystems."""
    cb = get_context_builder()
    simulator_ok = cb.simulator is not None
    api_key_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
    db_ok = await run_in_threadpool(_db_ping_sync)

    overall = "healthy" if (db_ok and simulator_ok) else "degraded"

    return {
        "timestamp": _now(),
        "status": overall,
        "checks": {
            "simulator_running": simulator_ok,
            "db_connected": db_ok,
            "api_key_configured": api_key_ok,
        },
        "version": Config.PROYECTO_VERSION,
        "project": Config.PROYECTO_NOMBRE,
    }


# ---------------------------------------------------------------------------
# POST /chat — Chat with Daniela
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse, summary="Chat with Daniela")
async def post_chat(body: ChatRequest) -> ChatResponse:
    """
    Sends a message to the DanielaAgent (Claude-backed) and returns
    the response. Language is auto-detected from the message.
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


# ---------------------------------------------------------------------------
# POST /chat/clear — Clear conversation history
# ---------------------------------------------------------------------------

@router.post("/chat/clear", summary="Clear Daniela conversation history")
async def post_chat_clear() -> Dict[str, Any]:
    """Clears the conversation history for a fresh start."""
    agent = get_agent()
    agent.clear_history()
    return {"timestamp": _now(), "message": "Conversation history cleared"}


# ---------------------------------------------------------------------------
# GET /briefing — Executive daily briefing
# ---------------------------------------------------------------------------

@router.get("/briefing", summary="Executive daily briefing")
async def get_briefing_endpoint() -> Dict[str, Any]:
    """3-paragraph executive summary in Kempinski hospitality tone."""
    try:
        result = await run_in_threadpool(generate_briefing)
        return result
    except Exception as exc:
        ai_logger.error(f"/briefing error: {exc}")
        raise HTTPException(status_code=503, detail="Briefing generation failed")


@router.get("/briefing/latest", summary="Latest daily briefing (cached)")
async def get_briefing_latest() -> Dict[str, Any]:
    """Returns most recent briefing; generates on demand if none today."""
    try:
        result = await run_in_threadpool(get_latest_briefing)
        return result
    except Exception as exc:
        ai_logger.error(f"/briefing/latest error: {exc}")
        raise HTTPException(status_code=503, detail="Briefing generation failed")


# ---------------------------------------------------------------------------
# GET /proactive — Unacknowledged proactive alerts
# ---------------------------------------------------------------------------

@router.get("/proactive", summary="Unacknowledged proactive alerts")
async def get_proactive() -> Dict[str, Any]:
    """Returns unacknowledged alerts ordered by severity (CRITICAL > HIGH > INFO)."""
    alerts = alert_store.get_unacknowledged()
    return {
        "timestamp": _now(),
        "alerts": alerts,
        "total": len(alerts),
    }


# ---------------------------------------------------------------------------
# POST /proactive/{alert_id}/acknowledge — Mark alert as read
# ---------------------------------------------------------------------------

@router.post("/proactive/{alert_id}/acknowledge", summary="Acknowledge a proactive alert")
async def acknowledge_proactive(alert_id: str) -> Dict[str, Any]:
    """Marks a proactive alert as acknowledged."""
    ok = alert_store.acknowledge(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"timestamp": _now(), "message": f"Alert {alert_id} acknowledged"}


# ---------------------------------------------------------------------------
# POST /proactive/check — Force an immediate threshold check
# ---------------------------------------------------------------------------

@router.post("/proactive/check", summary="Force immediate threshold check")
async def force_proactive_check() -> Dict[str, Any]:
    """Runs a threshold check immediately and returns any new alerts."""
    monitor = get_monitor()
    new_alerts = await run_in_threadpool(monitor.check_now)
    return {
        "timestamp": _now(),
        "new_alerts": new_alerts,
        "total_new": len(new_alerts),
    }


# ---------------------------------------------------------------------------
# DEMO MODE endpoints
# ---------------------------------------------------------------------------

@router.post("/demo/inject-leak", summary="Inject a leak in Building B")
async def demo_inject_leak() -> Dict[str, Any]:
    """Forces fuga_activa=True on a random Building B room for demo."""
    cb = get_context_builder()
    if not cb.simulator:
        raise HTTPException(status_code=503, detail="Simulator not running")

    b_rooms = [r for r in cb.simulator.habitaciones if r.edificio == "B"]
    if not b_rooms:
        raise HTTPException(status_code=404, detail="No Building B rooms")

    room = random.choice(b_rooms)
    room.fuga_activa = True
    ai_logger.info(f"[DEMO] Injected leak in {room.id}")
    return {"timestamp": _now(), "message": f"Leak injected in room {room.id} (Building B)"}


@router.post("/demo/degrade-chiller", summary="Degrade chiller 2CH-2 COP")
async def demo_degrade_chiller() -> Dict[str, Any]:
    """Reduces 2CH-2 COP by 20% for demo presentations."""
    cb = get_context_builder()
    if not cb.simulator:
        raise HTTPException(status_code=503, detail="Simulator not running")

    target = None
    for ch in cb.simulator.chillers:
        if ch.id == "2CH-2":
            target = ch
            break
    if not target or not target.last_data:
        raise HTTPException(status_code=404, detail="Chiller 2CH-2 not found")

    from devices.chiller import ChillerData
    old_cop = target.last_data.cop or 4.0
    new_cop = round(old_cop * 0.8, 2)
    degraded_data = ChillerData(
        timestamp=datetime.now(),
        temp_supply=target.last_data.temp_supply,
        temp_return=target.last_data.temp_return,
        power_kw=target.last_data.power_kw,
        cooling_kw=round((target.last_data.power_kw or 70) * new_cop, 1),
        cop=new_cop,
        compressor_status=target.last_data.compressor_status,
        alarm=True,
        flow_m3h=target.last_data.flow_m3h,
    )
    target.update(degraded_data)
    ai_logger.info(f"[DEMO] Degraded 2CH-2 COP: {old_cop} -> {new_cop}")
    return {
        "timestamp": _now(),
        "message": f"Chiller 2CH-2 degraded: COP {old_cop} -> {new_cop}",
    }


@router.post("/demo/reset", summary="Reset simulator to normal state")
async def demo_reset() -> Dict[str, Any]:
    """Clears all injected leaks and runs a normal simulator step."""
    cb = get_context_builder()
    if not cb.simulator:
        raise HTTPException(status_code=503, detail="Simulator not running")

    for room in cb.simulator.habitaciones:
        room.fuga_activa = False
    cb.simulator.step()
    # Clear context cache so next fetch is fresh
    cb.last_update = None
    ai_logger.info("[DEMO] Simulator reset to baseline")
    return {"timestamp": _now(), "message": "Simulator reset to normal state"}
