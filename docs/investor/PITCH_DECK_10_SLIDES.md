# DANIELA by TierCore — Pitch Deck (10 slides)

## Slide 1 — Portada
- DANIELA — Infrastructure Kernel para hoteles y resorts de lujo
- Subtítulo: IA aplicada a eficiencia operativa, agua y energía
- Proyecto piloto: BCH-Villa Colony Resort (Kempinski), Turks & Caicos
- Estado: sistema funcional v0.5 — IA proactiva

Notas del presentador:
- Abrir con problema concreto: costos crecientes de energía/agua y operación fragmentada BMS.
- Posicionar DANIELA como capa inteligente sobre infraestructura existente.

## Slide 2 — Problema
- Operación BMS fragmentada por fabricante/protocolo
- Baja visibilidad en tiempo real de fugas y degradación de equipos
- Decisiones reactivas, no predictivas
- Coste operativo elevado + riesgo reputacional por fallos en hospitality premium

Datos sugeridos en slide:
- Energía HVAC y agua como drivers principales del OPEX técnico.

## Slide 3 — Solución
- DANIELA unifica datos técnicos de habitaciones, villas y equipos críticos
- Detección inteligente de fugas (patrón nocturno + contexto edificio)
- Optimización operativa de chillers (COP, secuencia, ahorro diario)
- Arquitectura preparada para escalar a protocolos y analítica avanzada

Mensaje clave:
- “No reemplaza el BMS: lo vuelve inteligente y accionable.”

## Slide 4 — Producto hoy (v0.5)
- Sistema proactivo: Daniela monitorea e inicia conversación sin que le pregunten
- 191 viviendas, 1,438 puntos BMS, 3 chillers RTAG 573kW
- 6 módulos IA: Proactive Monitor, Briefing Scheduler, Claude Agent, Leak Detector, Chiller Optimizer, Context Builder
- API REST completa (FastAPI, 15 endpoints)
- Frontend proactivo: feed de alertas con severidad, botones de acción, voz
- 4 protocolos: BACnet/IP, Modbus, M-Bus, simulación

Activos técnicos:
- Conocimiento HVAC, fugas y costes embebido en el agente. Tests automatizados. CI-ready.

## Slide 5 — Tracción técnica y validación
- Habitación/viviendas corregidas: 187 aptos + 4 villas
- 2.100+ puntos lógicos simulados (objetivo técnico alcanzado)
- Suite de pruebas:
  - test_habitaciones
  - test_ai
  - test_quick
- Repositorio sincronizado y flujo CI-ready

Mensaje:
- “Ya no es un concepto: es un sistema ejecutable y demostrable.”

## Slide 6 — Mercado y oportunidad
- Segmento inicial: hospitality de lujo y resorts multiedificio
- Dolor recurrente: energía, agua, mantenimiento y cumplimiento SLA experiencia huésped
- Estrategia go-to-market inicial:
  - 1) Piloto técnico
  - 2) Caso de ahorro documentado
  - 3) Escalado a cadena / property portfolio

Narrativa:
- “Entramos por ahorro y control operativo; expandimos por inteligencia predictiva.”

## Slide 7 — Modelo de negocio
- Setup inicial (implantación + integración)
- Suscripción mensual por propiedad (SaaS + soporte)
- Add-ons premium:
  - Predictive maintenance
  - Executive dashboard multi-site
  - Benchmarking entre propiedades

Indicadores financieros a mostrar:
- CAC piloto, payback esperado, margen bruto software.

## Slide 8 — Ventaja competitiva
- Agnóstico de fabricante (evita lock-in del proveedor BMS)
- Contexto hospitality (no solo telemetría industrial genérica)
- Arquitectura modular IA + protocolos
- Time-to-value rápido con modo simulado + transición progresiva a real

Comparativo sugerido:
- DANIELA vs BMS tradicional vs consultoría manual puntual.

## Slide 9 — Roadmap 90 días
- Mes 1:
  - Orquestación main.py completa
  - Persistencia activa en simulador
- Mes 2:
  - Protocolos adicionales (BACnet MSTP, M-Bus)
  - API / endpoints de estado y alertas
- Mes 3:
  - Dashboard ejecutivo
  - Demo comercial grabada + caso ROI

Hito comercial:
- Primer piloto formal con KPIs firmados.

## Slide 10 — Ask de inversión
- Objetivo: acelerar de prototipo a piloto comercial productivo
- Uso de fondos (ejemplo):
  - Producto e integración
  - Comercial técnico B2B
  - Seguridad y observabilidad
- Entregables esperados en 6 meses:
  - Piloto validado
  - Métricas de ahorro reales
  - Pipeline comercial inicial

Cierre:
- “Estamos en el punto ideal: riesgo técnico reducido y valor económico claro.”

---

## Apéndice — KPIs para business angels
- Técnicos:
  - Uptime plataforma
  - Latencia de detección de eventos
  - Precisión de alertas (fugas/degradación)
- Negocio:
  - Ahorro €/día por propiedad
  - Tiempo de respuesta operativo
  - Conversión piloto → contrato anual
