#!/usr/bin/env python3

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from urllib import request
import asyncio
import json
import sys
from nplc import NPLC

app = FastAPI()

def parse_flags():
    args = sys.argv[1:]
    flags = {"red_url": "http://127.0.0.1:8000",
             "blue_url": "http://127.0.0.1:8001",
             "dashboard_url": "http://127.0.0.1:5001"}
    for i in range(len(args)):
        if args[i].startswith("--red_url") and i + 1 < len(args):
            flags["red_url"] = args[i + 1]
        elif args[i].startswith("--blue_url") and i + 1 < len(args):
            flags["blue_url"] = args[i + 1]
        elif args[i].startswith("--dashboard_url") and i + 1 < len(args):
            flags["dashboard_url"] = args[i + 1]
    return flags

flags = parse_flags()
red_url = flags["red_url"]
blue_url = flags["blue_url"]
dashboard_url = flags["dashboard_url"]

print(f"Using URLs -> red: {red_url}, blue: {blue_url}, dashboard: {dashboard_url}")

nplc = NPLC(red_url, blue_url, timeout_sec=0.5)

score_override = None
override_lock = asyncio.Lock()


class ScoreOverride(BaseModel):
    red_score: Optional[int] = None
    blue_score: Optional[int] = None


@app.post("/override_score")
async def set_override(override: ScoreOverride):
    """Set an override for red and/or blue scores. Provide at least one field."""
    global score_override
    if override.red_score is None and override.blue_score is None:
        raise HTTPException(status_code=400, detail="Provide red_score or blue_score")

    async with override_lock:
        current = (score_override or {}).copy()
        if override.red_score is not None:
            current["red_score"] = override.red_score
        if override.blue_score is not None:
            current["blue_score"] = override.blue_score
        score_override = current

    return {"override": score_override}


@app.get("/override_score")
async def get_override():
    async with override_lock:
        return {"override": score_override}


@app.delete("/override_score")
async def clear_override():

    global score_override
    async with override_lock:
        score_override = None
    return {"status": "cleared"}

def safe_hub_status(hub_name):
    try:
        status = nplc.get_hub_status(hub_name)
        return status.get("count", 0), status.get("state", False)
    except Exception:
        return 0, False

def get_match_state():
    """Get current match state from dashboard API."""
    try:
        req = request.Request(f"{dashboard_url}/match/state", method="GET")
        with request.urlopen(req, timeout=0.5) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else None
    except Exception as e:
        print(f"Error getting match state from dashboard: {e}")
        return None

def format_time(seconds: float) -> str:
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}:{secs:02d}"


async def safe_hub_status_async(hub_name):
    return await asyncio.to_thread(safe_hub_status, hub_name)

async def get_match_state_async():
    return await asyncio.to_thread(get_match_state)


@app.get("/")
def serve_audience():
    html_path = Path(__file__).parent / "scoreboard.html"
    return FileResponse(html_path)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    print("WS connection attempt")
    await ws.accept()
    print("WS connection accepted")

    phases = [
        (20.0, "AUTO", "both"),
        (30.0, "TRANSITION", "both"),
        (55.0, "SHIFT 1", "single"),
        (80.0, "SHIFT 2", "single"),
        (105.0, "SHIFT 3", "single"),
        (130.0, "SHIFT 4", "single"),
        (160.0, "END GAME", "both"),
    ]
    total_game_time = phases[-1][0]

    try:
        while True:
            match_state = await get_match_state_async()
            if match_state is None:
                await ws.send_text(json.dumps({
                    "total_time_left": "00:00",
                    "current_phase": "ERROR",
                    "time_left_in_phase": "00:00",
                    "hub_active": "NONE",
                    "red_score": 0,
                    "blue_score": 0
                }))
                await asyncio.sleep(0.03)
                continue

            time_left_total = match_state.get("match_time_left", 0)
            elapsed = match_state.get("elapsed", 0)
            current_phase = match_state.get("phase", "IDLE")
            time_left_in_phase = match_state.get("phase_time_left", 0)

            red_task = safe_hub_status_async("red")
            blue_task = safe_hub_status_async("blue")
            (red_score, red_active), (blue_score, blue_active) = await asyncio.gather(red_task, blue_task)

            blue_active = blue_active == "running"
            red_active = red_active == "running"

            if red_active and blue_active:
                hub_active = "BOTH"
            elif red_active:
                hub_active = "RED"
            elif blue_active:
                hub_active = "BLUE"
            else:
                hub_active = "NONE"
            
            # If an override is set, use those scores regardless of hub status.
            override_active = False
            async with override_lock:
                if score_override is not None:
                    override_active = True
                    if score_override.get("red_score") is not None:
                        red_score = score_override.get("red_score")
                    if score_override.get("blue_score") is not None:
                        blue_score = score_override.get("blue_score")

            data = {
                "total_time_left": format_time(time_left_total),
                "current_phase": current_phase,
                "time_left_in_phase": format_time(time_left_in_phase),
                "hub_active": hub_active,
                "red_score": red_score,
                "blue_score": blue_score,
                "override_active": override_active
            }

            await ws.send_text(json.dumps(data))
            await asyncio.sleep(0.03)

    except WebSocketDisconnect:
        print("WS client disconnected")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("nplc.scoreboard:app", host="127.0.0.1", port=5000)