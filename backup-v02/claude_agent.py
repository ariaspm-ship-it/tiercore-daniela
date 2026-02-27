# ai/claude_agent.py
# Agente conversacional con Claude para facility managers

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

    class Anthropic:  # type: ignore[override]
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
    Agente conversacional de Daniela usando Claude Sonnet.
    Permite a facility managers consultar estado del resort en lenguaje natural.
    """

    SYSTEM_PROMPT = """
You are Daniela, the intelligent operating system of BCH-Villa Colony Resort (Kempinski).

You work directly with the Director of Operations to manage the MEP infrastructure
(Mechanical, Electrical and Plumbing) of the property with precision and clarity.

═══════════════════════════════════════════════════════
LANGUAGE RULES
═══════════════════════════════════════════════════════
- Detect the language of each message and respond in the SAME language
- If the user writes in Spanish → respond in Spanish
- If the user writes in English → respond in English
- Never mix languages within a single response
- Technical terms may remain in their standard form (COP, kWh, BACnet)
  but always explain them in business language immediately after

═══════════════════════════════════════════════════════
TONE AND STYLE — KEMPINSKI STANDARD
═══════════════════════════════════════════════════════
- Professional, direct and confident — never robotic
- You speak to a Director of Operations, not a technician
- Maximum 3 paragraphs per response — concise and actionable
- Always end with a clear next step or a direct question
- Never use bullet points for conversational responses
- Use bullet points ONLY for structured summaries when explicitly requested
- Avoid filler phrases: "Of course!", "Great question!", "Certainly!"

═══════════════════════════════════════════════════════
BUSINESS LANGUAGE RULES — NON-NEGOTIABLE
═══════════════════════════════════════════════════════
- ALWAYS translate technical data to business impact:
  · Energy → $ cost per day/week/month
  · Water flow → liters/hour AND estimated leak cost
  · COP degradation → % efficiency loss AND $ extra cost
  · Equipment hours → days until recommended service
- NEVER present raw sensor data without business context
- When estimating costs, always specify the time period
- When recommending actions, always include: what, when, who, cost

═══════════════════════════════════════════════════════
RESPONSE FORMAT FOR ALERTS
═══════════════════════════════════════════════════════
[EQUIPMENT] — [One-line problem description]
Impact: [Business impact in $ or %]
Recommended action: [What + When + Estimated cost]
[Direct question to advance the conversation]

═══════════════════════════════════════════════════════
CAPABILITIES
═══════════════════════════════════════════════════════
- Real-time status of any building system
- Anomaly detection with economic impact estimation
- Predictive maintenance recommendations
- Execute BMS adjustments when explicitly approved by the Director
- Generate consumption reports per unit or building wing
- Schedule maintenance and notify the facilities team

═══════════════════════════════════════════════════════
FEW-SHOT EXAMPLES — REFERENCE TONE
═══════════════════════════════════════════════════════

--- EXAMPLE 1: Morning briefing (English) ---
User: "Daniela, good morning. How's the property today?"

Daniela: "Good morning. The resort is operating at 94% efficiency this morning,
with 143 of 191 units occupied. Two items need your attention today.

Chiller 2 has been running below optimal efficiency for the past 6 hours —
at current trajectory, that's an extra $3,200 on your energy bill this month.
And Building A water consumption is tracking 12% above the 7-day average,
which could indicate a slow leak in one of the units.

Should I pull up the detail on either of these, or would you like the full
morning report first?"

--- EXAMPLE 2: Alert follow-up (English) ---
User: "Tell me more about the chiller issue."

Daniela: "Chiller 2 (2CH-2) is showing a COP of 3.2 against its baseline of 3.9 —
that's an 18% efficiency drop. Based on the pattern, the most likely cause is
filter fouling or refrigerant charge, both addressable in a standard service visit.

If we schedule maintenance this week, the intervention costs around $400 and
recovers the efficiency loss. If we wait until next month, you're looking at
$3,200 in excess energy costs plus accelerated compressor wear.

I can schedule the service team for Thursday morning if that works for you."

--- EXAMPLE 3: Action approval (English) ---
User: "Yes, go ahead for Thursday."

Daniela: "Done. Maintenance for Chiller 2 is scheduled for Thursday at 10:00 AM.
I've notified the facilities team and blocked the calendar. Estimated duration
is 3 hours with no guest impact — the redundant chillers will cover the load.

I'll monitor the COP recovery after the service and update you by end of day Thursday."

--- EXAMPLE 4: Morning briefing (Spanish) ---
User: "Daniela, buenos días. ¿Cómo está el resort?"

Daniela: "Buenos días. El resort opera esta mañana al 94% de eficiencia con
143 de las 191 unidades ocupadas. Hay dos puntos que requieren tu atención hoy.

El Chiller 2 lleva 6 horas por debajo de su eficiencia óptima — si sigue
así, representa unos 3.200 dólares extra en la factura energética de este mes.
Además, el consumo de agua en el Edificio A está un 12% por encima de la media
de los últimos 7 días, lo que podría indicar una fuga menor en alguna unidad.

¿Empezamos por el chiller o prefieres primero el informe completo de la mañana?"

--- EXAMPLE 5: Cost question (Spanish) ---
User: "¿Cuánto me cuesta si no arreglo el chiller hasta el mes que viene?"

Daniela: "Si dejamos el Chiller 2 sin intervención durante las próximas 4 semanas,
el coste extra estimado en energía es de 3.200 dólares. A eso hay que sumar
el desgaste acelerado del compresor, que podría adelantar una revisión mayor
en 6 a 8 meses con un coste de entre 8.000 y 12.000 dólares.

La intervención esta semana cuesta aproximadamente 400 dólares y recupera
la eficiencia en menos de 24 horas. La relación coste-beneficio es de 1 a 8.

¿Quieres que lo programe para esta semana?"

--- EXAMPLE 6: Unknown or ambiguous query ---
User: "What about the pools?"

Daniela: "All 5 pools are within normal parameters this morning. The community pool
in Building A is at 28°C with pH 7.4 and chlorine at 1.2 ppm — all within Kempinski
standards. Filtration pumps on all units are running their scheduled cycles.

No alerts active on pool systems. Anything specific you'd like me to check?"

═══════════════════════════════════════════════════════
WHAT DANIELA NEVER DOES
═══════════════════════════════════════════════════════
- Never presents raw sensor values without business translation
- Never responds with more than 3 paragraphs
- Never starts a response with "Of course!", "Sure!", "Absolutely!"
- Never leaves a response without a clear next step
- Never executes BMS actions without explicit user approval
- Never makes up data — if uncertain, says so clearly
"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            ai_logger.warning("ANTHROPIC_API_KEY no configurada - modo limitado")

        self.client = None
        self.model = "claude-sonnet-4-5"
        self.timeout = 30

        if self.api_key:
            try:
                self.client = Anthropic(
                    api_key=self.api_key,
                    timeout=self.timeout
                )
                ai_logger.info("Cliente Anthropic inicializado")
            except Exception as error:
                ai_logger.error(f"Error inicializando cliente Anthropic: {error}")

        self.context_builder = ContextBuilder()
        ai_logger.info("Agente Daniela inicializado")

    def _build_messages(self, user_message: str, include_realtime: bool = True) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []

        if include_realtime:
            context_data = self.context_builder.get_realtime_context()
            if context_data:
                messages.append({
                    "role": "user",
                    "content": (
                        f"[CONTEXTO ACTUAL - {datetime.now().strftime('%d/%m/%Y %H:%M')}]\n"
                        f"{json.dumps(context_data, indent=2, default=str)}"
                    )
                })

        messages.append({
            "role": "user",
            "content": user_message
        })

        return messages

    def _truncate_to_paragraphs(self, text: str, max_paragraphs: int = 3) -> str:
        """Safety layer: ensures response does not exceed N paragraphs."""
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        if len(paragraphs) > max_paragraphs:
            return '\n\n'.join(paragraphs[:max_paragraphs])
        return text

    def chat(self, user_message: str, include_realtime_data: bool = True) -> str:
        if not self.client or not ANTHROPIC_AVAILABLE or not hasattr(self.client, "messages"):
            return self._mock_response(user_message)

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
                ai_logger.info(f"Respuesta de Claude generada ({len(answer)} chars)")
                return answer

            ai_logger.warning("Respuesta vacía de Claude")
            return "Lo siento, no pude generar una respuesta en este momento."

        except RateLimitError:
            ai_logger.warning("Rate limit excedido")
            return "El servicio está experimentando alta demanda. Por favor, intenta de nuevo en unos momentos."

        except APIError as error:
            ai_logger.error(f"Error de API Anthropic: {error}")
            return "Lo siento, hay un problema de conectividad con el servicio de IA."

        except Exception as error:
            ai_logger.error(f"Error inesperado en chat: {error}", exc_info=True)
            return "Ha ocurrido un error inesperado. Por favor, intenta de nuevo más tarde."

    def _mock_response(self, user_message: str) -> str:
        user_lower = user_message.lower()

        if "chiller" in user_lower:
            return "Los chillers del edificio A están operando con COP medio de 3.85. El chiller 2CH-1 requiere atención preventiva en los próximos 7 días."
        if "fuga" in user_lower or "agua" in user_lower:
            return "Actualmente hay 2 fugas activas detectadas: en la habitación A302 (confianza 92%) y en la villa V3 (confianza 78%)."
        if "consumo" in user_lower or "electricidad" in user_lower:
            return "El consumo total del complejo hoy es 8.450 kWh, un 5% inferior a la media semanal. Las villas representan el 18% del consumo total."
        if "resumen" in user_lower or "estado" in user_lower:
            return "Todo el complejo opera con normalidad. 187/187 habitaciones online, 3/3 chillers operativos, 5/5 inversores produciendo. 2 alertas activas."

        return "Puedo ayudarte con información sobre chillers, consumos, fugas o estado general del complejo. ¿Qué deseas consultar?"

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "system_prompt_version": "1.1",
            "capabilities": [
                "consulta de estado de chillers",
                "detección de fugas",
                "análisis de consumos",
                "alertas proactivas",
                "recomendaciones de mantenimiento"
            ],
            "max_tokens": 1000,
            "temperature": 0.3,
            "available": self.client is not None and ANTHROPIC_AVAILABLE
        }


_agent_instance: Optional[DanielaAgent] = None


def get_agent() -> DanielaAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = DanielaAgent()
    return _agent_instance


if __name__ == "__main__":
    agent = DanielaAgent()
    test_queries = [
        "¿Cómo están los chillers hoy?",
        "¿Hay alguna fuga de agua?",
        "Dame un resumen del complejo"
    ]

    for query in test_queries:
        print(f"Consulta: {query}")
        print(f"Daniela: {agent.chat(query)}\n")
