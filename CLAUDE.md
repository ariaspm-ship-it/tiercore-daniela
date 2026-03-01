# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DANIELA** (Data Analytics Network for Energy Logistics & Infrastructure Assessment) — AI-powered facility management system for luxury resorts. Simulates and monitors water, electricity, and HVAC across 191 units (BCH-VILLA COLONY RESORT, Kempinski brand).

**Current version: v0.5** — Proactive AI monitor. Daniela does not wait to be asked — she monitors, detects, and communicates. Machine-initiated conversation.

## Core Philosophy (v0.5)

Daniela is not a reactive dashboard. She is a proactive facility intelligence that:
- Scans all thresholds every 5 minutes via background thread
- Generates unprompted alerts when thresholds are crossed
- Always communicates in $ impact, never raw sensor data
- Ends every message with a decision for the Director to approve
- The human responds to Daniela, not the other way around

## Environment Setup

```bash
# Create venv and install dependencies
python -m venv backend/.venv
source backend/.venv/Scripts/activate  # Windows: backend\.venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env (optional — falls back to mock responses)
```

## Common Commands

```bash
# Run FULL system (simulator + AI + proactive monitor + briefing scheduler + API on :8000)
python main.py

# Run with options
python main.py --steps 288 --interval 0.05          # 24h simulation
python main.py --continuous                           # run indefinitely
python main.py --no-api                               # simulation only, no API server

# Investor demo (5-minute end-to-end)
python demo_investors.py
python demo_investors.py --test --no-slow             # fast, no voice

# Proactive AI feed (open in browser, API must be running)
# Open frontend/index.html directly — connects to API on :8000

# Claude agent REPL (direct, no API)
python -m ai.claude_agent

# Context builder test
python -m ai.context_builder

# Generate BMS point mapping files
python -m generators.point_mapping
```

## Testing

```bash
pytest tests/ -v
pytest tests/test_quick.py          # fast smoke tests
pytest tests/test_claude_agent.py   # AI interface tests
pytest tests/test_habitaciones.py   # room model tests
pytest tests/test_ai.py             # leak detector + chiller optimizer
```

## Architecture

### Data Flow

```
Simulator (191 units) -> Device Models -> Database (SQLite/PostgreSQL+TimescaleDB)
                       |
              Context Builder (30s TTL cache)
              - Chiller status + degradation flags
              - Per-building consumption (elec + water)
              - Active alerts from DB (leaks, degradation)
              - Solar production
              - Financial impact ($extra/day)
                       |
              Claude Agent (Sonnet) <- Full HVAC/leak/cost knowledge base
              - 10-turn conversation history
              - Proactive alert generation via generate_alert()
              - Auto language detection (EN/ES)
              - Mock mode uses REAL simulator data
                       |
              Proactive Monitor (background thread, 5-min cycle)
              - COP degradation → alert with $/day + days to critical
              - Leak detection → alert with location + damage timeline
              - Load imbalance → resequencing with $ savings
              - Capacity critical → emergency escalation
                       |
              Briefing Scheduler (daily at 08:00)
              - Auto-generates 3-paragraph executive summary
              - On-demand if no briefing today
                       |
              FastAPI API (:8000/api/v1)
              - GET /status, /chillers, /buildings, /leaks, /alerts, /health
              - GET /briefing, /briefing/latest
              - GET /proactive (unacknowledged alerts by severity)
              - POST /proactive/{id}/acknowledge, /proactive/check
              - POST /chat, /chat/clear
              - POST /demo/inject-leak, /demo/degrade-chiller, /demo/reset
                       |
              Proactive AI Feed (frontend/index.html)
              - Full-screen dark interface, no charts/tables
              - Daniela's messages appear unprompted with severity colors
              - Dynamic action buttons from recommendations
              - Voice output for CRITICAL/HIGH alerts
              - Auto-polls every 30 seconds
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `main.py` | **Orchestrator** — runs simulator + leak detector + chiller optimizer + proactive monitor + briefing scheduler + API |
| `core/config.py` | Central config — thresholds, building layout, project metadata |
| `core/database.py` | SQLAlchemy ORM models + session management |
| `simulator/resort_simulator.py` | Drives ~2,100 logical points across all devices |
| `devices/` | Device models: `Room`, `Villa`, `Chiller`, `HeatMachine`, `Inverter`, `ElectricalPanel` |
| `ai/context_builder.py` | **Feeds Claude with real data** — chillers, buildings, alerts, financials |
| `ai/claude_agent.py` | **Claude Sonnet interface** — full HVAC/leak/cost knowledge base, proactive alert generation |
| `ai/proactive_monitor.py` | **Proactive threshold monitor** — background thread, 5-min cycle, severity-based alerts |
| `ai/briefing.py` | **Daily briefing scheduler** — 08:00 auto-generation, on-demand, in-memory store |
| `ai/leak_detector.py` | Nighttime flow analysis (2-5 AM), 3-night pattern, confidence score |
| `ai/chiller_optimizer.py` | COP analysis, ML efficiency models, degradation detection (>8%), days-to-threshold prediction |
| `api/routes.py` | FastAPI endpoints — status, chillers, buildings, leaks, alerts, chat, briefing, proactive, demo |
| `generators/` | Factory functions for rooms, villas, buildings, BACnet/Modbus/M-Bus point catalogs |
| `protocols/` | BACnet/IP, Modbus TCP, M-Bus (EN 13757) — simulated, ready for real hardware |
| `frontend/index.html` | **Proactive AI feed** — full-screen, severity-colored messages, action buttons, voice |
| `frontend/dashboard.py` | Streamlit UI — alternative dashboard, consumes API |

### Daniela's Knowledge Base (system prompt)

HVAC:
- Condenser fouling: COP drop 0.3-0.5 over 6-8 weeks. $800 preventive vs $18,000 emergency.
- Chiller load imbalance: >40pp spread = 15-20% energy penalty ($27,000-$48,000/year)
- VFD pressure drift: >8% deviation for >2h = guest comfort risk
- Fan coil valves: exercise before guest arrival after >7 day vacancy

Leaks:
- 70% fan coil flex connections, 20% zone valves, 10% manifolds
- Detection: 2-5am nocturnal flow, >8 L/h in vacant room = active leak
- Pre-leak: 3-5 nights anomalous consumption before visible damage
- Cost: immediate = $400 repair, undetected 72h = $3,000-$8,000

Decision thresholds:
- COP >8% below baseline → alert
- Nocturnal flow >8 L/h vacant → leak alert
- Load imbalance >40pp → resequencing
- Occupied room >26C >15min → immediate escalation
- Chiller offline + capacity <80% → emergency

### Configuration (`core/config.py`)

Key constants used throughout:
- Buildings: A (119 units), B (41), C (27), Villas (4) = **191 total**
- `UMBRAL_FUGA_LPH = 2.0` — leak detection threshold (L/h)
- `UMBRAL_COP_MINIMO = 3.5` — chiller efficiency floor
- `UMBRAL_TEMP_MAXIMA = 28` — max room temperature
- `MODO_SIMULACION = True` — simulation vs. live hardware
- Electricity rate: **$0.25/kWh** (Turks & Caicos Islands)

### Database Models (`core/database.py`)

- `LecturaHabitacion` — room readings (indexed: `room_id`, `building`, `timestamp`)
- `LecturaChiller` — chiller readings
- `LecturaPanel` — electrical panel readings
- `Alerta` — system alerts with severity (alta/media/baja)
- `ConsumoDiario` — daily consumption aggregates

SQLite default (`daniela.db`). Set `DATABASE_URL` for PostgreSQL+TimescaleDB.

### API Endpoints (`api/routes.py`)

All under `/api/v1`:
- `GET /status` — full resort context (cached 30s)
- `GET /chillers` — 3 RTAG chillers with COP, power, degradation flag, days_to_threshold
- `GET /buildings` — per-building electricity/water/leaks
- `GET /leaks` — active water leak alerts (DB + in-flight simulator leaks)
- `GET /alerts` — all alerts last 24h
- `GET /health` — system health check (simulator, DB, API key)
- `GET /briefing` — generate executive daily briefing
- `GET /briefing/latest` — latest briefing (cached, on-demand if none today)
- `GET /proactive` — unacknowledged proactive alerts ordered by severity
- `POST /proactive/{id}/acknowledge` — mark alert as read
- `POST /proactive/check` — force immediate threshold check
- `POST /chat` — send message to Daniela, get response
- `POST /chat/clear` — clear conversation history
- `POST /demo/inject-leak` — inject leak in Building B (demo)
- `POST /demo/degrade-chiller` — degrade 2CH-2 COP by 20% (demo)
- `POST /demo/reset` — reset simulator to normal state (demo)

### Proactive Monitor (`ai/proactive_monitor.py`)

Background thread checks every 300 seconds:
1. COP degradation on any chiller → HIGH alert with $/day impact
2. Load imbalance >40pp → INFO alert with $/year waste
3. Active leaks → HIGH/CRITICAL based on flow rate
4. Capacity critical (offline chiller + >80% utilization) → CRITICAL

Alerts stored in thread-safe `ProactiveAlertStore` (in-memory).
Severity: CRITICAL > HIGH > INFO.

### Proactive AI Feed (`frontend/`)

The HTML interface (`index.html` + `styles.css` + `dashboard.js`):
- **Design**: Full-screen dark, no charts/tables/heatmaps — just Daniela talking
- **Feed**: Messages with severity-colored left borders (red=CRITICAL, amber=HIGH, green=INFO)
- **Action buttons**: Extracted from "Should I..." / "Shall I..." patterns in Daniela's messages
- **Voice**: Auto-speaks CRITICAL and HIGH alerts aloud
- **Input**: Text + voice input at bottom for Director queries
- **Polling**: GET /proactive every 30 seconds for new alerts
- **Briefing**: Loads morning briefing on empty feed

## Key Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | — | Claude API (optional, mock if absent) |
| `DATABASE_URL` | `sqlite:///daniela.db` | DB connection string |
| `MODO_SIMULACION` | `True` | Simulation vs. live hardware |
| `DANIELA_API_URL` | `http://localhost:8000/api/v1` | API URL for dashboard |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `UMBRAL_FUGA_LPH` | `2.0` | Leak detection threshold |

## Development Rules

- **Never hardcode data** in the frontend — always consume API
- **Context builder is the single source of truth** for what Claude knows
- **All financial calculations use $0.25/kWh** (TCI rate)
- **Mock responses must use real simulator data**, not invented strings
- **Tests must pass**: `pytest tests/ -v` before any commit
- **Maximum 3 paragraphs** in any Daniela response
- **Always end responses with a decision or question**
- **Daniela speaks first** — proactive alerts, not reactive queries
