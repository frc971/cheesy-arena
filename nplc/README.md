# NPLC (Network PLC) Fuel Counter

This folder contains a lightweight, networked fuel counter system for two hubs (red and blue). The FMS-side tools connect to two Raspberry Pis over HTTP and start/stop counting based on match timing rules.

**Key files**

- `nplc/nplc.py` HTTP client for hub control and status.
- `nplc/dashboard.py` Match-timed dashboard that starts/stops counting based on the game rules.
- `nplc/display.py` Manual control display for starting/stopping/resetting hubs.
- `nplc/dummy_pi.py` Local dummy server to simulate a hub.
- `nplc/raspi.py` Real Pi server (FastAPI + GPIO).
- `nplc/docs/fuel-counter-http-contract.md` HTTP API contract.
- `nplc/docs/game-counting-requirements.md` Timing rules for counting.

**Quick start with dummy hubs (local dev)**

1. Start two dummy Pi servers in separate terminals:

```bash
cd nplc
uv run dummy_pi.py --port 8000 --rate 3
uv run dummy_pi.py --port 8001 --rate 2
```

2. Start the match dashboard in a third terminal:

```bash
uv run dashboard.py --red http://127.0.0.1:8000 --blue http://127.0.0.1:8001
```

3. The game auto-starts on launch. Press `Ctrl+C` to quit the dashboard.

**Webpage dashboard**
The webpage is display-only (no game logic).
Game logic runs on the Pi instances.
The dashboard controls the match state.

1. Start the game webpage display in a seperate 4th terminal alongside the dashboard, and 2 dummy pi's

```bash
uv run uvicorn scoreboard:app --host 127.0.0.1 --port 5000 --reload
```

- This should be the same as real life except you would change the hosts and port to be the real life configuration instead

**Manual control display (optional)**
Use this if you want manual start/stop/reset controls instead of match timing:

```bash
uv run display.py --red http://127.0.0.1:8000 --blue http://127.0.0.1:8001
```

**Running on real Raspberry Pis**

1. Install dependencies on each Pi:

```bash
uv run -m pip install fastapi uvicorn
```

2. Ensure `RPi.GPIO` is installed (usually preinstalled on Raspberry Pi OS).
3. Update pins and host in `nplc/raspi.py` if needed.
4. Run on each Pi (red and blue):

```bash
uv run nplc/raspi.py
```

5. Point the dashboard or display at each Pi's IP address.

**Dashboard behavior (ball counting only)**

- AUTO and TRANSITION: both hubs active.
- SHIFT 1–4: only one hub active, alternating each shift.
- END GAME: both hubs active.
- Deactivation grace: 3 seconds after a hub becomes inactive.
- Match end grace: 3 seconds after match end.

**Notes**

- The dashboard reads AUTO counts to decide SHIFT 1 active hub. Ties are broken randomly.
- The HTTP contract is defined in `nplc/docs/fuel-counter-http-contract.md`.
