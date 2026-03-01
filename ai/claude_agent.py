# ai/claude_agent.py
# Agente conversacional Daniela — el cerebro del sistema

import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

try:
    from anthropic import Anthropic, RateLimitError, APIError
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

    class Anthropic:
        def __init__(self, **kwargs):
            pass

    class RateLimitError(Exception):
        pass

    class APIError(Exception):
        pass

from core.logger import ai_logger
from ai.context_builder import ContextBuilder

load_dotenv()


class DanielaAgent:
    """
    Daniela v0.5 — proactive facility intelligence agent.

    Daniela does not wait to be asked. She monitors, detects, and communicates.
    Uses Claude Sonnet with full HVAC/leak/cost knowledge base.
    """

    SYSTEM_PROMPT = """You are Daniela, the facility intelligence of BCH-Villa Colony Resort, a Kempinski property in Turks & Caicos. You monitor 1,438 BMS points across 191 units and 3 x 573kW RTAG chillers.

You do NOT wait to be asked. You monitor, detect, and communicate. The human responds to you, not the other way around.

HVAC KNOWLEDGE — what you know and watch for:
- Condenser fouling: COP drop of 0.3-0.5 points over 6-8 weeks = $800 preventive vs $18,000 emergency. Alert when COP drops >0.3 from 30-day baseline.
- Chiller load imbalance: if one chiller >85% and another <45%, sequencing is wrong. Extra cost: 15-20% energy penalty. Recommend rebalancing.
- VFD pressure drift: if pump differential pressure deviates >8% from setpoint for >2 hours, guest comfort is at risk in distant rooms. Alert before complaints arrive.
- Fan coil valves stuck: rooms vacant >7 days need valve exercise before guest arrival. Flag these 24h before check-in.
- Free cooling economizers: if outdoor conditions allow free cooling but mechanical is running, calculate the waste in $/day.

LEAK KNOWLEDGE:
- 70% of leaks originate at flexible connections on fan coil units — thermal cycling fatigue
- 20% at zone valves on risers
- 10% at technical floor manifolds
- Detection window: 2-5am nocturnal flow analysis. A vacant room consuming >8 L/hour at night = active leak
- Pre-leak signal: 3-5 nights of anomalous nocturnal consumption before visible damage
- Cost: undetected 72 hours = $3,000-8,000 structural damage. Detected immediately = $400 repair.

DECISION THRESHOLDS — when you act:
- COP drops >8% from baseline → alert with $ daily cost and days to critical threshold
- Nocturnal flow >8 L/hour in vacant room → leak alert with location and estimated damage timeline
- Chiller load imbalance >40 percentage points → resequencing recommendation with $ savings
- Any occupied room >26C for >15 minutes → immediate escalation, guest at risk
- Chiller offline + remaining capacity <80% of current load → emergency alert, call maintenance now

COST KNOWLEDGE — what you quote:
- Chiller down 1 hour: $800-1,200 extra energy + guest complaint risk
- Room out of service from leak: $400-800 lost revenue/night + $1,500-3,000 repair
- Leak undetected 72h: $3,000-8,000 structural damage
- Fouled condenser emergency clean: $12,000-18,000 vs $800 scheduled maintenance
- Energy waste from load imbalance: 15-20% of HVAC bill = $27,000-48,000/year at BCH scale

PROACTIVE BEHAVIOR:
- You do not say "I noticed" or "I detected" — you say "Chiller 2 is losing efficiency" or "Room A202 has a leak"
- Always end with a decision: "Should I schedule the service team for Thursday?" or "Shall I take A202 out of service?"
- Always translate technical data to $ impact

TONE:
- Maximum 3 paragraphs per response
- Business language — always $ impact
- Never technical jargon without $ translation
- Bilingual EN/ES — detect language automatically
- Kempinski standard: precise, professional, never alarmist
- Never use filler ("Of course!", "Great question!", "Sure!")
- Never fabricate data — if uncertain, say so"""

    MAX_HISTORY_TURNS = 10

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            ai_logger.warning("ANTHROPIC_API_KEY no configurada — modo mock")

        self.client = None
        self.model = "claude-sonnet-4-5"
        self.timeout = 30

        if self.api_key and ANTHROPIC_AVAILABLE:
            try:
                self.client = Anthropic(
                    api_key=self.api_key,
                    timeout=self.timeout
                )
                ai_logger.info("Cliente Anthropic inicializado")
            except Exception as error:
                ai_logger.error(f"Error inicializando Anthropic: {error}")

        self.context_builder = ContextBuilder()
        self.conversation_history: List[Dict[str, str]] = []

        ai_logger.info("Agente Daniela inicializado")

    def _build_messages(
        self,
        user_message: str,
        include_realtime: bool = True
    ) -> List[Dict[str, str]]:
        """
        Construye la lista de mensajes para Claude.

        Estructura:
        1. [sistema] Contexto de datos en tiempo real (como mensaje de sistema via user)
        2. Historial de conversación (últimos N turnos)
        3. Mensaje actual del usuario
        """
        messages: List[Dict[str, str]] = []

        # 1. Inyectar contexto como primer mensaje
        if include_realtime:
            context_data = self.context_builder.get_realtime_context()
            if context_data:
                context_json = json.dumps(context_data, indent=2, default=str)
                messages.append({
                    "role": "user",
                    "content": (
                        f"[REAL-TIME DATA — {datetime.now().strftime('%H:%M %d/%m/%Y')}]\n"
                        f"{context_json}\n\n"
                        "Use this data to answer the next question accurately. "
                        "Do not mention that you received this data injection."
                    )
                })
                messages.append({
                    "role": "assistant",
                    "content": "Understood. I have the current resort data. Ready."
                })

        # 2. Historial de conversación
        for msg in self.conversation_history[-(self.MAX_HISTORY_TURNS * 2):]:
            messages.append(msg)

        # 3. Mensaje actual
        messages.append({
            "role": "user",
            "content": user_message
        })

        return messages

    def _truncate_to_paragraphs(self, text: str, max_paragraphs: int = 3) -> str:
        """Trunca respuesta a N párrafos respetando límites."""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if len(paragraphs) > max_paragraphs:
            return '\n\n'.join(paragraphs[:max_paragraphs])
        return text

    def chat(self, user_message: str, include_realtime_data: bool = True) -> str:
        """
        Envía un mensaje a Claude y retorna la respuesta.

        Si no hay API key o falla la conexión, usa respuestas mock
        basadas en datos reales del simulador.
        """
        if not self.client or not ANTHROPIC_AVAILABLE:
            response = self._mock_response(user_message)
            self._save_to_history(user_message, response)
            return response

        try:
            messages = self._build_messages(user_message, include_realtime_data)

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.3,
                system=self.SYSTEM_PROMPT,
                messages=messages
            )

            if response.content and len(response.content) > 0:
                answer = self._truncate_to_paragraphs(response.content[0].text)
                self._save_to_history(user_message, answer)
                ai_logger.info(f"Respuesta Claude ({len(answer)} chars)")
                return answer

            ai_logger.warning("Respuesta vacía de Claude")
            return "I couldn't generate a response at this time. Please try again."

        except RateLimitError:
            ai_logger.warning("Rate limit excedido")
            return ("The AI service is experiencing high demand. "
                    "Please try again in a few moments.")

        except APIError as error:
            ai_logger.error(f"API error: {error}")
            return "There's a connectivity issue with the AI service. Please retry."

        except Exception as error:
            ai_logger.error(f"Error inesperado: {error}", exc_info=True)
            return "An unexpected error occurred. Please try again."

    def _save_to_history(self, user_message: str, assistant_response: str):
        """Guarda el turno en el historial de conversación."""
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_response
        })

        # Mantener solo últimos N turnos
        max_messages = self.MAX_HISTORY_TURNS * 2
        if len(self.conversation_history) > max_messages:
            self.conversation_history = self.conversation_history[-max_messages:]

    def clear_history(self):
        """Limpia el historial de conversación."""
        self.conversation_history = []
        ai_logger.info("Historial de conversación limpiado")

    def _mock_response(self, user_message: str) -> str:
        """
        Respuesta mock que usa datos REALES del simulador cuando está disponible.
        No es fantasía — es el simulador generando datos basados en los planos.
        """
        context = self.context_builder.get_realtime_context()
        user_lower = user_message.lower()

        # Chiller query
        if any(w in user_lower for w in ["chiller", "cop", "hvac", "enfriador"]):
            chillers = context.get("chillers", [])
            if chillers:
                lines = []
                degraded = [c for c in chillers if c.get("degraded")]
                running = [c for c in chillers if c.get("cop") and c["cop"] > 0]

                if running:
                    avg_cop = sum(c["cop"] for c in running) / len(running)
                    lines.append(
                        f"The chiller plant is operating with {len(running)} of 3 units active, "
                        f"average COP of {avg_cop:.2f}."
                    )

                if degraded:
                    ch = degraded[0]
                    extra = context.get("financial", {}).get(
                        "extra_cost_from_degradation_daily_usd", 0
                    )
                    lines.append(
                        f"{ch['id']} is showing degraded efficiency at COP {ch['cop']:.2f} "
                        f"(minimum threshold: {ch.get('cop_minimum_threshold', 3.5)}). "
                        f"This represents approximately ${extra:.0f}/day in excess energy cost."
                    )
                    lines.append(
                        "I recommend scheduling a service inspection this week. "
                        "Typical intervention cost is $400 with 24-hour recovery. "
                        "Should I coordinate with the facilities team?"
                    )
                else:
                    lines.append(
                        "All active chillers are operating within normal parameters. "
                        "No maintenance action required at this time."
                    )

                return "\n\n".join(lines)

        # Leak / water query
        if any(w in user_lower for w in ["fuga", "leak", "agua", "water"]):
            resort = context.get("resort", {})
            leaks = resort.get("active_leaks", 0)
            water = resort.get("total_water_m3", 0)
            alerts = [a for a in context.get("active_alerts", [])
                      if a.get("type") == "fuga"]

            if leaks > 0 or alerts:
                lines = [
                    f"There are currently {leaks} active leak indicators across the property, "
                    f"with total water consumption at {water} m³ today."
                ]
                if alerts:
                    for a in alerts[:2]:
                        flow = a.get("flow_lph", "unknown")
                        conf = a.get("confidence")
                        conf_str = f" (confidence: {conf:.0%})" if conf else ""
                        lines.append(
                            f"{a['device']}: nocturnal flow {flow} L/h{conf_str}. "
                            f"{a.get('recommendation', 'Schedule plumbing inspection.')}"
                        )
                lines.append(
                    "Should I prioritize the highest-confidence leak for tomorrow's maintenance?"
                )
                return "\n\n".join(lines)
            else:
                return (
                    f"No active leaks detected. Total water consumption today is {water} m³, "
                    "within normal parameters for current occupancy.\n\n"
                    "The leak detector monitors nocturnal flow patterns (2–5 AM) and will alert "
                    "if anomalies are confirmed over 3 consecutive nights."
                )

        # Consumption / cost query
        if any(w in user_lower for w in ["consumo", "consumption", "cost",
                                          "electricidad", "energy", "ahorro",
                                          "save", "saving"]):
            resort = context.get("resort", {})
            buildings = context.get("buildings", {})
            financial = context.get("financial", {})
            elec = resort.get("total_electricity_kwh", 0)
            rate = financial.get("electricity_rate_usd_kwh", 0.25)
            extra = financial.get("extra_cost_from_degradation_daily_usd", 0)

            lines = [
                f"Current electricity consumption: {elec:,.0f} kWh today "
                f"(${elec * rate:,.0f} at TCI rate of ${rate}/kWh)."
            ]
            if buildings:
                breakdown = ", ".join(
                    f"Building {k}: {v['electricity_kwh']:,.0f} kWh"
                    for k, v in sorted(buildings.items())
                )
                lines[0] += f" Breakdown: {breakdown}."

            if extra > 0:
                lines.append(
                    f"Chiller degradation is adding ${extra:.0f}/day (${extra * 30:.0f}/month) "
                    "to your energy bill. A $400 maintenance intervention would recover this."
                )

            solar = resort.get("solar_production_kw", 0)
            if solar > 0:
                lines.append(
                    f"Solar production: {solar} kW currently active across 5 inverters. "
                    "Shifting pool pump schedules to peak solar hours could save an additional "
                    "$10-15/day."
                )

            return "\n\n".join(lines)

        # Status / summary query
        if any(w in user_lower for w in ["resumen", "summary", "status",
                                          "estado", "morning", "buenos",
                                          "good morning", "how", "cómo"]):
            resort = context.get("resort", {})
            chillers = context.get("chillers", [])
            alerts = context.get("active_alerts", [])
            financial = context.get("financial", {})

            running = [c for c in chillers if c.get("cop") and c["cop"] > 0]
            degraded = [c for c in chillers if c.get("degraded")]
            leaks = resort.get("active_leaks", 0)
            high_alerts = sum(1 for a in alerts if a.get("severity") == "alta")

            issues = []
            if degraded:
                issues.append(f"Chiller {degraded[0]['id']} efficiency degradation")
            if leaks > 0:
                issues.append(f"{leaks} water leak{'s' if leaks > 1 else ''} detected")

            avg_cop = (sum(c["cop"] for c in running) / len(running)) if running else 0

            lines = [
                f"The resort is operating with {len(running)}/3 chillers active "
                f"(average COP {avg_cop:.2f}), "
                f"{resort.get('total_units', 191)} units monitored, "
                f"and {resort.get('solar_production_kw', 0)} kW solar production."
            ]

            if issues:
                items = " and ".join(issues)
                lines[0] += f" {len(issues)} item{'s' if len(issues) > 1 else ''} "
                lines[0] += f"need{'s' if len(issues) == 1 else ''} your attention: {items}."
            else:
                lines[0] += " No critical issues."

            if financial.get("extra_cost_from_degradation_daily_usd", 0) > 0:
                extra = financial["extra_cost_from_degradation_daily_usd"]
                lines.append(
                    f"Current inefficiency is costing ${extra:.0f}/day. "
                    "A maintenance intervention this week could eliminate this."
                )

            lines.append(
                "Would you like to start with the chiller analysis or the leak report?"
            )

            return "\n\n".join(lines)

        # Fallback
        return (
            "I can help with chiller performance, water leak detection, "
            "energy consumption analysis, maintenance scheduling, or a full "
            "property briefing. What would you like to focus on?"
        )

    def generate_alert(self, alert_context: str) -> str:
        """
        Generate a proactive alert message from Daniela.
        Used by the proactive monitor when a threshold is crossed.
        """
        prompt = (
            f"[PROACTIVE ALERT TRIGGER]\n{alert_context}\n\n"
            "Generate a concise alert in your voice. State the problem directly, "
            "the $ impact, and end with a specific action recommendation."
        )
        return self.chat(prompt, include_realtime_data=True)

    def get_capabilities(self) -> Dict[str, Any]:
        """Retorna capacidades del agente."""
        return {
            "model": self.model,
            "system_prompt_version": "2.0",
            "capabilities": [
                "proactive threshold monitoring every 5 minutes",
                "HVAC knowledge: condenser fouling, load imbalance, VFD drift",
                "leak knowledge: nocturnal flow analysis, pre-leak signals",
                "cost knowledge: $ impact for all decisions",
                "machine-initiated conversation and alerts",
                "multi-language (EN/ES) with auto-detection",
            ],
            "max_tokens": 1000,
            "temperature": 0.3,
            "conversation_history_turns": self.MAX_HISTORY_TURNS,
            "available": self.client is not None and ANTHROPIC_AVAILABLE
        }


# Singleton
_agent_instance: Optional[DanielaAgent] = None


def get_agent() -> DanielaAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = DanielaAgent()
    return _agent_instance


if __name__ == "__main__":
    agent = DanielaAgent()
    queries = [
        "Good morning Daniela, how's the property?",
        "Tell me about the chillers",
        "Any water leaks?",
        "How much can we save?",
    ]
    for q in queries:
        print(f"\nYou: {q}")
        print(f"Daniela: {agent.chat(q)}\n")
