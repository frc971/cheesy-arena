import argparse
import random
import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn

from nplc import NPLC

DEACTIVATION_GRACE_SEC = 3.0
STATUS_POLL_MAX_HZ = 10.0


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Dashboard:
    def __init__(self, red_url, blue_url, rate_hz, timeout_sec):
        self.nplc = NPLC(red_url, blue_url, timeout_sec=timeout_sec)
        self.sleep_s = 1.0 / max(rate_hz, 0.1)
        self.status_poll_sleep_s = 1.0 / STATUS_POLL_MAX_HZ
        self.timeline = self._build_timeline()
        self.match_end = self.timeline[-1][0]

        self.running = False
        self.start_time = None
        self.paused_elapsed = 0.0
        self.shift1_active = None
        self.last_message = "idle"

        self.hub_active = {"red": False, "blue": False}
        self.hub_lights_on = {"red": False, "blue": False}
        self.light_control_supported = {"red": True, "blue": True}
        self.stop_at = {"red": None, "blue": None}

        # Manual offsets applied on top of raw hub counts.
        self.score_adjust = {"red": 0, "blue": 0}

        self.control_lock = threading.Lock()
        self.match_state_lock = threading.Lock()
        self.status_cache_lock = threading.Lock()
        self.status_cache = {
            "red": {"count": 0, "state": "stopped"},
            "blue": {"count": 0, "state": "stopped"},
        }
        self.match_state = {
            "running": False,
            "elapsed": 0,
            "match_time_left": self.match_end,
            "phase": "IDLE",
            "phase_time_left": 0,
            "shift_active": "none",
            "red_raw_count": 0,
            "red_adjust": 0,
            "red_count": 0,
            "red_state": "stopped",
            "blue_raw_count": 0,
            "blue_adjust": 0,
            "blue_count": 0,
            "blue_state": "stopped",
            "last_message": self.last_message,
        }

    def _build_timeline(self):
        return [
            (20.0, "AUTO", "both"),
            (30.0, "TRANSITION", "both"),
            (55.0, "SHIFT 1", "single"),
            (80.0, "SHIFT 2", "single"),
            (105.0, "SHIFT 3", "single"),
            (130.0, "SHIFT 4", "single"),
            (160.0, "END GAME", "both"),
        ]

    def _start_hub(self, hub):
        try:
            self.nplc.start_hub_counting(hub)
            self.hub_active[hub] = True
        except RuntimeError as exc:
            self.last_message = f"error starting {hub}: {exc}"

    def _stop_hub(self, hub):
        try:
            self.nplc.stop_hub_counting(hub)
            self.hub_active[hub] = False
        except RuntimeError as exc:
            self.last_message = f"error stopping {hub}: {exc}"

    def _reset_hubs(self):
        try:
            self.nplc.reset_hub_count("red")
            self.nplc.reset_hub_count("blue")
            self.hub_active = {"red": False, "blue": False}
            self.hub_lights_on = {"red": False, "blue": False}
            self.stop_at = {"red": None, "blue": None}
        except RuntimeError as exc:
            self.last_message = f"error resetting hubs: {exc}"

    def _set_hub_lights(self, hub, on):
        if not self.light_control_supported[hub]:
            return
        if self.hub_lights_on[hub] == on:
            return
        try:
            if on:
                self.nplc.turn_hub_lights_on(hub)
            else:
                self.nplc.turn_hub_lights_off(hub)
            self.hub_lights_on[hub] = on
        except RuntimeError as exc:
            self.light_control_supported[hub] = False
            self.last_message = f"warning: {hub} lights endpoint unavailable: {exc}"

    def _schedule_stop(self, hub, now):
        if self.hub_active[hub] and self.stop_at[hub] is None:
            self.stop_at[hub] = now + DEACTIVATION_GRACE_SEC

    def _ensure_active(self, hub):
        if self.stop_at[hub] is not None:
            self.stop_at[hub] = None
        if not self.hub_active[hub]:
            self._start_hub(hub)

    def _update_stops(self, now):
        for hub in ("red", "blue"):
            if self.stop_at[hub] is not None and now >= self.stop_at[hub]:
                self.stop_at[hub] = None
                self._stop_hub(hub)

    def _choose_shift1_active(self):
        try:
            red_status = self._get_cached_status("red")
            blue_status = self._get_cached_status("blue")
            red_auto = _safe_int(red_status.get("count", 0))
            blue_auto = _safe_int(blue_status.get("count", 0))
        except Exception as exc:
            self.last_message = f"error reading auto counts: {exc}"
            red_auto = 0
            blue_auto = 0

        if red_auto == blue_auto:
            winner = random.choice(["red", "blue"])
            self.last_message = f"auto tie, random winner {winner}"
        else:
            winner = "red" if red_auto > blue_auto else "blue"
            self.last_message = f"auto winner {winner}"

        return "blue" if winner == "red" else "red"

    def _active_for_shift(self, index):
        if index % 2 == 1:
            return self.shift1_active
        return "blue" if self.shift1_active == "red" else "red"

    def _desired_state(self, elapsed):
        for idx, (end, phase, mode) in enumerate(self.timeline):
            if elapsed < end:
                if mode == "both":
                    return {"red": True, "blue": True}, phase, end - elapsed, "both"
                if self.shift1_active is None:
                    self.shift1_active = self._choose_shift1_active()
                active = self._active_for_shift(idx - 1)
                return (
                    {"red": active == "red", "blue": active == "blue"},
                    phase,
                    end - elapsed,
                    active,
                )
        return {"red": False, "blue": False}, "POST", 0, "none"

    def _poll_status(self, hub):
        try:
            return self.nplc.get_hub_status(hub)
        except RuntimeError as exc:
            return {"count": 0, "state": str(exc)}

    def _get_cached_status(self, hub):
        with self.status_cache_lock:
            return dict(self.status_cache[hub])

    def _set_cached_status(self, hub, status):
        with self.status_cache_lock:
            self.status_cache[hub] = dict(status)

    def _compute_live_timing(self, now=None):
        if now is None:
            now = time.time()

        start_time = self.start_time
        paused_elapsed = self.paused_elapsed
        running = bool(self.running and start_time is not None)

        if running:
            elapsed = max(0.0, now - start_time)
        else:
            elapsed = max(0.0, float(paused_elapsed or 0.0))

        phase = "IDLE"
        phase_left = 0.0
        shift_active = "none"

        if running:
            for idx, (end, phase_name, mode) in enumerate(self.timeline):
                if elapsed < end:
                    phase = phase_name
                    phase_left = max(0.0, end - elapsed)
                    if mode == "both":
                        shift_active = "both"
                    elif self.shift1_active is None:
                        shift_active = "pending"
                    else:
                        shift_active = self._active_for_shift(idx - 1)
                    break
            else:
                phase = "POST"
                phase_left = 0.0
                shift_active = "none"

        return {
            "running": running,
            "elapsed": elapsed,
            "match_time_left": max(0, int(round(self.match_end - elapsed))),
            "phase": phase,
            "phase_time_left": phase_left,
            "shift_active": shift_active,
        }

    def _start_game_locked(self):
        self._reset_hubs()
        self._start_hub("red")
        self._start_hub("blue")
        self.score_adjust = {"red": 0, "blue": 0}
        self.running = True
        self.start_time = time.time()
        self.paused_elapsed = 0.0
        self.shift1_active = None
        self.last_message = "game started"

    def start_match(self):
        with self.control_lock:
            resume_window = self.match_end + DEACTIVATION_GRACE_SEC
            if self.running:
                self.last_message = "match already running"
                return
            if self.start_time is not None and 0 < self.paused_elapsed < resume_window:
                self.start_time = time.time() - self.paused_elapsed
                self.running = True
                self.last_message = "match resumed"
                return
            self._start_game_locked()

    def stop_match(self):
        with self.control_lock:
            if self.running and self.start_time is not None:
                self.paused_elapsed = max(0.0, time.time() - self.start_time)
            self.running = False
            self.stop_at = {"red": None, "blue": None}
            self._stop_hub("red")
            self._stop_hub("blue")
            self._set_hub_lights("red", False)
            self._set_hub_lights("blue", False)
            self.last_message = "match stopped"

    def reset_match(self):
        with self.control_lock:
            self.running = False
            self.shift1_active = None
            self.start_time = None
            self.paused_elapsed = 0.0
            self.score_adjust = {"red": 0, "blue": 0}
            self._reset_hubs()
            self._set_hub_lights("red", False)
            self._set_hub_lights("blue", False)
            self.last_message = "match reset"

    def adjust_score(self, hub, delta):
        with self.control_lock:
            self.score_adjust[hub] += int(delta)
            self.last_message = f"manual {hub} adjustment: {delta:+d}"

    def set_score(self, red_target=None, blue_target=None):
        with self.control_lock:
            red_raw = _safe_int(self._get_cached_status("red").get("count", 0))
            blue_raw = _safe_int(self._get_cached_status("blue").get("count", 0))
            changed = []
            if red_target is not None:
                self.score_adjust["red"] = int(red_target) - red_raw
                changed.append("red")
            if blue_target is not None:
                self.score_adjust["blue"] = int(blue_target) - blue_raw
                changed.append("blue")

            if not changed:
                self.last_message = "manual score set skipped (no values)"
            elif len(changed) == 2:
                self.last_message = "manual score set"
            else:
                self.last_message = f"manual score set ({changed[0]})"

    def _tick(self):
        with self.control_lock:
            now = time.time()
            if self.running and self.start_time is not None:
                elapsed = now - self.start_time
                self.paused_elapsed = elapsed
                desired, phase, phase_left, shift_active = self._desired_state(elapsed)

                for hub in ("red", "blue"):
                    if desired[hub]:
                        self._ensure_active(hub)
                    else:
                        self._schedule_stop(hub, now)
                    self._set_hub_lights(hub, desired[hub])

                self._update_stops(now)
                if elapsed >= self.match_end + DEACTIVATION_GRACE_SEC:
                    self.running = False
                    self.start_time = None
                    self.paused_elapsed = 0.0
                    self.last_message = "match complete"
            else:
                elapsed = self.paused_elapsed
                phase = "IDLE"
                phase_left = 0
                shift_active = "none"
                self._update_stops(now)
                self._set_hub_lights("red", False)
                self._set_hub_lights("blue", False)

            red_status = self._get_cached_status("red")
            blue_status = self._get_cached_status("blue")

            red_raw = _safe_int(red_status.get("count", 0))
            blue_raw = _safe_int(blue_status.get("count", 0))
            red_count = max(0, red_raw + self.score_adjust["red"])
            blue_count = max(0, blue_raw + self.score_adjust["blue"])

            match_left = max(0, int(round(self.match_end - elapsed)))

            new_state = {
                "running": self.running,
                "elapsed": elapsed,
                "match_time_left": match_left,
                "phase": phase,
                "phase_time_left": phase_left,
                "shift_active": shift_active,
                "red_raw_count": red_raw,
                "red_adjust": self.score_adjust["red"],
                "red_count": red_count,
                "red_state": red_status.get("state", "stopped"),
                "blue_raw_count": blue_raw,
                "blue_adjust": self.score_adjust["blue"],
                "blue_count": blue_count,
                "blue_state": blue_status.get("state", "stopped"),
                "last_message": self.last_message,
            }

        with self.match_state_lock:
            self.match_state = new_state

    def run_forever(self):
        while True:
            self._tick()
            time.sleep(self.sleep_s)

    def run_status_poller(self, hub):
        while True:
            self._set_cached_status(hub, self._poll_status(hub))
            time.sleep(self.status_poll_sleep_s)


# Global dashboard instance for HTTP API.
dashboard = None

# FastAPI app for serving control page + API.
api = FastAPI()


# Match-over display flag (controlled from dashboard control UI)
display_lock = threading.Lock()
display_show_final = False


@api.post("/api/display/show")
def api_display_show(payload: dict):
    global display_show_final
    if dashboard is None:
        return {"ok": False, "error": "dashboard not initialized"}
    show = bool(payload.get("show", True))
    with display_lock:
        display_show_final = show
    return {"ok": True, "show_final": display_show_final}


@api.get("/api/display")
def api_display_get():
    with display_lock:
        return {"show_final": display_show_final}


@api.get("/")
def control_page():
    html_path = Path(__file__).parent / "dashboard_control.html"
    return FileResponse(html_path)


@api.get("/match/state")
def get_match_state():
    if dashboard is None:
        return {"error": "Dashboard not initialized"}
    with dashboard.match_state_lock:
        state = dashboard.match_state.copy()
    state.update(dashboard._compute_live_timing())
    return state


@api.get("/api/state")
def get_api_state():
    return get_match_state()


@api.post("/api/match/start")
def api_start_match():
    if dashboard is None:
        return {"ok": False, "error": "dashboard not initialized"}
    dashboard.start_match()
    return {"ok": True}


@api.post("/api/match/stop")
def api_stop_match():
    if dashboard is None:
        return {"ok": False, "error": "dashboard not initialized"}
    dashboard.stop_match()
    return {"ok": True}


@api.post("/api/match/reset")
def api_reset_match():
    if dashboard is None:
        return {"ok": False, "error": "dashboard not initialized"}
    dashboard.reset_match()
    return {"ok": True}


@api.post("/api/score/adjust")
def api_adjust_score(payload: dict):
    if dashboard is None:
        return {"ok": False, "error": "dashboard not initialized"}

    hub = str(payload.get("hub", "")).lower()
    delta = _safe_int(payload.get("delta", 0))
    if hub not in ("red", "blue"):
        return {"ok": False, "error": "hub must be red or blue"}

    dashboard.adjust_score(hub, delta)
    return {"ok": True}


@api.post("/api/score/set")
def api_set_score(payload: dict):
    if dashboard is None:
        return {"ok": False, "error": "dashboard not initialized"}

    has_red = "red" in payload
    has_blue = "blue" in payload
    if not has_red and not has_blue:
        return {"ok": False, "error": "provide at least one of red or blue"}

    red = _safe_int(payload["red"]) if has_red else None
    blue = _safe_int(payload["blue"]) if has_blue else None
    dashboard.set_score(red, blue)
    return {"ok": True}


def main():
    global dashboard

    parser = argparse.ArgumentParser(description="Web dashboard for NPLC fuel counters.")
    parser.add_argument("--red", required=True, help="Red hub base URL, e.g. http://10.0.0.10:8000")
    parser.add_argument("--blue", required=True, help="Blue hub base URL, e.g. http://10.0.0.11:8000")
    parser.add_argument("--rate", type=float, default=5.0, help="Polling rate in Hz (default: 5)")
    parser.add_argument("--timeout", type=float, default=2.0, help="HTTP timeout in seconds (default: 2)")
    parser.add_argument("--port", type=int, default=5001, help="Port for web/API (default: 5001)")
    args = parser.parse_args()

    dashboard = Dashboard(args.red, args.blue, args.rate, args.timeout)

    tick_thread = threading.Thread(target=dashboard.run_forever, daemon=True)
    tick_thread.start()
    threading.Thread(target=dashboard.run_status_poller, args=("red",), daemon=True).start()
    threading.Thread(target=dashboard.run_status_poller, args=("blue",), daemon=True).start()

    print(f"NPLC dashboard control: http://127.0.0.1:{args.port}/")
    print(f"NPLC dashboard state:   http://127.0.0.1:{args.port}/match/state")
    print("Press Ctrl+C to stop.")

    uvicorn.run(api, host="0.0.0.0", port=args.port, log_level="error")


if __name__ == "__main__":
    main()
