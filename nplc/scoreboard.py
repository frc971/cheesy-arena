#!/usr/bin/env python3

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pathlib import Path
import asyncio
import time
import json
from nplc import NPLC  # make sure this is installed and works

# -------------------------------
# Create FastAPI app first
# -------------------------------
app = FastAPI()

# -------------------------------
# NPLC setup
# -------------------------------
red_url = "http://127.0.0.1:8000"
blue_url = "http://127.0.0.1:8001"
nplc = NPLC(red_url, blue_url, timeout_sec=0.5)

# -------------------------------
# Safe hub status helper
# -------------------------------
def safe_hub_status(hub_name):
    """Return hub status safely, defaults if hub is unreachable."""
    try:
        status = nplc.get_hub_status(hub_name)
        return status.get("count", 0), status.get("state", False)
    except Exception:
        return 0, False

def format_time(seconds: float) -> str:
    """Convert seconds to MM:SS format with leading zeros."""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}:{secs:02d}"


async def safe_hub_status_async(hub_name):
    """Run the blocking safe_hub_status in a thread so it doesn't block the event loop."""
    return await asyncio.to_thread(safe_hub_status, hub_name)

# -------------------------------
# Serve HTML at /
# -------------------------------
@app.get("/")
def serve_audience():
    html_path = Path(__file__).parent / "audience.html"
    return FileResponse(html_path)

# -------------------------------
# WebSocket endpoint for real-time updates
# -------------------------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    print("WS connection attempt")
    await ws.accept()
    print("WS connection accepted")
    start_time = time.time()

    # Phase definitions
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
            elapsed = time.time() - start_time
            time_left_total = max(0, total_game_time - elapsed)

            # Determine current phase
            current_phase = phases[-1][1]
            time_left_in_phase = 0
            for i, (phase_end, phase_name, _) in enumerate(phases):
                if elapsed <= phase_end:
                    current_phase = phase_name
                    phase_start = 0 if i == 0 else phases[i - 1][0]
                    time_left_in_phase = max(0, phase_end - elapsed)
                    break

            # Query both hubs concurrently
            red_task = safe_hub_status_async("red")
            blue_task = safe_hub_status_async("blue")
            (red_score, red_active), (blue_score, blue_active) = await asyncio.gather(red_task, blue_task)

            # Determine hub active string
            if red_active and blue_active:
                hub_active = "RED, BLUE"
            elif red_active:
                hub_active = "RED"
            elif blue_active:
                hub_active = "BLUE"
            else:
                hub_active = "NONE"

            # Send data to WebSocket
            data = {
                "total_time_left": format_time(time_left_total),
                "current_phase": current_phase,
                "time_left_in_phase": format_time(time_left_in_phase),
                "hub_active": hub_active,
                "red_score": red_score,
                "blue_score": blue_score
            }

            await ws.send_text(json.dumps(data))

            # Smooth FPS (~30–60)
            await asyncio.sleep(0.03)

    except WebSocketDisconnect:
        print("WS client disconnected")
