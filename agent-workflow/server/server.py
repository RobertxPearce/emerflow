"""Streams a simulated run to the UI as Server-Sent Events.

    .venv/bin/uvicorn server:app --port 8000

GET /run?casualties=25&seed=1234&pace=1.0 → text/event-stream of protocol events.
GET /region?incident=true → JSON: every hospital's current load, for the public capacity map.
GET /simulate?lat=39.26&lon=-76.58&casualties=40 → JSON: a what-if incident played forward 3 hours.
"""

import asyncio
import json
import os
import random

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import region
import workflow
from protocol import error

app = FastAPI(title="Hospital Swarm simulation")
# Pages allowed to connect, comma-separated. Add your dashboard's URL here.
# 3000: agent-workflow demo, 3001: capacity-map demo.
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET"])


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/region")
def region_status(incident: bool = True):
    return region.snapshot(incident=incident)


@app.get("/simulate")
def simulate(lat: float, lon: float, casualties: int = 40, seed: int | None = None):
    center = region.REGION["center"]
    if region.km(lat, lon, *center) > region.MAX_INCIDENT_KM:
        raise HTTPException(400, f"Incidents must be within {region.MAX_INCIDENT_KM} km of {region.REGION['name']}.")
    return region.simulate(lat, lon, max(5, min(casualties, 120)), seed=seed)


@app.get("/run")
async def run(seed: int | None = None, casualties: int = 25, pace: float = 1.0):
    seed = seed if seed is not None else random.randint(1000, 9999)
    casualties = max(1, min(casualties, 80))

    async def events():
        try:
            for event in workflow.run(seed, casualties):
                if event["type"] == "pause":
                    await asyncio.sleep(event["seconds"] * pace)
                else:
                    yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # report to the UI instead of silently dropping the stream
            yield f"data: {json.dumps(error(f'Simulation failed (seed {seed}): {exc}'))}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
