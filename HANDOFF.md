# Handoff: where the build is right now

**Read this first, then SPEC.md.** Claude: also read `CLAUDE.md`, `CONTINUE.md` (prompts and laptop handover) and `docs/SESSION_LOG.md`. SPEC.md is the source of truth for what to build. This file says what's already built, how to run it, and what to do next. Whoever builds updates this file and pushes after every working step, so another laptop can continue at any moment.

_Last updated: the benchmark and the deck are done. `docs/SafeTrail-Deck.pptx` has 10 slides and 3 backups, with only the team name and Join QR left to fill in. On 100 simulated trips SafeTrail costs about 3 paise per trip and 10 paise per emergency at Google's list price, with 82% fewer tokens per trip than the naive way. The AI is live through Prune with Gemini, and `scripts/prune_check.py` gives 10 OK and 1 warning. Prune's exact cache is on, with two guards that must stay: read `docs/DECISIONS.md` 28 to 45 before touching the AI layer. 76 backend tests and 6 frontend tests pass, and the whole of `docs/DEMO_SCRIPT.md` ran in real browsers with and without WebGL. What is left needs people and places: real phones, the real spots at the venue, two rehearsals, a backup video and the signed report from Prune's dashboard._

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
- [x] Backend tests: 20 passing at first (27 now) (`pytest -q`); live smoke test `scripts/smoke_test.py` passes
- [x] Frontend scaffold: Vite + React + TS + Tailwind + MapLibre (OpenStreetMap tiles) + installable PWA; `lib/api.ts` (REST + SSE), `lib/types.ts`, `lib/offline.ts` (IndexedDB SOS/ping queues), `lib/geofence.ts` (+ 6 vitest tests), `lib/i18n.tsx` (English/Hindi), `lib/signals.ts`, `lib/verify.ts`
- [x] Tourist: Welcome, Trip setup (3 steps), Judge join `/j`, Preparing, Trip map `/t` (zone alerts with hysteresis, approach banner, safe way back, crowd sheet, hold-to-SOS flow with voice note, live SOS tracker with SMS fallback, "Are you safe?", safety pack with "Show to a local", whistle/strobe/read-to-112 signal tools, compass guide to help points, pass QR, family sharing, demo location mode, checkpoint `/c/:id`), Family view `/f/:token`
- [x] Responder `/r`: live map, incident queue + panel (counts, AI summary with receipt tag, translated notes, accept/en route/resolved, copilot, verify timeline), tap-to-draw zones (shape or circle), safety check + tally, pass scanner, AI & cost (cost meters, Routing River, receipts); simple judge-responder mode `/jr`
- [x] Stage `/stage` (projector), Stage control `/stage/control`, Break it `/break`
- [x] README, DECISIONS, CONTRACT_CHANGES
- [x] Real data: Kedarnath trail, hospital and rain shelters from OpenStreetMap (`scripts/fetch_osm.py`, 15.1 km real trek); live weather per section from Open-Meteo (`backend/app/weather.py`, no key, fixed-threshold warnings, cached 30 min, `weather.updated` event); tourist weather card + danger banner + weather sheet; 23 backend tests
- [x] Responder weather panel (`WeatherPanel` in `components/ops.tsx`, above the incident list): per-section chips coloured by warning level, tap for details and to fly the map there, "Draw a zone here" pre-fills the zone tool (the officer still reviews and publishes; weather never publishes a zone by itself); `weather.updated` refreshes it live and danger warnings go to the live feed
- [x] `scripts/prune_check.py`: the SPEC 2 hour-1 checks in one command (basic call, exact-cache repeat, run-budget 429, injection detect, policy header, MODEL_LARGE, the app's own `chat()` path, public-key allowlist). Writes `docs/PRUNE_FIELDS.md` and `docs/prune_sample_response.json` from the real responses only, and lists every Prune header and metadata field `_extract` does not read yet. `--dry-run` works without keys. Uses `prune_client.probe()` (raw call, no retry, no logging); diagnostics log into a throwaway database so they never count in cost per trip. 27 backend tests
- [x] Extra routes (SPEC 10.1): `sikkim` (Lachung to Yumthang, landslide + restricted zones) and `park` (Corbett: Dhangarhi gate to Dhikala, wildlife core + river crossing), generated by `scripts/make_extra_routes.py`, all simulated; Nepali phrasebook (`ne.json`, partial templates fall back to English); responder route picker lists all routes; benchmark trips now span Kedarnath and Sikkim. 39 backend tests
- [x] SMS inbound (SPEC 5.6 + 5.8.6): `POST /api/sms/inbound` (shared secret, JSON or form), coded SOS SMS parsed without AI and deduplicated against data SOS, free text becomes an SOS at once and the `sms_parse` AI job fills only unknown fields (never lowers priority, never invents a place), unknown senders go to responders as call-backs; number stored only as hash + last 4. 46 backend tests
- [x] Phase 2 Digital Tourist ID, simulated (SPEC 17): mock registry (`seed/mock_registry.json`, fake numbers), `POST /permits/lookup` (hash + last 4 only, rate limited), `POST /passes/{id}/upgrade` (re-signed pass with permit and allowed zones), `POST /passes/{id}/revoke` + `GET /passes/revocations`, `/passes/verify` with `zone_id`, permit card via Prune (`permit`); tourist **Pass → Link your permit**, permit-aware zone alerts, responder scanner with "Checking entry to", offline revocation list and Revoke. Not built: optional OCR photo check. 54 backend tests
- [x] Projector "wow": headline live counter (round · on the trail · SOS → incidents · AI cost this round), confetti + cheer on Accept, **Next round** on Stage control (one tap, 3 s cancel, round recap on the projector, `GET /stage/round`, `next_round` action, `/ai/stats?since=`). 56 backend tests
- [x] AI live through Prune with Gemini. In `.env` (keys are on Hardik's Mac only, so another laptop needs its own): `PRUNE_API_KEY`, `PRUNE_PUBLIC_API_KEY`, `MODEL_SMALL=gemini/gemini-3.1-flash-lite`, `MODEL_LARGE=gemini/gemini-3.5-flash`. `backend/.venv/bin/python scripts/prune_check.py` (Windows: `backend\.venv\Scripts\python scripts\prune_check.py`) gives 10 OK and 1 warning, and writes `docs/PRUNE_FIELDS.md`. Live tests: report (en, hi, as), cluster, copilot, pack (en, hi), advisories (en, hi), sms_parse and permit all gave validated AI text. In three demo rounds, the repeated SOS was a true `exact` cache hit and the different one got its own report. 67 backend tests. One signed receipt (`docs/receipts/sample_receipt.json`) passes a local check against Prune's public key, and a tampered copy fails
- [x] Safety pack Briefing tab shows risks by section with the nearest help point, and marks the section you're in
- [x] Full demo played in real browsers (3 phones, projector, presenter, responder), with and without WebGL: join, landslide, crowd, airplane-mode SOS, grouping, "Are you safe?", Accept, Verify timeline, family link, budget stress test, Next round and 7 Break-it tricks. It found and fixed four bugs (DECISIONS 36 to 39). Desktop browsers with phone emulation only, so real phones are still to do
- [x] The public key stays on `MODEL_SMALL`: `jobs.run_job` enforces it, so setting allowed models in Prune's Shield is an optional extra (DECISIONS 40). `prune_check.py` still shows this as its 1 warning
- [x] Receipt verified on withprune.com/verify: "Signature valid" for `docs/receipts/sample_receipt.json`, screenshot in `docs/receipts/receipt-verified.png`. After the benchmark, also download the signed report from Prune's Shield → Reports
- [x] Provider for the demo: Hardik chose to keep the free Gemini key (31 Oct). On it, 5 of 16 calls in one full run returned 503 and 3 timed out, and the trouble can last a minute or more, so expect some "Standard text" on stage. `docs/DEMO_SCRIPT.md` says what to do
- [x] Field-readiness fixes (1 Nov): line icons instead of emoji; terrain relief on the map (cached for offline); the route, zones and help points now draw even when map tiles fail; zone outlines are true buffers (the old Kedarnath outlines had holes on switchbacks, so parts of the trail read as outside the landslide zone). DECISIONS 46-50. 77 backend tests; the tourist map keeps only the compass, which no longer hides under the "Online" chip
- [x] Benchmark runner R1–R4 + `/benchmark` page: deterministic scenario in `backend/seed/scenario/` (500 trips, 6 zones, 40 SOS in 3 clusters + 6 singles, notes in en/hi/as, 4 injections; `scripts/make_benchmark_scenario.py`), runner `backend/app/benchmark.py`, CLI `scripts/benchmark.py` (own database `backend/benchmark.db`; `--no-ai` plumbing test needs no key), results to `docs/benchmark_results.json` + `docs/BENCHMARK.md`, page `/benchmark` (waterfall, per-run table, Prune estimate box; empty state until a real run), link from the responder's AI & cost tab. Tested with AI off (counts 100% in all four runs) and against a local fake Prune server. 31 backend tests
- [x] Benchmark run on 100 trips, results in `docs/BENCHMARK.md` and on `/benchmark`. Read its "Read this first" notes: tokens are solid, and R1 is a low estimate because the free key hit its limits
- [x] Costs worked out from Google's token counts at list price, because Prune's Gemini costs skip output tokens and a free key has no bill to check against (DECISIONS 44). The table is in `docs/BENCHMARK.md`
- [x] Deck built: `docs/SafeTrail-Deck.pptx`, 10 slides and 3 backups with speaker notes, checked in Keynote. Fill in the team name (slide 1) and Join QR (slide 9). For another version, paste `docs/PPT_PROMPT.md` into any LLM and attach the app screenshots
- [ ] Download the signed report from Prune's Shield → Reports for the submission
- [x] Phone access: `bash scripts/run_phones.sh` starts the tunnel and the app together. Tested through a real tunnel with an emulated phone: https, GPS, SOS, QR and family links all worked
- [x] Venue route: `backend/seed/routes/hall.json` is now the CSED block loop (59 × 52 m, drawn on geojson.io), and the full demo passed on it with AI off. The route id stays `hall`. OpenStreetMap labels this spot "LT Building", but Hardik confirmed the name to show is "CSED block"
- [ ] Replace the placeholder help desk, lobby and door positions in `hall.json` with the real spots
- [ ] Test GPS at the venue with 3+ real phones (`scripts/run_phones.sh`)
- [ ] Rehearse `docs/DEMO_SCRIPT.md` twice with real phones (Android and iPhone), then record a backup video
- [x] Backup walkthrough: `docs/SafeTrail-Backup-Walkthrough.mp4`, 75 seconds, built from screenshots of the real app on emulated phones and labelled that way on every frame. A recording on real phones would still be better
- [x] `docs/EXPLAINER.md` for the team (SPEC Section 16): story, diagram, three sentences per part, glossary, judge Q&A, what we did not build
- [x] `scripts/check_no_direct_calls.sh` (logic in `check_no_direct_calls.py`, runs on Windows too): fails on direct AI-provider URLs, AI SDK imports outside `prune_client.py`, LLM use in the frontend, committed keys (files, git history and the built bundle), `.env`, `backend/keys/` or databases. Passes; tested in `tests/test_no_direct_calls.py`. 36 backend tests
- [x] `docs/DEMO_SCRIPT.md` (SPEC 10.4): setup checklist, the 3-minute run of show with the app's real button labels, fallbacks, Break-it round
- [x] README: the safety rule, Prune headers, keys and the three budget layers, how cost per trip and per emergency are computed, the benchmark method

## How to run
**macOS / Linux:** `bash scripts/run_local.sh` does everything below and opens the browser.

### Step by step (backend)
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

## Moving work between laptops without GitHub access
If a session can't push to `gaurvit06/Safetrail`, it can hand over a git bundle (one file with every commit):
```bash
git bundle create safetrail-work.bundle main          # on the machine that has the new commits
git pull /path/to/safetrail-work.bundle main          # in the Safetrail folder on the other laptop
git push origin main
```
The pull is a fast-forward when the bundle was built on top of the latest `main`; if someone pushed in between, git merges as usual.

## Prompt to continue on another laptop
Use the prompts in `CONTINUE.md` (Prompt 1 on your own desktop, Prompt 2 in another Claude or on another laptop). Short version:
```
Clone https://github.com/gaurvit06/Safetrail.git into a SHORT folder (Windows: C:\Users\<you>\safetrail), or git pull if it's already there. Read CLAUDE.md, HANDOFF.md, CONTINUE.md and docs/SESSION_LOG.md, then SPEC.md where needed. Continue from the first unchecked item in HANDOFF.md without redoing finished work. After every working step: run the tests and scripts/check_no_direct_calls.sh, update HANDOFF.md, commit, and push to main.
```
