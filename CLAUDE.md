# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DANIELA** (Data Analytics Network for Energy Logistics & Infrastructure Assessment) — AI-powered facility management system for luxury resorts. Simulates and monitors water, electricity, and HVAC across 191 units (BCH-VILLA COLONY RESORT, Kempinski brand).

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
# Run main orchestrator (continuous simulation)
python main.py --steps 288 --interval 0.05

# Investor demo (5-minute end-to-end)
python demo_investors.py
python demo_investors.py --test --no-slow   # fast, no voice

# Streamlit web dashboard
streamlit run frontend/dashboard.py

# Claude agent REPL
python -m ai.claude_agent

# Context builder (test realtime data feed)
python -m ai.context_builder
```

## Testing

```bash
pytest tests/ -v
pytest tests/test_quick.py          # fast smoke tests
pytest tests/test_claude_agent.py   # AI interface tests
pytest tests/test_habitaciones.py   # room model tests
```

## Windows Installer Scripts

Located in `installer/`. Run from PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File .\installer\install.ps1
powershell -ExecutionPolicy Bypass -File .\installer\healthcheck.ps1
```

## Docker Stack (Optional)

```bash
docker-compose up -d   # backend + InfluxDB + Grafana + Redis
```
Services: FastAPI `:8000`, InfluxDB `:8086`, Grafana `:3001`, Redis `:6379`.

## Architecture

### Data Flow

```
Simulator → Device Models → Database (SQLite / PostgreSQL+TimescaleDB)
         ↓
    Context Builder (30s TTL cache)
         ↓
    Claude Agent  ←  Realtime status JSON
         ↓
Dashboard (Streamlit) / FastAPI endpoints
         ↓
Alerts (LeakDetector, ChillerOptimizer) → Database
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `core/config.py` | Central config — thresholds, building layout, project metadata |
| `core/database.py` | SQLAlchemy ORM models + session management |
| `simulator/resort_simulator.py` | Drives ~2,100 logical points across all devices |
| `devices/` | Device models: `Room`, `Villa`, `Chiller`, `HeatMachine`, `Inverter`, `ElectricalPanel` |
| `ai/claude_agent.py` | Claude Sonnet conversational interface with injected context |
| `ai/context_builder.py` | Aggregates realtime simulator/DB data for Claude |
| `ai/leak_detector.py` | Nighttime flow analysis (2–5 AM), 3-night pattern, confidence score |
| `ai/chiller_optimizer.py` | COP analysis, ML efficiency models, degradation detection (>8% loss) |
| `generators/` | Factory functions for rooms, villas, buildings, BACnet/Modbus point catalogs |
| `frontend/dashboard.py` | Streamlit UI — charts, voice input, Claude chat, alerts |

### Configuration (`core/config.py`)

Key constants used throughout the codebase:
- Buildings: A (119 units), B (41), C (27), Villas (4)
- `UMBRAL_FUGA_LPH = 2.0` — leak detection threshold (L/h)
- `COP_MINIMO = 3.5` — chiller efficiency floor
- `TEMP_MAX = 28.0` — max room temperature threshold
- `MODO_SIMULACION = True` — simulation vs. live hardware

### Database Models (`core/database.py`)

- `LecturaHabitacion` — room readings (indexed: `room_id`, `building`, `timestamp`)
- `LecturaChiller` — chiller readings
- `LecturaPanel` — electrical panel readings
- `Alerta` — system alerts with severity
- `ConsumoDiario` — daily consumption aggregates

SQLite is the default (`daniela.db`). Set `DATABASE_URL` for PostgreSQL+TimescaleDB.

## Key Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | — | Claude API (optional, mock if absent) |
| `DATABASE_URL` | `sqlite:///daniela.db` | DB connection string |
| `MODO_SIMULACION` | `True` | Simulation vs. live hardware |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `UMBRAL_FUGA_LPH` | `2.0` | Leak detection threshold |
