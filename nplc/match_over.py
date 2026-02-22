#!/usr/bin/env python3

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from urllib import request
import asyncio
import json
import threading

app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

# Allow dashboard (127.0.0.1:5001) to call this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5001", "http://localhost:5001"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dashboard location (control authority)
red_url = "http://127.0.0.1:8000"
blue_url = "http://127.0.0.1:8001"
dashboard_url = "http://127.0.0.1:5001"


def get_match_state():
    """Get current match state from dashboard API."""
    try:
        req = request.Request(f"{dashboard_url}/match/state", method="GET")
        with request.urlopen(req, timeout=0.5) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else None
    except Exception as e:
        # Quietly return None on error so the UI can show a placeholder
        print(f"Error getting match state from dashboard: {e}")
        return None


def get_show_final():
    """Query dashboard for whether final display should be shown."""
    try:
        req = request.Request(f"{dashboard_url}/api/display", method="GET")
        with request.urlopen(req, timeout=0.5) as response:
            payload = response.read().decode("utf-8")
            j = json.loads(payload) if payload else {}
            return bool(j.get("show_final", False))
    except Exception as e:
        print(f"Error getting display state from dashboard: {e}")
        return False


async def get_match_state_async():
    return await asyncio.to_thread(get_match_state)


async def get_show_final_async():
    return await asyncio.to_thread(get_show_final)


@app.get("/")
def serve_audience():
    html_path = Path(__file__).parent / "match_over.html"
    return FileResponse(html_path)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    try:
        while True:
            match_state = await get_match_state_async()
            if match_state is None:
                payload = {
                    "running": False,
                    "red_score": 0,
                    "blue_score": 0,
                    "phase": "UNKNOWN",
                    "show_final": False,
                    "final_red": 0,
                    "final_blue": 0,
                }
                await ws.send_text(json.dumps(payload))
                await asyncio.sleep(0.1)
                continue

            # Extract scores
            red_count = match_state.get("red_count", match_state.get("red_raw_count", 0))
            blue_count = match_state.get("blue_count", match_state.get("blue_raw_count", 0))
            running = bool(match_state.get("running", False))
            phase = match_state.get("phase", "IDLE")

            sf = await get_show_final_async()

            payload = {
                "running": running,
                "phase": phase,
                "red_score": red_count,
                "blue_score": blue_count,
                "show_final": sf,
                "final_red": red_count,
                "final_blue": blue_count,
            }

            await ws.send_text(json.dumps(payload))
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        print("WS client disconnected")


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("MATCH_OVER_PORT", "5002"))
    uvicorn.run("nplc.match_over:app", host="127.0.0.1", port=port)
