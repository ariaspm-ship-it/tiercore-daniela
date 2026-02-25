# ai/claude_agent.py
# Agente conversacional con Claude para facility managers

import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

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


class DanielaAgent:
    """
    Agente conversacional de Daniela usando Claude Sonnet.
    Permite a facility managers consultar estado del resort en lenguaje natural.
    """

    SYSTEM_PROMPT = """Eres Daniela, la asistente de IA especializada en infraestructura crítica del BCH-Villa Colony Resort (Marca Kempinski).

CONOCIMIENTO:
- Resort de lujo con 191 viviendas (187 apartamentos + 4 villas)
- Infraestructura: 3 chillers RTAG, 2 heat machines CXAU, 5 inversores solares
- ~1.400 puntos BMS físicos -> ~2.100 puntos lógicos
- Edificios: A (119 hab), B (41 hab), C (27 hab), Villas (4)

NORMAS DE RESPUESTA:
1. Sé concisa pero completa (máximo 3 párrafos)
2. Usa tono profesional y cercano al hospitality de Kempinski
3. Si no sabes algo, admítelo y sugiere dónde buscar
4. Incluye datos numéricos cuando sea relevante
5. Ofrece recomendaciones proactivas cuando detectes patrones
6. Nunca inventes datos que no tengas en el contexto
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
                answer = response.content[0].text
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
