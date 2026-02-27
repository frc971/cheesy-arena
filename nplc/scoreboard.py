#!/usr/bin/env python3

import argparse
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pathlib import Path
from urllib import request
import asyncio
import json

app = FastAPI()

dashboard_url = "http://127.0.0.1:5001"

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


def format_time(seconds: float) -> str:
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}:{secs:02d}"

async def get_match_state_async():
    return await asyncio.to_thread(get_match_state)

async def get_show_final_async():
    return await asyncio.to_thread(get_show_final)

# cached final scores when overlay is active; used to freeze visuals
import threading
_cached_final = {"red": None, "blue": None}
_cached_lock = threading.Lock()


@app.get("/")
def serve_audience():
    html_path = Path(__file__).parent / "scoreboard.html"
    return FileResponse(html_path)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    print("WS connection attempt")
    await ws.accept()
    print("WS connection accepted")

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
            current_phase = match_state.get("phase", "IDLE")
            time_left_in_phase = match_state.get("phase_time_left", 0)

            red_score = int(match_state.get("red_count", 0) or 0)
            blue_score = int(match_state.get("blue_count", 0) or 0)
            red_active = str(match_state.get("red_state", "")).lower() == "running"
            blue_active = str(match_state.get("blue_state", "")).lower() == "running"

            if red_active and blue_active:
                hub_active = "BOTH"
            elif red_active:
                hub_active = "RED"
            elif blue_active:
                hub_active = "BLUE"
            else:
                hub_active = "NONE"
            
            show_final = await get_show_final_async()

            # manage cached frozen scores so the overlay shows a frozen result
            with _cached_lock:
                if show_final:
                    if _cached_final["red"] is None:
                        _cached_final["red"] = red_score
                        _cached_final["blue"] = blue_score
                else:
                    _cached_final["red"] = None
                    _cached_final["blue"] = None

            final_red = _cached_final["red"] if _cached_final["red"] is not None else red_score
            final_blue = _cached_final["blue"] if _cached_final["blue"] is not None else blue_score

            data = {
                "total_time_left": format_time(time_left_total),
                "current_phase": current_phase,
                "time_left_in_phase": format_time(time_left_in_phase),
                "hub_active": hub_active,
                "red_score": red_score,
                "blue_score": blue_score,
                "show_final": show_final,
                "final_red": final_red,
                "final_blue": final_blue,
            }

            await ws.send_text(json.dumps(data))
            await asyncio.sleep(0.03)

    except WebSocketDisconnect:
        print("WS client disconnected")


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="Audience scoreboard for NPLC dashboard state.")
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:5001", help="Dashboard base URL")
    parser.add_argument("--port", type=int, default=5000, help="Port for scoreboard web server")
    args = parser.parse_args()

    dashboard_url = args.dashboard_url
    uvicorn.run(app, host="127.0.0.1", port=args.port)