# ai/briefing.py
# Daily briefing generator + scheduler — Daniela v0.5
#
# Auto-generates an executive briefing at 08:00 every day.
# Stores in memory. GET /api/v1/briefing/latest returns the most recent.
# If no briefing today, generates one on demand.

import threading
import time
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from core.logger import ai_logger
from core.config import Config
from ai.context_builder import get_context_builder


# ── Briefing store ───────────────────────────────────────────────────
class BriefingStore:
    """Thread-safe store for daily briefings."""

    def __init__(self):
        self._briefings: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def add(self, briefing: Dict[str, Any]) -> None:
        with self._lock:
            self._briefings.append(briefing)

    def get_latest(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self._briefings:
                return None
            return self._briefings[-1]

    def has_today(self) -> bool:
        with self._lock:
            if not self._briefings:
                return False
            last = self._briefings[-1]
            last_date = last.get("date")
            return last_date == date.today().isoformat()


briefing_store = BriefingStore()


# ── Briefing generation ──────────────────────────────────────────────
def generate_briefing() -> Dict[str, Any]:
    """
    Pulls live data from the ContextBuilder and formats a 3-paragraph
    executive summary in Kempinski hospitality tone.
    """
    cb = get_context_builder()
    ctx = cb.get_realtime_context(force_refresh=True)

    resort = ctx.get("resort", {})
    chillers = ctx.get("chillers", [])
    financial = ctx.get("financial", {})
    alerts = ctx.get("active_alerts", [])

    now = datetime.now()
    greeting = "Good morning" if now.hour < 12 else (
        "Good afternoon" if now.hour < 18 else "Good evening"
    )

    total_units = resort.get("total_units", 191)
    elec_kwh = resort.get("total_electricity_kwh", 0)
    water_m3 = resort.get("total_water_m3", 0)
    solar_kw = resort.get("solar_production_kw", 0)
    active_leaks = resort.get("active_leaks", 0)

    running = [c for c in chillers if c.get("cop") and c["cop"] > 0]
    degraded = [c for c in chillers if c.get("degraded")]
    avg_cop = (sum(c["cop"] for c in running) / len(running)) if running else 0

    rate = financial.get("electricity_rate_usd_kwh", 0.25)
    extra_cost = financial.get("extra_cost_from_degradation_daily_usd", 0)

    # Paragraph 1 — Property overview
    p1 = (
        f"{greeting}. BCH-Villa Colony Resort is monitoring "
        f"{total_units} units across Buildings A, B, C and 4 luxury villas. "
        f"Electricity: {elec_kwh:,.1f} kWh (${elec_kwh * rate:,.0f}), "
        f"water: {water_m3:,.1f} m\u00b3, solar: {solar_kw} kW."
    )

    # Paragraph 2 — Chiller plant + issues
    if degraded:
        ids = ", ".join(c["id"] for c in degraded)
        p2 = (
            f"Chiller plant: {len(running)}/3 active, average COP {avg_cop:.2f}. "
            f"{ids} {'is' if len(degraded) == 1 else 'are'} below the "
            f"{chillers[0].get('cop_minimum_threshold', 3.5)} threshold — "
            f"${extra_cost:.0f}/day in excess cost. "
            f"Fouled condenser emergency: $12,000-$18,000 vs $800 scheduled."
        )
    else:
        cop_thresh = chillers[0].get("cop_minimum_threshold", 3.5) if chillers else 3.5
        p2 = (
            f"Chiller plant: {len(running)}/3 active, average COP {avg_cop:.2f} — "
            f"above the {cop_thresh} threshold. No efficiency concerns."
        )

    # Paragraph 3 — Leaks + decision
    high_alerts = sum(1 for a in alerts if a.get("severity") == "alta")

    if active_leaks > 0:
        p3 = (
            f"{active_leaks} active leak indicator{'s' if active_leaks > 1 else ''}. "
            f"Undetected 72h = $3,000-$8,000 structural damage per leak. "
        )
    else:
        p3 = "No water leaks detected. "

    if high_alerts > 0:
        p3 += f"{high_alerts} high-severity alert{'s' if high_alerts > 1 else ''} pending. "

    if degraded or active_leaks > 0 or high_alerts > 0:
        p3 += "Should I prepare a prioritized action plan for today's operations meeting?"
    else:
        p3 += "All systems nominal. Next scheduled maintenance window can proceed as planned."

    briefing_text = f"{p1}\n\n{p2}\n\n{p3}"

    ai_logger.info(f"Briefing generated ({len(briefing_text)} chars)")

    result = {
        "timestamp": now.isoformat(),
        "date": date.today().isoformat(),
        "briefing": briefing_text,
        "summary": {
            "total_units": total_units,
            "electricity_kwh": elec_kwh,
            "water_m3": water_m3,
            "solar_kw": solar_kw,
            "active_leaks": active_leaks,
            "chillers_running": len(running),
            "avg_cop": round(avg_cop, 2),
            "degraded_chillers": [c["id"] for c in degraded],
            "extra_cost_daily_usd": extra_cost,
            "high_alerts": high_alerts,
        },
    }

    briefing_store.add(result)
    return result


def get_latest_briefing() -> Dict[str, Any]:
    """
    Returns the latest briefing. If none exists for today, generates one.
    """
    if not briefing_store.has_today():
        return generate_briefing()
    return briefing_store.get_latest()


# ── Scheduled briefing thread ────────────────────────────────────────
class BriefingScheduler:
    """Background thread that generates a briefing at 08:00 daily."""

    BRIEFING_HOUR = 8

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        ai_logger.info("Briefing scheduler started (daily at 08:00)")

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        last_briefing_date: Optional[str] = None
        while self._running:
            now = datetime.now()
            today_str = date.today().isoformat()

            if (
                now.hour >= self.BRIEFING_HOUR
                and last_briefing_date != today_str
            ):
                try:
                    generate_briefing()
                    last_briefing_date = today_str
                    ai_logger.info("Scheduled 08:00 briefing generated")
                except Exception as exc:
                    ai_logger.error(f"Scheduled briefing error: {exc}")

            time.sleep(60)  # Check every minute


_scheduler: Optional[BriefingScheduler] = None


def get_scheduler() -> BriefingScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BriefingScheduler()
    return _scheduler
