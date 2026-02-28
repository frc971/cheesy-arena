# NPLC (Not PLC)

NPLC is a two-hub fuel counting and light control system for the FRC game 2026 rebuilt.

- `dashboard.py` is the control authority (match timing, hub activation logic, score adjustments).
- Each hub runs an HTTP counter service (`dummy_pi.py` for dev, `raspi.py` on real hardware).
- `scoreboard.py` serves the audience display (`scoreboard.html`) using dashboard state as the authoritative source (no direct hub/PI connections).

## File Map

- `dashboard.py`: web control page + API (`/`, `/match/state`, control endpoints)
- `dashboard_control.html`: operator control UI
- `scoreboard.py`: audience display backend (WebSocket feed)
- `scoreboard.html`: audience display frontend
- `dummy_pi.py`: simulated hub server for local testing
- `raspi.py`: Raspberry Pi GPIO hub server
- `nplc.py`: shared HTTP client for hub control/status
- `docs/fuel-counter-http-contract.md`: hub HTTP API contract
- `docs/game-counting-requirements.md`: phase/timing/counting requirements

## Production Quick Start

### For pis:

SSH into each pi:
* Red: `ssh nvidia@10.0.100.10` password `nvidia`
* Blue: `ssh nvidia@10.0.100.11` password `nvidia`

Run:
```
source venv/bin/activate
python raspi.py
```

This should host the counter and light API at port 5000.

### For the FMS/controller PC:

Run the dashboard webpage at `localhost:5001`:
```
uv run dashboard.py
```

Run the scoreboard webpage at `localhost:5000`:
```
uv run scoreboard.py
```

Optional: run the manual CLI controller:
```
uv run display.py
```

They will use `http://10.0.100.10:5000` as the default red port and `http://10.0.100.10:5001` as the default blue port.

## Local Dev Quick Start

From `nplc/`, open 4 terminals.

1. Start dummy red hub:

```bash
uv run dummy_pi.py --port 8000 --rate 3
```

2. Start dummy blue hub:

```bash
uv run dummy_pi.py --port 8001 --rate 2
```

3. Start dashboard (control authority):

```bash
uv run dashboard.py --red http://127.0.0.1:8000 --blue http://127.0.0.1:8001 --port 5001
```

4. Start audience scoreboard (reads only from dashboard API):

```bash
uv run scoreboard.py --dashboard-url http://127.0.0.1:5001 --port 5000
```

Open:

- Dashboard control page: `http://127.0.0.1:5001/`
- Dashboard state feed: `http://127.0.0.1:5001/match/state`
- Audience scoreboard: `http://127.0.0.1:5000/`

## Dashboard Controls

On `http://127.0.0.1:5001/`:

- `Start Match`: starts a new match or resumes if previously stopped
- `Stop Match`: pauses the match
- `Reset Match`: full reset (timer/state/scores)
- `Set relative scores`: add/subtract red/blue deltas
- `Set exact scores`: set one or both alliances directly (empty field is ignored)

## Match Behavior Summary

- AUTO and TRANSITION: both hubs active
- SHIFT 1-4: one hub active, alternating each shift
- END GAME: both hubs active
- SHIFT 1 selection is based on AUTO result (ties are randomized)
- 3-second grace after hub deactivation
- 3-second grace at match end

See `docs/game-counting-requirements.md` for full rules.

## Real Raspberry Pi Deployment

1. Install runtime deps on each Pi:

```bash
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn RPi.GPIO
```

2. Configure pins/host as needed in `raspi.py`.
3. Run one instance per hub Pi:

```bash
python raspi.py
```

4. Run dashboard on control laptop and point `--red` / `--blue` to Pi IPs.

## Notes

- Hub contract is in `docs/fuel-counter-http-contract.md`.
- `display.py` is an older manual CLI control tool and is optional.


https://chatgpt.com/share/69a27ed7-0788-8007-9a2e-2cff3e9618de