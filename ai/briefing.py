# ai/briefing.py
# Executive daily briefing generator for Daniela

from datetime import datetime
from typing import Dict, Any

from core.logger import ai_logger
from ai.context_builder import get_context_builder


def generate_briefing() -> Dict[str, Any]:
    """
    Pulls live data from the ContextBuilder and formats a 3-paragraph
    executive summary in Kempinski hospitality tone.
    """
    cb = get_context_builder()
    ctx = cb.get_realtime_context(force_refresh=True)

    resort = ctx.get("resort", {})
    buildings = ctx.get("buildings", {})
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
        f"{greeting}. BCH-Villa Colony Resort is currently monitoring "
        f"{total_units} units across Buildings A, B, and C plus 4 luxury villas. "
        f"Today's electricity consumption stands at {elec_kwh:,.1f} kWh "
        f"(${elec_kwh * rate:,.0f}), water usage at {water_m3:,.1f} m\u00b3, "
        f"and solar production is delivering {solar_kw} kW."
    )

    # Paragraph 2 — Chiller plant + issues
    if degraded:
        ids = ", ".join(c["id"] for c in degraded)
        p2 = (
            f"The chiller plant has {len(running)} of 3 units active with an "
            f"average COP of {avg_cop:.2f}. {ids} "
            f"{'is' if len(degraded) == 1 else 'are'} showing efficiency "
            f"degradation below the {chillers[0].get('cop_minimum_threshold', 3.5)} "
            f"COP threshold, adding an estimated ${extra_cost:.0f}/day to "
            f"operating costs. Immediate maintenance is recommended."
        )
    else:
        p2 = (
            f"The chiller plant is performing well with {len(running)} of 3 units "
            f"active and an average COP of {avg_cop:.2f} — comfortably above "
            f"the {chillers[0].get('cop_minimum_threshold', 3.5) if chillers else 3.5} "
            f"minimum threshold. No efficiency concerns at this time."
        )

    # Paragraph 3 — Leaks + alerts + recommendation
    high_alerts = sum(1 for a in alerts if a.get("severity") == "alta")

    if active_leaks > 0:
        p3 = (
            f"Water leak monitoring has flagged {active_leaks} active "
            f"indicator{'s' if active_leaks > 1 else ''} requiring attention. "
        )
    else:
        p3 = "No water leaks detected across the property. "

    if high_alerts > 0:
        p3 += (
            f"There {'are' if high_alerts > 1 else 'is'} {high_alerts} "
            f"high-severity alert{'s' if high_alerts > 1 else ''} pending review. "
        )

    if degraded or active_leaks > 0 or high_alerts > 0:
        p3 += (
            "I recommend addressing these items during today's operations "
            "meeting. Shall I prepare a detailed action plan?"
        )
    else:
        p3 += (
            "All systems are operating within normal parameters. "
            "No immediate action required — the next scheduled maintenance "
            "window can proceed as planned."
        )

    briefing_text = f"{p1}\n\n{p2}\n\n{p3}"

    ai_logger.info(f"Briefing generated ({len(briefing_text)} chars)")

    return {
        "timestamp": now.isoformat(),
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
