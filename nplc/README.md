# NPLC (Network PLC) Fuel Counter

This folder contains a lightweight, networked fuel counter system for two hubs (red and blue). The central web dashboard runs match timing/rules, controls hub counting, and supports manual score adjustments.

**Key files**

- `nplc/nplc.py` HTTP client for hub control and status.
- `nplc/dashboard.py` Central web dashboard + API for match control and score adjustments.
- `nplc/dashboard_control.html` Simple control page served by `dashboard.py`.
- `nplc/dummy_pi.py` Local dummy server to simulate a hub.
- `nplc/raspi.py` Real Pi server (FastAPI + GPIO).
- `nplc/scoreboard.py` Audience scoreboard backend (WebSocket feed).
- `nplc/scoreboard.html` Audience scoreboard frontend.
- `nplc/docs/fuel-counter-http-contract.md` HTTP API contract.
- `nplc/docs/game-counting-requirements.md` Timing rules for counting.

**Quick start with dummy hubs (local dev)**

1. Start two dummy Pi servers in separate terminals:

```bash
cd nplc
uv run dummy_pi.py --port 8000 --rate 3
uv run dummy_pi.py --port 8001 --rate 2
```

2. Start the web dashboard in a third terminal:

```bash
uv run dashboard.py --red http://127.0.0.1:8000 --blue http://127.0.0.1:8001
```

3. Open the control page:

- `http://127.0.0.1:5001/`

4. Start/stop/reset the match and set relative/exact scores from the page.

5. On startup, `dashboard.py` prints links like:

```text
NPLC dashboard control: http://127.0.0.1:5001/
NPLC dashboard state:   http://127.0.0.1:5001/match/state
```

**Webpage dashboard**
The audience scoreboard webpage is display-only. Match/game logic lives in `dashboard.py`.

1. Start the audience scoreboard in a separate terminal:

```bash
uv run uvicorn scoreboard:app --host 127.0.0.1 --port 5000 --reload
```

2. Open:
- `http://127.0.0.1:5000/`

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

5. Point the dashboard at each Pi's IP address.

**Dashboard behavior (ball counting only)**

- AUTO and TRANSITION: both hubs active.
- SHIFT 1–4: only one hub active, alternating each shift.
- END GAME: both hubs active.
- Deactivation grace: 3 seconds after a hub becomes inactive.
- Match end grace: 3 seconds after match end.

**Notes**

- The dashboard reads AUTO counts to decide SHIFT 1 active hub. Ties are broken randomly.
- The HTTP contract is defined in `nplc/docs/fuel-counter-http-contract.md`.
