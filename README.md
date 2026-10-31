# SafeTrail

A trail safety companion for treks, pilgrimages and national parks. It warns tourists before danger, keeps their SOS safe when there's no signal, and gives responders one clear picture. Every AI call goes through [Prune](https://withprune.com), and the AI is never in the emergency path.

Built for BIOS V2 (Thapar Institute, Patiala), Prune challenge "Ship It Lean: AI Apps on a Budget".

- **Spec:** [SPEC.md](SPEC.md) (source of truth) · **Where the build is:** [HANDOFF.md](HANDOFF.md)
- **Decisions:** [docs/DECISIONS.md](docs/DECISIONS.md) · **API differences:** [docs/CONTRACT_CHANGES.md](docs/CONTRACT_CHANGES.md)

## Run it (one origin, one port)
Clone into a **short path** (Windows: `C:\Users\<you>\safetrail`).

**macOS / Linux, one command:** `bash scripts/run_local.sh` (checks Python 3.10+ and Node 18+, builds, installs, starts http://localhost:8000 and opens the browser). Windows:

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
- **Phones:** on macOS or Linux, `bash scripts/run_phones.sh` starts a tunnel and the app together and prints the links (needs `cloudflared`). On Windows, run a tunnel (`cloudflared tunnel --url http://localhost:8000`), put the https URL in `PUBLIC_URL`, restart. Geolocation needs https.
- **SOS by SMS (optional):** set `SOS_SMS_NUMBER` (the number tourists text) and `SMS_WEBHOOK_SECRET`, then point an SMS gateway (for example an Android SMS-gateway app on the demo phone, or Twilio) at `https://<tunnel>/api/sms/inbound?secret=<SMS_WEBHOOK_SECRET>`. It accepts JSON `{"from", "text"}` or a form post with `From`/`Body`. The app's coded SOS SMS is parsed without AI; free text from a registered phone becomes an SOS at once and the `sms_parse` AI job only fills in unknown details; texts from unknown numbers go to responders as call-back requests.
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
| `/stage` | Projector (PIN) | Live map, join QR, headline counter, confetti on Accept, round recap, Routing River, Break-it board |
| `/stage/control` | Presenter (PIN) | Next round, landslide here, crowd surge, safety check, budget stress test, reset |
| `/break` | Judges | Try 8 real abuse tricks and see what catches them |
| `/benchmark` | Everyone | R1–R4 cost per trip and per emergency, measured (after `scripts/benchmark.py`) |
| `/c/<id>` | Tourist | Checkpoint QR: confirms your location precisely |

Demo PINs: `RESPONDER_PIN` (default 2468) and `PRESENTER_PIN` (default 1357) in `.env`. Live demo steps: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). Team guide: [docs/EXPLAINER.md](docs/EXPLAINER.md).

## The safety rule: the AI is never in the emergency path
These work with Prune switched off, over budget or unreachable: zone alerts, crowd detection, SOS saving, sending and receiving, SOS grouping and counts, check-ins, quiet-tourist detection, pass checks, the signed event log and the family link. They are plain code; the alerts and the SOS queue run on the phone.

The AI only writes and translates: safety packs, zone warnings, incident reports, cluster summaries and copilot steps. Every AI feature has a fixed standard text that's used when the AI can't be, and the UI labels it "Standard text". Priority is set by rules, never by the AI. A suspicious note becomes a flag on the incident; an SOS is never blocked.

## How every AI call goes through Prune
All LLM calls are made on the server, by one module (`backend/app/ai/prune_client.py`), to one base URL (`PRUNE_BASE_URL`, default `https://api.withprune.com/v1`), non-streaming `chat.completions` only. `scripts/check_no_direct_calls.sh` fails if any other code calls a provider directly, imports an AI SDK, or if a key is committed.

**Headers on every call:**

| Header | Value |
|---|---|
| `X-Prune-Run-Id` | one run per AI job, e.g. `pack_kedarnath_hi_senior_v1`, `adv_<zone>`, `inc_<incident>_<n>`, `clu_<incident>_<n>`, `cop_<incident>_<n>`, plus a random suffix, because Prune remembers a stopped run for good |
| `X-Prune-Run-Budget-Usd` / `X-Prune-Max-Steps` | the job's budget and step limit (below) |
| `X-Prune-Feature-Id` | `pack`, `advisory`, `report`, `cluster`, `copilot`, `sms_parse`, `permit` or `repair` |
| `X-Prune-Customer-Id` | `route_<route_id>`, so Prune's dashboard shows cost per route |
| `X-Prune-Cache` | `exact` (`PRUNE_CACHE_MODE`), never semantic. Every call also sends `X-Prune-Max-Cache-Error: 0` and a fingerprint of the request in the system prompt: without both, `exact` returned one incident's summary for another (`docs/DECISIONS.md`, 28) |
| `X-Prune-Model-Policy` | `balanced` (`PRUNE_MODEL_POLICY`) |
| `X-Prune-Injection` | `detect` (`PRUNE_INJECTION_MODE`): a signal becomes a flag, never a block |

**Keys:** provider keys live only in Prune's vault. `.env` (never committed) holds two Prune keys: `PRUNE_API_KEY` (ops, with a daily spend cap set in the Prune dashboard) and `PRUNE_PUBLIC_API_KEY` (the Break-it round: small cap, kept on `MODEL_SMALL` by the app, plus a local cap `PUBLIC_BUDGET_USD`). Nothing secret is in the frontend bundle.

**Three budget layers:**
1. **Our governor** estimates each call before sending it. If it won't fit the job's budget, LARGE drops to SMALL, or the job uses standard text. Budgets per job (`backend/app/config.py`): pack $0.03, advisory $0.005 per language, report $0.02, cluster summary $0.03, copilot $0.01, SMS parse $0.003, permit card $0.004.
2. **Prune's run guard** enforces those budgets and step limits per job (`X-Prune-Run-Budget-Usd`, `X-Prune-Max-Steps`). A 429 `run_budget` is never retried: the job uses standard text.
3. **Prune's key caps** are the outer wall: a daily spend cap on each key.

Errors: Prune's fail-closed 503s are retried once after `Retry-After`; rate-limit 429s pause AI for 20 s; a 402 plan limit turns AI off until restart. Alerts and SOS never wait for any of this.

## How cost per trip and per emergency are computed
Every cost is Prune's own `cost_with_prune_usd` from the stored response metadata (`LlmCall` table). If Prune didn't return a cost, the screen shows n/a, never a guess.
- **Cost per monitored trip** = cost of all `pack`, `advisory` and `permit` calls ÷ trips started (simulated stage dots excluded).
- **Cost per emergency** = cost of all `report`, `cluster`, `copilot` and `sms_parse` calls ÷ incidents (incidents merged into another one excluded).
- A repair call counts toward the feature of the job it repaired. Prune's `cost_without_prune_usd` is always labelled "Prune estimate (list price)".

## Benchmark method
`scripts/benchmark.py` runs one simulated scenario (`backend/seed/scenario/`: 500 trips on the seeded routes, 6 zones, 40 SOS in 3 clusters and 6 singles, notes in English, Hindi and Assamese, 4 of them injection attempts) through four configurations, in its own database:

| Run | What it does | Prune headers |
|---|---|---|
| R1 Naive | MODEL_LARGE for everything, one personalised pack per trip, a cluster summary after every SOS, no budgets | policy off, cache off |
| R2 SafeTrail, no Prune optimisations | full design: packs per route, language and profile; templates; refresh limits; budgets | policy off, cache off |
| R3 SafeTrail + Prune (cold) | full design with a fresh nonce in the prompt | policy balanced, cache exact |
| R4 SafeTrail + Prune (warm) | R3 again with the same nonce: a second day on the same routes | policy balanced, cache exact |

R1 → R2 is the saving from SafeTrail's design, R2 → R3 from Prune's routing and optimisations, R3 → R4 from Prune's exact cache. It also measures count accuracy (must be 100%: counts are computed), the invented-fact rate (answers the validators rejected), injection recall, standard-text fallbacks and latency. Results go to `docs/BENCHMARK.md` and the `/benchmark` page, with run ids and timestamps.

## Phase 2: Digital Tourist ID (simulated)
A tourist opens **Pass → Link your permit**, picks Foreign or Indian visitor and enters the document they already have. A **simulated registry** (`backend/seed/mock_registry.json`, fake numbers) stands in for the e-Visa, e-ILP and yatra systems. The number is hashed at once; only its last 4 characters are kept, and it never reaches the AI. The pass is re-signed with the permit type, dates and the restricted zones it allows, so phones and checkpoints apply it offline: the phone alerts "Not permitted for your pass" in a restricted zone the permit doesn't cover, and the responder's **Verify pass** has "Checking entry to …", an offline revocation list and **Revoke pass**. "What your permit allows" is written in the tourist's language through Prune (`permit` feature, cached per permit type and language) or shown as the official text.

Demo numbers (all fake): e-Visa `EV2026IN0042137` (Sikkim RAP: not beyond Yumthang) · DigiLocker `DL-SK-NS-2026-1129` (Indian North Sikkim permit: Zero Point road allowed) · Yatra `UK-YATRA-2026-551023` (Kedarnath) · Passport `Z1234567` (Corbett Dhikala) · expired e-Visa `EV2025IN0007788` · Aadhaar: last 4 digits only, self-declared, never a permit.

## Tests
```bash
cd backend && .venv\Scripts\python -m pytest -q
cd frontend && npm test
bash scripts/check_no_direct_calls.sh   # no direct AI calls, no keys (also: python scripts/check_no_direct_calls.py)
python scripts/smoke_test.py      # against a running backend
python scripts/prune_check.py     # once, after the Prune keys are in .env
python scripts/benchmark.py --trips 100   # R1-R4, writes docs/BENCHMARK.md
```
