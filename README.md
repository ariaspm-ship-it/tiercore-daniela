# DANIELA v0.5 — Proactive Facility Intelligence

**Data Analytics Network for Energy Logistics & Infrastructure Assessment**

AI-powered facility management for BCH-Villa Colony Resort (Kempinski), Turks & Caicos. Monitors 1,438 BMS points across 191 units and 3 x 573kW RTAG chillers.

Daniela does not wait to be asked. She monitors, detects, and communicates.

## Quick Start

```bash
# 1. Install
python -m venv backend/.venv
source backend/.venv/Scripts/activate   # Windows: backend\.venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure (optional — falls back to mock responses)
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env

# 3. Run
python main.py
# Open frontend/index.html in browser → connects to API on :8000
```

## What Runs

`python main.py` starts:
- **Simulator** — 191 units generating real BMS data
- **Leak Detector** — nocturnal flow analysis every ~1h simulated
- **Chiller Optimizer** — COP analysis, degradation detection
- **Proactive Monitor** — threshold checks every 5 minutes, generates alerts
- **Briefing Scheduler** — auto-generates executive summary at 08:00 daily
- **FastAPI** — REST API on `:8000/api/v1`

## Frontend

Open `frontend/index.html` — full-screen proactive AI feed:
- Daniela's messages appear unprompted with severity colors (red/amber/green)
- Dynamic action buttons from her recommendations
- Voice output for CRITICAL and HIGH alerts
- Text + voice input for Director queries
- Auto-polls every 30 seconds

## API Endpoints

All under `/api/v1`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Full resort context |
| GET | `/chillers` | 3 RTAG chillers with COP, degradation, days-to-threshold |
| GET | `/buildings` | Per-building electricity/water/leaks |
| GET | `/leaks` | Active water leak alerts |
| GET | `/alerts` | All alerts last 24h |
| GET | `/health` | System health check |
| GET | `/briefing` | Generate executive briefing |
| GET | `/briefing/latest` | Latest briefing (cached) |
| GET | `/proactive` | Unacknowledged proactive alerts by severity |
| POST | `/proactive/{id}/acknowledge` | Mark alert as read |
| POST | `/proactive/check` | Force immediate threshold check |
| POST | `/chat` | Chat with Daniela |
| POST | `/demo/inject-leak` | Demo: inject leak |
| POST | `/demo/degrade-chiller` | Demo: degrade chiller COP |
| POST | `/demo/reset` | Demo: reset simulator |

## Testing

```bash
pytest tests/ -v
```

## Project

- **Pilot property:** BCH-Villa Colony Resort (Kempinski), Grace Bay, Turks & Caicos
- **Scale:** 191 units, 1,438 BMS points, 4 protocols (BACnet/IP, Modbus, M-Bus, simulated)
- **Stack:** Python, FastAPI, SQLAlchemy, Claude Sonnet, vanilla JS
