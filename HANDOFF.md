# Handoff: where the build is right now

**Read this first, then SPEC.md.** SPEC.md is the source of truth for what to build. This file says what's already built, how to run it, and what to do next. Whoever builds updates this file and pushes after every working step, so another laptop can continue at any moment.

_Last updated: backend complete and tested; starting the frontend._

## Plan and status
- [x] Repo, spec, `.gitignore`, `.env.example`, `requirements.txt`
- [x] Backend core files: `config.py`, `db.py`, `models.py` (all tables, SPEC 6), `geo.py`, `events.py` (SSE broadcaster), `security.py` (Ed25519 passes, role tokens), `eventlog.py` (signed hash chain), `seeddata.py`
- [x] Seed data: `hall` and `kedarnath` routes, route facts, demo SOPs, English and Hindi templates
- [x] AI: `ai/templates.py` (all fallbacks), `ai/pii.py`
- [x] AI layer: `ai/prune_client.py` (headers, retry table, receipts, logging), `ai/validators.py`, `ai/prompts.py` (cacheable), `ai/jobs.py` (governor, repair, escalation, template fallback, public-key budget), `ai/features.py` (pack, advisories, report, cluster summary, copilot)
- [x] Core logic `core.py`: zones, trips, pings with impossible-travel flags, SOS intake (idempotent, flood flag, injection scanner, rule priority), incident grouping with exact counts, statuses, timeline, safety checks, family status, AI stats
- [x] Engines `engines.py`: crowd heat + auto crowd zones + "crowd ahead" warnings, quiet tourists, zone expiry, retention
- [x] Stage `stage.py`: landslide here, crowd surge, safety check, budget stress test, walk simulation, reset; Break-it (8 tricks)
- [x] API `api.py` + `main.py` (SSE at `/api/events?token=`, serves `frontend/dist`)
- [x] Backend tests: 20 passing (`pytest -q`); live smoke test `scripts/smoke_test.py` passes
- [ ] **NEXT** Frontend: Vite + React + TS + Tailwind + MapLibre PWA scaffold, `api/types.ts`, `api/client.ts`, `api/sse.ts`
- [ ] Frontend tourist flow: Welcome, Trip setup, Preparing, Home map + geofence + zone alert, SOS flow + offline queue + status, safety check, pack, pass, family share
- [ ] Frontend responder: login, control map, incident panel + timeline verify, draw zone, safety check tally, AI & cost
- [ ] Frontend stage: Stage, Stage control, Join (`/j`, `/jr`), Break it; Family view; Benchmark page
- [ ] Benchmark runner R1–R4 (needs Prune keys)
- [ ] Docs: `docs/EXPLAINER.md`, `docs/PRUNE_FIELDS.md` (needs a real Prune call), README

## How to run (backend)
Clone into a **short path** (Windows: `C:\Users\<you>\safetrail`; long paths break Python and `node_modules`).
```bash
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
.venv\Scripts\python -m pytest -q
```
(macOS/Linux: use `.venv/bin/python`.) With no Prune key in `.env`, AI features fall back to templates and everything else still works. Copy `.env.example` to `.env` at the repo root and add keys to turn AI on.

## Important notes
- Implementation decisions: `docs/DECISIONS.md`. API differences from the spec: `docs/CONTRACT_CHANGES.md`.
- Never commit `.env`, `backend/keys/` or `*.db`.
- Push after every working step and update the checklist above.

## Prompt to continue on another laptop
```
Clone https://github.com/gaurvit06/Safetrail.git into a SHORT folder (Windows: C:\Users\<you>\safetrail). If it's already there, run git pull.

Read HANDOFF.md and SPEC.md completely. SPEC.md is the source of truth; HANDOFF.md says what's built, how to run it, and what's next.

Continue building SafeTrail from the first unchecked item in HANDOFF.md. You build everything (backend and frontend). Don't redo finished work; read the existing code first.

After every working step: run the tests, update the checklist in HANDOFF.md, commit, and push to main.
```
