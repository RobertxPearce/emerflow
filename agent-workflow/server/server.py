"""Streams a simulated run to the UI as Server-Sent Events.

    .venv/bin/uvicorn server:app --port 8000

GET /run?casualties=25&seed=1234&pace=1.0 → text/event-stream of protocol events.
"""

import asyncio
import json
import os
import random

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import workflow
from protocol import error

app = FastAPI(title="Hospital Swarm simulation")
# Pages allowed to connect, comma-separated. Add your dashboard's URL here.
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET"])


@app.get("/health")
def health():
    return {"ok": True}


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
