# Handoff: where the build is right now

**Read this first, then SPEC.md.** SPEC.md is the source of truth for what to build. This file says what's already built, how to run it, and what to do next. Whoever builds updates this file and pushes after every working step, so another laptop can continue at any moment.

_Last updated: backend + interactive app built and tested end to end (join → zone alert → SOS → responder accept → "Help acknowledged" on the phone)._

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
- [x] Frontend scaffold: Vite + React + TS + Tailwind + MapLibre (OpenStreetMap tiles) + installable PWA; `lib/api.ts` (REST + SSE), `lib/types.ts`, `lib/offline.ts` (IndexedDB SOS/ping queues), `lib/geofence.ts` (+ 6 vitest tests), `lib/i18n.tsx` (English/Hindi), `lib/signals.ts`, `lib/verify.ts`
- [x] Tourist: Welcome, Trip setup (3 steps), Judge join `/j`, Preparing, Trip map `/t` (zone alerts with hysteresis, approach banner, safe way back, crowd sheet, hold-to-SOS flow with voice note, live SOS tracker with SMS fallback, "Are you safe?", safety pack with "Show to a local", whistle/strobe/read-to-112 signal tools, compass guide to help points, pass QR, family sharing, demo location mode, checkpoint `/c/:id`), Family view `/f/:token`
- [x] Responder `/r`: live map, incident queue + panel (counts, AI summary with receipt tag, translated notes, accept/en route/resolved, copilot, verify timeline), tap-to-draw zones (shape or circle), safety check + tally, pass scanner, AI & cost (cost meters, Routing River, receipts); simple judge-responder mode `/jr`
- [x] Stage `/stage` (projector), Stage control `/stage/control`, Break it `/break`
- [x] README, DECISIONS, CONTRACT_CHANGES
- [x] Real data: Kedarnath trail, hospital and rain shelters from OpenStreetMap (`scripts/fetch_osm.py`, 15.1 km real trek); live weather per section from Open-Meteo (`backend/app/weather.py`, no key, fixed-threshold warnings, cached 30 min, `weather.updated` event); tourist weather card + danger banner + weather sheet; 23 backend tests
- [ ] **NEXT** Responder weather panel: add `weather` state to `useOpsFeed` in `frontend/src/components/ops.tsx` (load `/api/weather?route_id=`, handle `weather.updated`) and show per-section chips above the incident list
- [ ] Write `scripts/prune_check.py` (SPEC 2 hour-1 checks via `ai/prune_client.chat`: one call, cache-hit repeat, run-budget 429, injection signal; write `docs/PRUNE_FIELDS.md`)
- [ ] Add Prune keys to `.env`, do the SPEC Section 2 hour-1 tasks, write `docs/PRUNE_FIELDS.md` and fix any field names in `ai/prune_client.py::_extract`
- [ ] Benchmark runner R1–R4 + `/benchmark` page (needs Prune keys)
- [ ] Replace `backend/seed/routes/hall.json` with the real venue (geojson.io) and test GPS in the hall with 3+ phones over a tunnel
- [ ] `docs/EXPLAINER.md` for the team (SPEC Section 16)

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
