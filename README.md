# SafeTrail

A trail safety companion for treks, pilgrimages and national parks. It warns tourists before danger, keeps their SOS safe when there's no signal, and gives responders one clear picture. Every AI call goes through [Prune](https://withprune.com), and the AI is never in the emergency path.

Built for BIOS V2 (Thapar Institute, Patiala), Prune challenge "Ship It Lean: AI Apps on a Budget".

- **Spec:** [SPEC.md](SPEC.md) (source of truth) · **Where the build is:** [HANDOFF.md](HANDOFF.md)
- **Decisions:** [docs/DECISIONS.md](docs/DECISIONS.md) · **API differences:** [docs/CONTRACT_CHANGES.md](docs/CONTRACT_CHANGES.md)

## Run it (one origin, one port)
Clone into a **short path** (Windows: `C:\Users\<you>\safetrail`).

```bash
cd frontend
npm install
npm run build
cd ../backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```
Open `http://localhost:8000`. (macOS/Linux: `.venv/bin/python`.)

- **AI on:** copy `.env.example` to `.env` (repo root), add the Prune keys and the two model names. Without them every AI feature uses its standard text and everything else works.
- **Phones:** run a tunnel (`cloudflared tunnel --url http://localhost:8000`), put the https URL in `PUBLIC_URL`, restart. Geolocation needs https.
- **Frontend dev mode:** `npm run dev` in `frontend/` (port 5173, proxies `/api` to port 8000).

## Screens
| URL | Who | What |
|---|---|---|
| `/` | Tourist | Start a trip, or continue one |
| `/j` | Judge | One-screen join onto the hall demo route |
| `/t` | Tourist | Map, zone alerts, crowd warnings, SOS, safety pack, signal tools, pass, family link |
| `/f/<token>` | Family | Trip status only, never location |
| `/r` | Responder (PIN) | Live map, incidents, draw zones, safety checks, verify passes, AI & cost |
| `/jr` | Judge as responder (PIN) | Simple incident queue with Accept |
| `/stage` | Projector (PIN) | Live map, join QR, counters, Routing River, Break-it board |
| `/stage/control` | Presenter (PIN) | Landslide here, crowd surge, safety check, budget stress test, reset |
| `/break` | Judges | Try 8 real abuse tricks and see what catches them |
| `/c/<id>` | Tourist | Checkpoint QR: confirms your location precisely |

Demo PINs: `RESPONDER_PIN` (default 2468) and `PRESENTER_PIN` (default 1357) in `.env`.

## Tests
```bash
cd backend && .venv\Scripts\python -m pytest -q
cd frontend && npm test
python scripts/smoke_test.py      # against a running backend
```
