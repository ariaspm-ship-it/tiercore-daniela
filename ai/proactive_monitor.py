# ai/proactive_monitor.py
# Proactive threshold monitor — Daniela v0.5
#
# Runs as a background thread, checks all thresholds every 300 seconds.
# When a threshold is crossed, generates an alert via DanielaAgent and
# stores it in the proactive alerts database.

import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logger import ai_logger
from core.config import Config

try:
    from ai.context_builder import get_context_builder
except ImportError:
    get_context_builder = None

try:
    from ai.claude_agent import get_agent
except ImportError:
    get_agent = None


# ── Severity levels ──────────────────────────────────────────────────
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_INFO = "INFO"

SEVERITY_ORDER = {SEVERITY_CRITICAL: 0, SEVERITY_HIGH: 1, SEVERITY_INFO: 2}

CHECK_INTERVAL_SECONDS = 300  # 5 minutes


# ── In-memory alert store ────────────────────────────────────────────
class ProactiveAlert:
    __slots__ = (
        "id", "timestamp", "severity", "alert_type",
        "equipment", "message", "acknowledged",
    )

    def __init__(
        self,
        severity: str,
        alert_type: str,
        equipment: str,
        message: str,
    ):
        self.id: str = uuid.uuid4().hex[:12]
        self.timestamp: str = datetime.now().isoformat()
        self.severity = severity
        self.alert_type = alert_type
        self.equipment = equipment
        self.message = message
        self.acknowledged = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "alert_type": self.alert_type,
            "equipment": self.equipment,
            "message": self.message,
            "acknowledged": self.acknowledged,
        }


class ProactiveAlertStore:
    """Thread-safe in-memory store for proactive alerts."""

    def __init__(self):
        self._alerts: List[ProactiveAlert] = []
        self._lock = threading.Lock()

    def add(self, alert: ProactiveAlert) -> None:
        with self._lock:
            self._alerts.append(alert)

    def get_unacknowledged(self) -> List[Dict[str, Any]]:
        with self._lock:
            pending = [a for a in self._alerts if not a.acknowledged]
            pending.sort(key=lambda a: SEVERITY_ORDER.get(a.severity, 9))
            return [a.to_dict() for a in pending]

    def acknowledge(self, alert_id: str) -> bool:
        with self._lock:
            for a in self._alerts:
                if a.id == alert_id:
                    a.acknowledged = True
                    return True
            return False

    def get_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [a.to_dict() for a in self._alerts]


# Singleton store
alert_store = ProactiveAlertStore()


# ── Threshold checks ─────────────────────────────────────────────────
def _check_thresholds(context: Dict[str, Any]) -> List[ProactiveAlert]:
    """Evaluate all decision thresholds against current context. Returns new alerts."""
    alerts: List[ProactiveAlert] = []

    chillers = context.get("chillers", [])
    resort = context.get("resort", {})
    financial = context.get("financial", {})
    active_alerts_ctx = context.get("active_alerts", [])

    # 1. COP degradation — any chiller below threshold
    for ch in chillers:
        cop = ch.get("cop")
        if not cop or cop <= 0:
            continue
        cop_min = ch.get("cop_minimum_threshold", Config.UMBRAL_COP_MINIMO)
        if ch.get("degraded") or (cop < cop_min):
            extra = financial.get("extra_cost_from_degradation_daily_usd", 0)
            alerts.append(ProactiveAlert(
                severity=SEVERITY_HIGH,
                alert_type="cop_degradation",
                equipment=ch["id"],
                message=(
                    f"{ch['id']} is losing efficiency — COP {cop:.2f} "
                    f"(threshold {cop_min}). Extra cost: ${extra:.0f}/day. "
                    f"Should I schedule a condenser service this week?"
                ),
            ))

    # 2. Chiller load imbalance (>40 percentage-point spread)
    running = [ch for ch in chillers if ch.get("cop") and ch["cop"] > 0]
    if len(running) >= 2:
        powers = [ch.get("power_kw", 0) for ch in running]
        max_p, min_p = max(powers), min(powers)
        capacity = 573.0  # kW per chiller
        if capacity > 0:
            spread = ((max_p - min_p) / capacity) * 100
            if spread > 40:
                alerts.append(ProactiveAlert(
                    severity=SEVERITY_INFO,
                    alert_type="load_imbalance",
                    equipment="Chiller Plant",
                    message=(
                        f"Chiller load imbalance detected — {spread:.0f} percentage-point spread. "
                        f"Energy penalty: 15-20% = $27,000-$48,000/year at BCH scale. "
                        f"Shall I recommend a resequencing schedule?"
                    ),
                ))

    # 3. Active leaks
    active_leaks = resort.get("active_leaks", 0)
    if active_leaks > 0:
        leak_alerts = [a for a in active_alerts_ctx if a.get("type") == "fuga"]
        for la in leak_alerts:
            flow = la.get("flow_lph", 0)
            device = la.get("device", "unknown")
            severity = SEVERITY_CRITICAL if flow > 50 else SEVERITY_HIGH
            alerts.append(ProactiveAlert(
                severity=severity,
                alert_type="leak",
                equipment=device,
                message=(
                    f"{device} has a leak — nocturnal flow {flow} L/h. "
                    f"Undetected 72h = $3,000-$8,000 structural damage. "
                    f"Shall I take {device} out of service and dispatch plumbing?"
                ),
            ))
        # If leaks exist but no DB alerts, still flag
        if not leak_alerts:
            alerts.append(ProactiveAlert(
                severity=SEVERITY_HIGH,
                alert_type="leak",
                equipment="Property",
                message=(
                    f"{active_leaks} active leak indicator(s) across the property. "
                    f"Cost if undetected: $3,000-$8,000 per leak in structural damage. "
                    f"Should I generate a room-by-room leak report?"
                ),
            ))

    # 4. Chiller offline + capacity concern
    offline_count = sum(1 for ch in chillers if not ch.get("cop") or ch["cop"] <= 0)
    if offline_count > 0 and len(chillers) > 0:
        remaining_capacity = (len(chillers) - offline_count) * 573
        total_load = sum(ch.get("power_kw", 0) for ch in running)
        if remaining_capacity > 0 and total_load > remaining_capacity * 0.8:
            alerts.append(ProactiveAlert(
                severity=SEVERITY_CRITICAL,
                alert_type="capacity_critical",
                equipment="Chiller Plant",
                message=(
                    f"{offline_count} chiller(s) offline — remaining capacity at "
                    f"{(total_load / remaining_capacity * 100):.0f}% utilization. "
                    f"Chiller down 1 hour = $800-$1,200 extra energy + guest complaint risk. "
                    f"Call maintenance immediately?"
                ),
            ))

    return alerts


# ── Background monitor thread ────────────────────────────────────────
class ProactiveMonitor:
    """Background thread that checks thresholds every CHECK_INTERVAL_SECONDS."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        ai_logger.info(
            f"Proactive monitor started (interval={CHECK_INTERVAL_SECONDS}s)"
        )

    def stop(self) -> None:
        self._running = False
        ai_logger.info("Proactive monitor stopped")

    def _loop(self) -> None:
        while self._running:
            try:
                self._check_once()
            except Exception as exc:
                ai_logger.error(f"Proactive monitor error: {exc}")
            time.sleep(CHECK_INTERVAL_SECONDS)

    def _check_once(self) -> None:
        if not get_context_builder:
            return
        cb = get_context_builder()
        context = cb.get_realtime_context(force_refresh=True)

        new_alerts = _check_thresholds(context)
        if not new_alerts:
            ai_logger.debug("Proactive check: all clear")
            return

        for alert in new_alerts:
            # Try to generate a richer message via the agent
            if get_agent:
                try:
                    agent = get_agent()
                    enriched = agent.generate_alert(
                        f"Type: {alert.alert_type}, Equipment: {alert.equipment}, "
                        f"Base: {alert.message}"
                    )
                    if enriched and len(enriched) > 20:
                        alert.message = enriched
                except Exception:
                    pass  # Keep the rule-based message

            alert_store.add(alert)
            ai_logger.warning(
                f"[PROACTIVE] {alert.severity} — {alert.equipment}: "
                f"{alert.message[:80]}..."
            )

    def check_now(self) -> List[Dict[str, Any]]:
        """Run a check immediately (for on-demand use). Returns new alerts."""
        if not get_context_builder:
            return []
        cb = get_context_builder()
        context = cb.get_realtime_context(force_refresh=True)
        new_alerts = _check_thresholds(context)
        for alert in new_alerts:
            alert_store.add(alert)
        return [a.to_dict() for a in new_alerts]


# Singleton monitor
_monitor: Optional[ProactiveMonitor] = None


def get_monitor() -> ProactiveMonitor:
    global _monitor
    if _monitor is None:
        _monitor = ProactiveMonitor()
    return _monitor
