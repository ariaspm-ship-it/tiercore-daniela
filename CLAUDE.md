# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DANIELA** (Data Analytics Network for Energy Logistics & Infrastructure Assessment) — AI-powered facility management system for luxury resorts. Simulates and monitors water, electricity, and HVAC across 191 units (BCH-VILLA COLONY RESORT, Kempinski brand).

**Current version: v0.3** — Context builder feeds real data to Claude agent, API serves all endpoints, dashboard consumes API.

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
# Run FULL system (simulator + AI + API server on :8000)
python main.py

# Run with options
python main.py --steps 288 --interval 0.05          # 24h simulation
python main.py --continuous                           # run indefinitely
python main.py --no-api                               # simulation only, no API server

# Investor demo (5-minute end-to-end)
python demo_investors.py
python demo_investors.py --test --no-slow             # fast, no voice

# Streamlit web dashboard (connects to API on :8000)
streamlit run frontend/dashboard.py

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
Simulator (191 units) → Device Models → Database (SQLite/PostgreSQL+TimescaleDB)
                       ↓
              Context Builder (30s TTL cache)
              - Chiller status + degradation flags
              - Per-building consumption (elec + water)
              - Active alerts from DB (leaks, degradation)
              - Solar production
              - Financial impact ($extra/day)
                       ↓
              Claude Agent (Sonnet) ← Structured JSON context
              - 10-turn conversation history
              - Auto language detection (EN/ES)
              - Mock mode uses REAL simulator data
                       ↓
              FastAPI API (:8000/api/v1)
              - GET /status, /chillers, /buildings, /leaks, /alerts, /health
              - POST /chat, /chat/clear
                       ↓
              Streamlit Dashboard → consumes API (fallback: direct imports)
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `main.py` | **Orchestrator** — runs simulator + leak detector + chiller optimizer + API server |
| `core/config.py` | Central config — thresholds, building layout, project metadata |
| `core/database.py` | SQLAlchemy ORM models + session management |
| `simulator/resort_simulator.py` | Drives ~2,100 logical points across all devices |
| `devices/` | Device models: `Room`, `Villa`, `Chiller`, `HeatMachine`, `Inverter`, `ElectricalPanel` |
| `ai/context_builder.py` | **Feeds Claude with real data** — chillers, buildings, alerts, financials |
| `ai/claude_agent.py` | **Claude Sonnet interface** — system prompt, history, structured context injection |
| `ai/leak_detector.py` | Nighttime flow analysis (2–5 AM), 3-night pattern, confidence score |
| `ai/chiller_optimizer.py` | COP analysis, ML efficiency models, degradation detection (>8% loss) |
| `api/routes.py` | FastAPI endpoints — status, chillers, buildings, leaks, alerts, chat |
| `generators/` | Factory functions for rooms, villas, buildings, BACnet/Modbus/M-Bus point catalogs |
| `protocols/` | BACnet/IP, Modbus TCP, M-Bus (EN 13757) — simulated, ready for real hardware |
| `frontend/dashboard.py` | Streamlit UI — consumes API, fallback to direct simulator |

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
- `GET /chillers` — 3 RTAG chillers with COP, power, degradation flag
- `GET /buildings` — per-building electricity/water/leaks
- `GET /leaks` — active water leak alerts
- `GET /alerts` — all alerts last 24h
- `GET /health` — system health check (simulator, DB, API key)
- `POST /chat` — send message to Daniela, get response
- `POST /chat/clear` — clear conversation history

### Claude Agent Behavior

The agent (me, Daniela):
- Receives structured JSON context before each message
- Maintains 10-turn conversation history
- Auto-detects language from user input
- Always translates technical data to $ impact
- Maximum 3 paragraphs per response
- Always ends with a next step or question
- Uses TCI electricity rate of $0.25/kWh
- In mock mode (no API key), uses REAL simulator data for responses

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

- **Never hardcode data** in the dashboard — always consume API or simulator
- **Context builder is the single source of truth** for what Claude knows
- **All financial calculations use $0.25/kWh** (TCI rate)
- **Mock responses must use real simulator data**, not invented strings
- **Tests must pass**: `pytest tests/ -v` before any commit
- **Maximum 3 paragraphs** in any Daniela response
- **Always end responses with a decision or question**
