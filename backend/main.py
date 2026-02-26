#!/usr/bin/env python3
# backend/main.py — Daniela API Server v2.0
# FastAPI entry-point; mounts api/routes.py under /api/v1

import sys
from pathlib import Path

# Ensure project root is on sys.path when running from backend/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.routes import router
from core.config import Config
from core.logger import main_logger

app = FastAPI(
    title="Daniela API",
    description=(
        "AI-powered facility management system for "
        "BCH-VILLA COLONY RESORT (Kempinski). "
        "Monitors water, electricity, and HVAC across 191 units."
    ),
    version=Config.PROYECTO_VERSION,
)

# CORS — allow all origins so the Streamlit dashboard and any
# external client can reach the API without extra configuration.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all Daniela endpoints under /api/v1
app.include_router(router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "Daniela — Facility Intelligence System",
        "project": Config.PROYECTO_NOMBRE,
        "version": Config.PROYECTO_VERSION,
        "docs":    "/docs",
        "api":     "/api/v1",
    }


if __name__ == "__main__":
    main_logger.info("Starting Daniela API server on :8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
