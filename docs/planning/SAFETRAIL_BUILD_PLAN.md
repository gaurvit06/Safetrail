# SafeTrail: build plan and technical spec

> A safety companion for treks, pilgrimages and national parks. Tourist mode and Responder mode in one app. Every LLM call goes through Prune. Safety-critical features never depend on the AI.

**Contents**
1. Scope: what we build now vs Phase 2
2. Architecture
3. Tech stack
4. Data model
5. Core features in detail (non-AI)
6. Prune features in detail (all LLM work)
7. Offline and connectivity
8. UI and UX spec
9. API and events
10. Security and privacy
11. Demo setup and seed data
12. Build schedule (two agents and the team)
13. Definition of done
14. Phase 2: Digital Tourist ID with visa and e-ILP e-KYC (only if time allows)

---

## 1. Scope

**Build now (MUST):**
- Simple trip registration (name, phone, emergency contact, route, language). The pass is a **signed demo pass**, not real KYC.
- Offline safety pack (AI through Prune)
- Danger-zone alerts (on the phone, offline)
- Crowd heatmap and crowd red zones with stampede warnings
- Offline SOS with a queue, auto-send and SMS fallback
- "Are you safe?" mass check-in
- Family link (status only)
- Responder mode:
  - live map and zone drawing
  - incident cards (AI report through Prune)
  - SOS grouping (AI through Prune)
  - responder copilot (AI through Prune)
  - Accept, with a signed and hash-chained timeline
- Zone advisories in many languages (AI through Prune)
- Prune cost panel, receipts and benchmark

**Phase 2 (only if time allows; see Section 14):** a Digital Tourist ID with e-KYC: visa or e-Visa number for foreigners, e-ILP or yatra number for Indians, Aadhaar optional and masked.

**Not building:**
- real police or 112 integration
- real permit-system APIs
- satellite SOS
- Bluetooth mesh
- face recognition

All zones and dispatches in the demo are labelled **Simulated**.

---

## 2. Architecture

```
┌──────────────── PHONE (PWA, works offline) ─────────────────┐
│  Tourist mode / Responder mode (role from login)            │
│  ├─ Geofence engine (turf.js)       → zone alerts, offline  │
│  ├─ Check-in timer                  → "quiet" state, offline│
│  ├─ SOS queue (IndexedDB)           → retry + SMS fallback  │
│  ├─ Safety pack cache (IndexedDB)   → readable offline      │
│  └─ Service worker                  → app shell + map tiles │
└───────────────▲──────────────────────────────┬──────────────┘
                │ HTTPS + SSE (when online)    │ SMS (fallback)
┌───────────────┴──────────────────────────────▼──────────────┐
│  BACKEND (FastAPI, reused from JURY)                        │
│  ├─ Trips, pings, zones, incidents, check-ins (SQLite)      │
│  ├─ Crowd engine (grid density, every 10 s)                 │
│  ├─ Clustering engine (DBSCAN on SOS points)                │
│  ├─ Event log (hash-chained, Ed25519-signed)                │
│  ├─ SSE broadcaster (reused from JURY)                      │
│  └─ ai/  ← ONLY place that calls an LLM                     │
│       └─ prune_client.py (reused from JURY) ──► Prune ──► LLMs│
└─────────────────────────────────────────────────────────────┘
```

**Golden rule:** these never call the AI:
- zone alerts
- crowd detection
- SOS saving and sending
- check-ins
- pass validation
- the event log

Every AI feature has a **template fallback**.

---

## 3. Tech stack

| Layer | Choice | Why |
|---|---|---|
| App | **React + Vite + TypeScript as an installable PWA** | Judges scan a QR and are in immediately, with no app-store install |
| Styling | Tailwind + shadcn/ui (already in JURY) | Fast and consistent |
| Map | **MapLibre GL JS** with OpenStreetMap raster tiles | Free and supports offline tile caching. Use `react-map-gl/maplibre` |
| Geometry | **turf.js** (point-in-polygon, distance, buffers) | Geofencing on the phone, no server needed |
| Zone drawing | `@mapbox/mapbox-gl-draw` (works with MapLibre) | The responder draws polygons |
| Offline storage | **IndexedDB via `idb`** | SOS queue, safety pack, zones |
| Service worker | `vite-plugin-pwa` (Workbox) | App shell, cached tiles, background sync where supported |
| Location | `navigator.geolocation.watchPosition` (high accuracy) | Live position while the app is open |
| Alerts | Vibration API + full-screen alert + sound + Web Notifications | **iOS doesn't support vibration**, so always use sound and a flash as well |
| QR | `qrcode.react` (show), `@zxing/browser` (scan checkpoint) | Pass QR and door checkpoint |
| Backend | **FastAPI + SQLModel + SQLite** (from JURY) | Reuse |
| Live updates | **SSE** (from JURY) | Responder map and the tourist's acknowledgment |
| Clustering | `scikit-learn` DBSCAN (haversine) | Grouping SOS points |
| Signing | `cryptography` Ed25519 | Pass signatures and the event log |
| LLM | **OpenAI SDK pointed at the Prune base URL**, via JURY's `prune_client.py` | Every call goes through Prune |
| SMS (fallback) | `sms:` link prefilled on the phone; a server number receives it through an SMS-gateway webhook (optional) | Honest offline path |
| Tunnel | cloudflared or ngrok, as `PUBLIC_URL` | Judges' phones reach the laptop |

**HTTPS is required:** geolocation and service workers only work over HTTPS. The tunnel provides it.

**Reused from JURY:**
- `prune_client.py`: headers, retries, receipts, call logging
- the `LlmCall` table
- the cost meters
- the receipts drawer and Verify link
- the benchmark runner
- the SSE plumbing
- the arena, which becomes the "Break it" round

---

## 4. Data model (SQLite)

```
Route(id, name, region, geojson_line, checkpoints_json, languages_json)
Zone(id, route_id, kind: landslide|closed_trail|restricted|wildlife_core|crowd|custom,
     severity: warn|danger, polygon_geojson, message_key, source: seeded|drawn|auto_crowd,
     simulated: bool, active: bool, created_by, created_at, expires_at)
Trip(id, pass_id, name, phone, emergency_contact, language, route_id, start_at, end_at,
     status: planned|active|quiet|sos|safe|ended, sharing: bool, family_token, created_at)
Pass(id, trip_id, payload_json, signature, key_id, expires_at, kyc_level: demo|verified)
Ping(id, trip_id, lat, lon, accuracy_m, ts, source: gps|checkpoint|sim)
SosEvent(id, client_id UNIQUE, trip_id, kind: injured|lost|stuck|medical|unsafe,
         people_count, note_text, lat, lon, accuracy_m, created_at_device,
         received_at_server, channel: data|sms|checkpoint, incident_id)
Incident(id, status: new|accepted|en_route|resolved, cluster_center, radius_m,
         people_total, injured_total, summary_json, report_lang, accepted_by, accepted_at)
SafetyCheck(id, zone_id, sent_at, message_key)          -- "Are you safe?"
CheckResponse(id, check_id, trip_id, answer: safe|need_help, ts)
SafetyPack(id, route_id, language, profile_bucket, content_json, cache_key, created_at)
Advisory(id, zone_id, language, text, cache_key, created_at)
EventLog(seq, ts, type, entity_id, payload_hash, prev_hash, hash, signature)
LlmCall(... reused from JURY: stage, models, cache_hit, costs, receipt_signature ...)
```

Privacy: delete `Ping` rows 7 days after a trip ends (scheduled job). `Trip.phone` and `name` are never sent in any prompt.

---

## 5. Core features in detail (no AI)

### 5.1 Trip registration (MVP, no KYC)
1. Form fields: name, phone, emergency contact, language (English, Hindi, Bengali, Assamese, Nepali, Tamil), route, start date, group size, any medical note (optional, kept on the phone only).
2. The server creates the `Trip`, plus a **signed demo pass**: an Ed25519 signature over `{trip_id, route_id, expires_at}`.
3. The pass is shown as a QR code that a checkpoint can scan to verify offline using the public key.
4. "Start trip" turns on location sharing (explicit consent screen) and downloads the safety pack and zones.

### 5.2 Danger-zone alerts (on the phone, offline)
- Zones are stored in IndexedDB and refreshed whenever the phone is online. New drawn zones arrive over SSE.
- On every location fix:
  - if `accuracy_m > 60`, ignore it (avoids false alarms)
  - run `turf.booleanPointInPolygon` on each active zone
  - also warn when within **80 m** of a danger zone (turf buffer), the "approaching" state
- **Hysteresis:** enter after 2 consecutive inside fixes; exit after 3 outside fixes. This stops flickering when GPS is noisy.
- **On enter:**
  1. full-screen alert in the zone's colour
  2. vibration pattern `[400,200,400,200,800]`
  3. a sound
  4. the message in the tourist's language, read from the cached advisory, or a template if it isn't cached
  5. a "Show safe way back" button that draws the nearest exit on the map (turf `nearestPointOnLine` to the route outside the zone)
- The event is queued and sent to the server, so the responder sees "Tourist entered landslide zone".

### 5.3 Crowd heatmap and stampede warning
- **Server:** every 10 s, the active trips' last pings go into a ~25 m grid (geohash level 8, or a simple lat/lon grid).
- Density = people per cell ÷ the cell's capacity, a value set per route segment (seeded; default 40 people).
  - green < 0.6
  - amber 0.6–0.9
  - red ≥ 0.9, or ≥ 0.75 and rising quickly (+30% in 1 minute)
- When a cell turns red, the server creates an `auto_crowd` zone covering the red cells (a merged buffer) and pushes it.
  - Tourists **heading toward it** (bearing within 45° and distance < 300 m) get: "Heavy crowd ahead. Wait about 20 minutes or take route B."
  - Tourists inside it get: "Crowd is dense here. Move slowly to the open area marked on the map."
- The responder map shows the heatmap layer, red cells pulse, and a crowd card appears with the number of people and the trend.
- **Demo:** judges plus about 60 seeded simulated dots gather in one cell, and it turns red live.

### 5.4 Offline SOS
- One big SOS button, held for 1.5 s with a ring filling up, so it can't be pressed by accident.
- Next screen: 5 large tiles: **Injured · Lost · Stuck · Medical · Unsafe**. Then "How many people?" (1, 2–5, 6+). Then an optional short note.
- On send:
  1. create `client_id = uuid`
  2. save to the IndexedDB queue with location, accuracy and the device time
  3. show the status **"Saved on phone · Pending transmission"** with a spinner
- **Sender loop:** every 10 s, and on `online` events, POST the queued items; delete each one only after the server confirms (`200` with `received_at`).
- **Duplicate protection:** `client_id` is unique, so a resend never creates a second SOS.
- **After 2 minutes still offline:** offer **"Send by SMS"**, which opens the SMS app prefilled with `SOS TRP-4821 30.7352,79.0669 INJ 3 1131`. In the demo the tourist presses Send; we can't send an SMS silently from a web app, so we say so.
- **When the server receives it:** status changes to **"Received by control room"**. When the responder accepts: **"Help acknowledged · 11:42 · Team Rambara"**, with a vibration.

### 5.5 "Are you safe?" mass check-in
- The responder selects a zone (or draws one) and presses **Send safety check**.
- Every trip whose last ping is inside, or that entered in the last 2 hours, gets a full-screen prompt: **I'm safe / I need help**.
- "I need help" opens the SOS flow with "Stuck" preselected.
- The responder sees a live tally: "42 asked · 31 safe · 3 need help · 8 no answer". Trips with no answer after 10 minutes turn orange on the map.

### 5.6 Missed check-in ("quiet" tourist)
- The phone sends a heartbeat every 2 minutes while sharing is on.
- The server marks a trip **quiet** after 15 minutes without a ping in a risky segment (30 minutes elsewhere). The dot turns orange, then red after 45 minutes.
- When the phone reconnects, it sends its queued pings, so the responder sees where the person went while offline.

### 5.7 Family link
- `https://<PUBLIC_URL>/f/<family_token>` is read-only, with no login.
- It shows only:
  - the trip name
  - the status (On trip / Safe / Help requested / Help acknowledged / Trip ended)
  - the last check-in time ("2 min ago")
  - the route name
- **No coordinates and no map.**
- The token expires when the trip ends, and the tourist can revoke it.

### 5.8 Responder: zone drawing and broadcast
- A **Draw zone** button opens a polygon tool. Then pick the kind (landslide / closed / restricted / wildlife / custom) and the severity, add an optional note, and press **Publish**.
- Publishing:
  1. saves the zone
  2. writes a signed log entry
  3. sends an SSE event to every phone
  4. triggers the advisory job (6.2)
- Phones apply the new zone immediately (template text first; the AI text replaces it when ready).

### 5.9 Signed, hash-chained event log
- Logged events: SOS created (device time), SOS received, incident created, accepted, en route, resolved, zone published, safety check sent and answered.
- `hash = sha256(prev_hash + type + payload_hash + ts)`. Each entry is signed with the server's Ed25519 key.
- A **Verify timeline** button recomputes the chain in the browser and shows ✓, or the first broken link.
- Prune's receipts are shown **next to** AI entries. They prove the AI call and its cost. The chain proves the timeline.

---

## 6. Prune features in detail (all LLM work)

### 6.1 Rules for every call
- **One module, `ai/prune_client.py` (from JURY), is the only code that imports the OpenAI SDK.**
- Base URL comes from `PRUNE_BASE_URL`, and the key from `.env`. **No provider keys anywhere.**
- `chat.completions` only, non-streaming.
- Ask for JSON in the prompt and validate it with Pydantic. On invalid output, do 1 repair call, then use the template.
- Headers on every call (same pattern as JURY; check the exact names and values in Prune's docs during hour 1):

```
X-Prune-Run-Id: <job id, e.g. inc_812 / pack_route3_hi / adv_zone44>
X-Prune-Run-Budget-Usd: <per job, see table>
X-Prune-Max-Steps: <per job>
X-Prune-Feature-Id: <pack | advisory | report | cluster | copilot | sms_parse>
X-Prune-Customer-Id: <route_id or park_id>      # cost per route/park
X-Prune-Cache: exact
X-Prune-Model-Policy: balanced                    # pinned model where noted
X-Prune-Injection: detect                         # never block an SOS
```

- **PII rule:** never put name, phone, pass ID or visa number in a prompt. Use `TRIP-#` labels and send only the needed fields. Prune's PII shield is a second layer, not the first.
- **Fallback rule:** every feature has a template. If there's an error, a 429 budget stop, a 402, a 503, or a timeout over 8 s, use the template and mark the output **"Template (AI unavailable)"**.
- **Retry policy (from JURY):**
  - 503: wait for `Retry-After`, retry once
  - 429 `rate_limit`: retry once after 20 s
  - 429 for a budget or cap: never retry
  - never send the same payload more than twice

### 6.2 Feature: offline safety pack
- **When:** at "Start trip", while the phone has network. Generated on the server and downloaded to IndexedDB.
- **Input** (no PII): `{route_id, route_facts (seeded: distance, altitude profile, medical posts, shelters, checkpoints, risky segments), language, profile_bucket}`
  - `profile_bucket` is one of `standard | senior | with_children | medical_note`. Buckets keep requests identical so they hit the cache.
- **Output JSON:**
  - `briefing` (5 bullets)
  - `segments` (per segment: risks and the nearest help)
  - `altitude_signs` (symptoms and what to do)
  - `phrasebook` (10 emergency phrases in the local language, with your language alongside)
  - `if_cards` ("If you are lost", "If someone is injured", "If the path is blocked", "If the crowd is too dense")
- **Model:** SMALL. Budget $0.01, max steps 3.
- **Cache key design:**
  - the request is `system + route_facts_version + language + profile_bucket`, nothing else, in a fixed key order
  - so every tourist on the same route, language and bucket sends a **byte-identical** request and gets Prune's exact-cache hit
  - **Cost slide line:** "Pack #1 paid. Packs #2 to #10,000 on the same route and language: served from Prune's cache."
- **Safety:** the facts come only from seeded `route_facts`. The prompt says "use only these facts; never invent distances or phone numbers". The validator checks that every phone number and medical post in the output exists in `route_facts`, the same idea as JURY's evidence validator. If not, it does 1 repair call, then uses the template pack.
- **Fallback:** a template pack built from `route_facts` (English and Hindi).

### 6.3 Feature: zone advisories in many languages
- **When:** a zone is published (seeded, drawn or auto-crowd).
- **Input:** `{zone_kind, severity, segment_name, responder_note (optional, max 200 chars), language}`
- **Output:** `{title (≤ 6 words), body (≤ 30 words), action (≤ 10 words)}`, in plain words.
- **Model:** SMALL, one call per language (6 languages). Budget $0.005 per zone.
- **Cache:** drawn landslide zones on the same segment produce the same request, so repeats are free. Responder notes are free text, so they're wrapped as data and checked with **injection detect**. If Prune flags them, the note is dropped and the template is used.
- **Fallback:** template sentences per kind and severity in each language.

### 6.4 Feature: SOS incident report
- **When:** an SOS reaches the server.
- **Input:** `{kind, people_count, note_text (untrusted), segment_name, distance_to_nearest_post, time_since_last_ping, tourist_language, responder_language}`
- **Output JSON:**
  - `headline` (≤ 12 words)
  - `what_we_know` (bullets; facts only from the input)
  - `unknowns`
  - `translated_note`
  - `suggested_questions` (3)
  - `priority` (P1/P2/P3)
- **Models:** SMALL first. Escalate to LARGE only if the note is longer than 150 characters, is in a language the small model handles badly, or the first output fails validation. Log the escalation and show it in the Routing River.
- **Budget** per incident: $0.02, max steps 4.
- **Injection:** the note is wrapped in `<tourist_note>` tags and treated as data. Prune's detect header is on. If it's flagged, show a "Suspicious text" chip on the card but **still create the incident** (never block an SOS).
- **Never invents:** the validator rejects outputs that mention injuries or crimes not present in `kind` or the note.
- **Priority is decided by rules, not AI:** medical or injured, or 6+ people, is P1. The AI's suggestion is shown but doesn't override the rule.
- **Fallback:** a template report built from the fields.

### 6.5 Feature: SOS grouping into one incident
- **Deterministic first:** DBSCAN on SOS points from the last 30 minutes (eps 150 m, min 2) forms clusters with no AI.
- **AI step:** one call per cluster, refreshed at most every 60 s while it grows.
  - **Input:** the cluster's SOS rows (kinds, counts, translated notes, segment)
  - **Output:**
    - `summary`, e.g. "38 people, 3 injured, stuck between Rambara and Linchauli"
    - `needs` (stretcher, oxygen, food)
    - `count_by_kind`
    - `notes_to_check`
- **Model:** LARGE, but only once per cluster per minute. This is a deliberate, justified expensive call. **Budget** per cluster: $0.03, max steps 6. When the budget is used up, the card shows the template summary and a "Budget limit reached" chip; the counts keep updating, since those are deterministic.
- **Validator:** the numbers in the summary must equal the computed counts. If they don't, the template is used.

### 6.6 Feature: responder copilot
- **When:** the officer opens an incident and presses **Brief me**.
- **Input:** the incident summary plus the route's seeded SOP snippets (standard operating procedure text per incident kind).
- **Output:** `steps` (≤ 5, each citing an SOP snippet id), `resources_nearby` (from seeded data only), and `message_to_tourists` (≤ 25 words, translated).
- **Model:** SMALL. Budget $0.01, max steps 3.
- **Validator:** every step must cite a real SOP id (the same idea as JURY's citation validator). Steps without a real citation are dropped.
- **Cache:** the same incident kind and SOP version give the same request, so the base brief is cached.

### 6.7 Feature: SMS SOS parsing (only if time allows)
- Coded SMS is parsed with a regex, no AI. For a free-text SMS ("help we r stuck near bridge 3 ppl"), a SMALL call extracts `{kind, people, place_hint}`. Budget $0.003. Fallback: create the SOS as "Unknown, needs a call".

### 6.8 Prune cost and receipts UI
- **Responder → "AI & cost" drawer**, reusing JURY's cost meters and receipts:
  - Today: total AI cost, calls, cache hits %, routed %, escalations, template fallbacks
  - **Cost per monitored trip** = AI cost for packs and advisories ÷ active trips
  - **Cost per emergency** = AI cost for reports, grouping and copilot ÷ incidents
  - A **Routing River** strip shows each call as a dot: small, large, routed, or cache (gold)
  - **Receipts table:** time, feature, model requested → model used, cache, cost, Prune's estimate without optimisations, signature (shortened), and a **Verify on Prune** link
- **Every AI-generated card** (pack, advisory, report, summary, brief) has a small footer: "AI · small model · ₹0.004 · receipt ✓". Tapping it opens that receipt.

### 6.9 Benchmark (for the 30% cost score)
Run on a fixed scenario:
- 500 simulated trips on 2 routes
- 3 languages
- 40 SOS events in 3 clusters
- 6 drawn zones

| Run | Setup |
|---|---|
| R1 Naive | LARGE model for everything, a unique pack per tourist (name in the prompt), no buckets |
| R2 Lean, no Prune features | Same prompts as SafeTrail, Prune routing and cache off |
| R3 SafeTrail cold | Prune on, empty cache |
| R4 SafeTrail warm | Prune on, cache warm |

**Report:**
- cost per monitored trip
- cost per emergency
- cache hit %
- % of calls routed
- p50 and p95 latency
- template-fallback rate
- validator rejections

Show it as a waterfall: Naive → our bucketed prompt design → Prune routing → Prune cache → final.

### 6.10 Budget layers
1. **Our own per-job budget** (the tables above), checked before each call.
2. **Prune's run budget and max steps** on each job (enforced by Prune).
3. **A Prune key spend cap** per day for the whole deployment. In the demo, also show a "Budget stress test" button: it runs a job with a tiny budget and shows the template fallback taking over, while alerts keep working.

---

## 7. Offline and connectivity

| Situation | What works |
|---|---|
| No network at all | Zone alerts, approaching warnings, the safety pack, the SOS saved to the queue, the pass QR, the map (cached tiles for the route) |
| 2G / SMS only | The above, plus SMS SOS (prefilled; the user taps Send) |
| Back online | Queue flushes, queued pings upload, zone updates download, acknowledgments arrive |
| Passing a checkpoint (Wi-Fi) | Full sync |

- **Map tiles:** at "Start trip", pre-cache tiles for the route's bounding box at zoom levels 12–16 (about 300–800 tiles). Show the progress: "Offline map 72%".
- The status pill on every tourist screen shows **Online · Offline · Sending… · SMS ready**.
- **Honest line:** "Nothing can send from a true dead zone. We warn before you enter one, save the SOS instantly, and send on the first signal."

---

## 8. UI and UX spec

### 8.1 Design principles
- **Calm, clear and trustworthy, like a good transit or maps app, not a sci-fi AI dashboard.** No neon, glows or gradients, and no "AI sparkles" everywhere.
- **The map is the main screen.** Information sits in bottom sheets over the map.
- **Big targets and few words:** this is used in rain, with gloves, while panicking. Minimum tap target 48 px; SOS 96 px.
- **Colour means status.** Red only for danger and SOS, amber for caution, green for safe, blue for info and your own location.
- **The tourist's language everywhere** (i18n from day one). Icons always come with text.
- **AI is labelled, not shown off:** a small "AI" tag and a receipt footer, and that's all.

### 8.2 Design tokens
- **Font:** Inter (UI) and JetBrains Mono (codes, times, receipts). Sizes 14 / 16 / 20 / 28.
- **Colours (light theme default, dark for night):**
  - background `#F7F7F5`, surface `#FFFFFF`, text `#1B1D1F`, muted text `#5F6368`
  - safe `#1E8E3E`, caution `#E37400`, danger `#D93025`, info `#1A73E8`
  - crowd heat: green → amber → red
- **Shape:** radius 14 for cards, 24 for sheets, full for pills. Shadows are soft and used only on floating elements.
- **Motion:** 150–250 ms. The zone alert slides up; SOS hold uses a ring fill. Respect reduced-motion settings.

### 8.3 Tourist mode screens
1. **Welcome:** a one-line promise, "Safety on your route, even offline". Buttons: *Start a trip* and *I'm a responder*. A language picker sits at the top.
2. **Trip setup** (3 steps with a progress bar):
   1. you (name, phone, emergency contact)
   2. route and dates, group size
   3. consent ("Share my location during this trip only", Stop anytime, deleted 7 days after the trip)
   Then **Start trip**.
3. **Preparing your trip:** a checklist that ticks off: Safety pack ✓, Offline map 72%…, Danger zones ✓, Pass ✓. It shows "You can go offline after this."
4. **Home (map):**
   - **Map:** your blue dot, the route line, zones (red/amber outlines with an icon), the crowd heat layer, checkpoints, medical posts.
   - **Top bar:** route name, a **status pill** (Online/Offline/Sending), and the battery state.
   - **Bottom sheet (collapsed):** "On trip · 3.2 km to Rambara · Next medical post 900 m". Drag it up for the segment details.
   - **SOS button:** fixed bottom right, red, round, labelled "SOS (hold)".
   - **Quick row:** *Safety pack* · *Share with family* · *Check in* · *Stop sharing*.
5. **Zone alert (full screen):**
   - red background, a large icon, and the title in the user's language
   - one-sentence body, then a primary button **"Show safe way back"** and a secondary "I understand"
   - an "AI-translated · receipt" footer, or "Standard warning" when it's the template
6. **Crowd warning (bottom sheet, amber):** "Heavy crowd ahead · Wait ~20 min or take Route B", with buttons *Show Route B* and *Remind me in 20 min*.
7. **SOS flow:**
   1. hold the button (ring fills)
   2. 5 tiles: *Injured / Lost / Stuck / Medical / Unsafe*
   3. people count
   4. optional note (a voice-to-text mic if supported)
   5. **status screen** with a 4-step tracker: *Saved on phone ✓ → Sending… → Received by control room → Help acknowledged*
   - Offline, it shows "Pending transmission. We'll send it automatically" and, after 2 minutes, a **Send by SMS** button.
   - "Cancel SOS" needs a second hold.
8. **"Are you safe?" prompt (full screen):** two huge buttons, green **I'm safe** and red **I need help**.
9. **Safety pack:** tabs *Briefing · Phrases · If… · Help points*, all readable offline. Phrases show both languages with a speaker button (TTS where available).
10. **My pass:** a QR card with the trip details, valid until the trip ends, and a "Verified offline ✓" badge when a checkpoint scans it.
11. **Share with family:** create the link, copy or WhatsApp-share it, preview exactly what family sees, and **Revoke**.
12. **Trip end:** "You're back safe?" Then summary and data deletion info.

### 8.4 Responder mode screens (tablet or laptop first, works on phone)
1. **Login:** demo officer accounts.
2. **Control map (main):**
   - **Map** (fills the screen): tourist dots (blue on trip, orange quiet, red SOS), zones, the crowd heat layer, incident pins with counts.
   - **Left rail filters:** *All · SOS · Quiet · Crowd*.
   - **Top bar:** route or park picker, live counts ("412 on trail · 3 incidents · 1 crowd alert"), the **AI & cost** button.
   - **Actions (top right):** **Draw zone**, **Send safety check**, **Simulation** (seed dots or a walk).
3. **Incident panel (right side sheet):**
   - header: priority chip, headline, time since the first SOS, people and injured counts
   - AI summary card (receipt footer), unknowns, suggested questions
   - map preview of the cluster, and the list of SOS rows (kind, count, translated note, chips such as *Suspicious text*)
   - buttons: **Accept** (primary), *En route*, *Resolved*, **Brief me** (copilot), *Message tourists*
   - **Timeline** tab with the signed events and **Verify timeline ✓**
4. **Crowd card:** density trend sparkline, people count, actions *Broadcast warning* and *Open Route B*.
5. **Safety check tally:** live counters and a list of trips with no answer.
6. **AI & cost drawer:** Section 6.8.

### 8.5 Family view (web link)
One card: name, status chip, "Last check-in 2 min ago", route name, and "Help acknowledged at 11:42" if relevant. No map.

### 8.6 Empty, error and loading states (write all of these)
- No GPS: "Turn on location to get zone alerts".
- Low GPS accuracy: "Location is rough (±80 m); alerts may be delayed".
- Offline: pill turns grey; SOS still enabled.
- AI unavailable: cards show "Standard text (AI unavailable)". **Never show an error where a warning should be.**
- Budget hit: "Budget limit reached, using standard text", shown only to responders.

---

## 9. API and events (base `/api`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/trips` | Create a trip and its demo pass |
| POST | `/trips/{id}/start` | Start sharing and return pack, zones, tile bounds |
| POST | `/trips/{id}/pings` | Batch of pings (works for queued uploads) |
| POST | `/trips/{id}/stop` | Stop sharing |
| GET | `/routes/{id}/pack?lang=&bucket=` | Safety pack (AI through Prune, cached) |
| GET | `/zones?route_id=` | Active zones |
| POST | `/zones` | Responder publishes a zone |
| POST | `/sos` | `{client_id, ...}`, idempotent |
| POST | `/sms/inbound` | SMS gateway webhook (if time allows) |
| POST | `/incidents/{id}/accept` · `/status` | Responder actions |
| POST | `/incidents/{id}/brief` | Copilot |
| POST | `/safety-checks` | Send "Are you safe?" |
| POST | `/safety-checks/{id}/answer` | Tourist answer |
| GET | `/family/{token}` | Status only |
| GET | `/log/verify?entity=` | Chain and signatures |
| GET | `/ai/stats` · `/ai/receipts` | Cost drawer |
| POST | `/sim/seed` · `/sim/walk` | Demo simulation |
| GET | `/events` | SSE |

**SSE events:**
- `zone.published`
- `zone.crowd_red`
- `sos.received`
- `incident.updated`
- `incident.accepted`
- `check.sent`
- `check.answer`
- `trip.quiet`
- `ai.call`, which feeds the Routing River

---

## 10. Security and privacy
- Location sharing is opt-in per trip; **Stop sharing** is always visible; pings are deleted 7 days after the trip ends.
- The family link shows status only and can be revoked.
- No PII in prompts; Prune's PII shield is a second layer.
- The pass is signed with Ed25519 and verifiable offline. Replay protection: the pass has an expiry, and SOS uses a unique `client_id`.
- **Spoofing checks** (flag, never block):
  - impossible travel (> 30 km/h on a trek segment)
  - a duplicate `client_id`
  - a forged pass signature
  - free-text injection in notes
- Officer login is required for responder mode; every action goes into the signed log.

---

## 11. Demo setup and seed data
- **Seeded routes:**
  - Kedarnath (Gaurikund → Kedarnath, with checkpoints and medical posts)
  - Sikkim (Lachung area)
  - one tiger reserve with a core zone
- **Seeded `route_facts`, SOPs and zones:** one landslide, one restricted, one wildlife core. All marked **Simulated**.
- **The venue route:** a special "Hall demo" route drawn around the hackathon building, so judges' real GPS works.
- **Simulation panel:**
  - seed 60 dots in a cell (crowd)
  - walk a fake tourist along the route
  - fire 5 SOS events in a cluster
- **Backups:**
  - QR checkpoint on a door (scan = entered zone)
  - phone hotspot
  - templates if Prune is down
- **Demo script:** as in `SAFETRAIL_PITCH.md` Section 8.

---

## 12. Build schedule (two AI agents and the team)

| Hours | Agent A (backend, AI) | Agent B (app, UI) | Humans |
|---|---|---|---|
| 0–1 | Copy JURY's prune_client, LlmCall, SSE; new models; test one Prune call and a cache hit | Vite PWA shell, routing, Tailwind tokens, MapLibre map | Draw demo routes and zones (geojson.io); write route_facts and SOPs |
| 1–3 | Trips, pings, zones, SOS (idempotent), event log | Trip setup, home map, geofence engine with hysteresis, zone alert | Test GPS in the hall; fix zone sizes |
| 3–5 | Safety pack and advisories (6.2, 6.3) with validators and templates | SOS flow, IndexedDB queue, status tracker, offline pill | Translate templates (6 languages) |
| 5–7 | Crowd engine, DBSCAN clustering, report and grouping (6.4, 6.5) | Responder map, incident panel, Draw zone, SSE | Seed the simulation; rehearse the SOS offline flow |
| 7–9 | Safety check, quiet trips, family link, copilot (6.6) | "Are you safe?" screens, family view, safety pack screens | Write `docs/EXPLAINER.md` sections |
| 9–10 | AI & cost endpoints, receipts, benchmark runner | AI & cost drawer, Routing River, receipt footers | Run the benchmark R1 to R4 |
| 10–11 | Hardening: retries, budget stress test, spoof flags | Empty/error states, i18n pass, tile pre-cache | Full rehearsal x2 with real phones |
| 11+ | **Phase 2 (Section 14) only if everything above is done** | | |

**Cut order if late:**
1. SMS inbound webhook
2. Copilot
3. Wildlife route
4. Benchmark R2
5. Trip replay
6. Dark theme

---

## 13. Definition of done
- [ ] A judge scans the QR, starts a trip, and appears on the map within 20 s
- [ ] A drawn zone alerts every phone inside within 5 s
- [ ] The crowd cell turns red live and warnings reach approaching phones
- [ ] An airplane-mode SOS shows Pending, then auto-sends with no duplicate
- [ ] 3 or more SOS events merge into one incident whose AI summary counts match exactly
- [ ] "Are you safe?" tally updates live
- [ ] Accept shows "Help acknowledged" on the tourist's phone; Verify timeline ✓
- [ ] Family link shows status only
- [ ] With Prune switched off or over budget, every alert still works and cards show template text
- [ ] AI & cost drawer shows real receipts with working Verify links, and the benchmark numbers are measured
- [ ] No provider key in the repo; no PII in any logged prompt

---

## 14. Phase 2: Digital Tourist ID with e-KYC (work in progress; build only if time allows)

> Pitch line: "We're extending the demo pass into a Digital Tourist ID that's linked to the permit each traveller already holds."

### 14.1 Which ID for whom
| Traveller | ID used | Why |
|---|---|---|
| Foreign tourist | **Visa / e-Visa number** and passport number; **PAP/RAP permit** where a state requires it | Foreigners have no Aadhaar. The visa is already checked by immigration and has a built-in validity period |
| Indian tourist | **e-ILP number** (Arunachal, Nagaland, Mizoram, Manipur), **yatra registration** (Char Dham/Kedarnath), or DigiLocker / passport / voter ID | These permits already exist for these routes |
| Aadhaar | **Optional only**, masked (last 4 digits), offline e-KYC XML if the user chooses | The Supreme Court's 2018 ruling bars making it mandatory; also data minimisation |

### 14.2 Flow (simulated in the hackathon)
1. The tourist picks a type: Foreign or Indian.
2. They enter the ID number. A **mock registry** (seeded JSON standing in for the e-Visa, e-ILP and yatra systems) returns validity dates and the permitted zones.
3. **Document photo check (optional):** the camera captures the visa or permit page. The OCR text is matched to the typed number on the phone (tesseract.js). Images never leave the phone in the demo.
4. **The pass is issued:** signed `{pass_id, id_type, id_last4, valid_from, valid_to, permitted_zone_ids}`, expiring with the permit.
5. **Permit-aware geofencing:** zones the pass doesn't allow (a restricted area without a PAP) show as *Not permitted for your pass*, with a warning before entry.
6. **Checkpoint scan:** an officer scans the QR and verifies the signature offline. The result is ✓ Valid, ✗ Expired or ✗ Forged.

### 14.3 Prune's role in Phase 2
- **Permit rules explainer:** the official text for each state is turned into a simple "What your permit allows" card in the tourist's language (SMALL model, cached per state, permit type and language).
- **No ID numbers in prompts.** Only the permit type and the state.

### 14.4 Tamper-proof ID record
- Pass issue and revoke events go into the same hash-chained, signed log. Pitch this as "blockchain-style tamper evidence without the cost of running a chain". A permissioned ledger (for example Hyperledger Fabric) is listed as future work for a multi-agency rollout.

### 14.5 What we'd need for a real rollout
- Access to official permit and e-Visa verification APIs
- Verified official geofence data from state and park authorities
- An authorised integration with 112 or the police
- A data-protection review under India's DPDP Act
