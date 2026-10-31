# SafeTrail: everything you need to build the PPT

Use this file to build the deck in Google Slides, PowerPoint or Canva. It has the slide order, the words for each slide, what to say, which screenshots to take, the numbers you can and can't quote, and the judge Q&A. Everything matches what's built on `main` (31 Oct, after Hardik's Prune + Gemini work).

Rules for every slide: **one idea per slide, big screenshots, at most 3–4 short lines of text.** Say the rest out loud (speaker notes).

---

## 0. Plan your time

| Slot you get | What to show |
|---|---|
| **5 minutes** | Slides 1–4 (60 s) → live demo (3 min) → slides 10–11 (40 s) → slide 16 (20 s) |
| **8 minutes** | All main slides 1–16, with the 3-minute demo at slide 7 |
| **Q&A** | Use the backup slides B1–B5 and Section 6 below |

Rehearse with a timer. The demo is the most important part: if time is short, cut slides, not the demo.

---

## 1. Slide-by-slide content

### Slide 1 · Title
- **On the slide:** `SafeTrail` · *Warn early. Never lose an SOS. Prove every response.*
- Small text: Team name and members · BIOS V2, Thapar Institute · Prune track "Ship It Lean: AI Apps on a Budget"
- **Visual:** the app icon, plus a mountain trail photo (use your own or a properly licensed photo).
- **Say:** "We're team ___. We built SafeTrail, a safety companion for treks, pilgrimages and national parks."

### Slide 2 · The moment
- **On the slide:** "A landslide on the Kedarnath trail. No signal. No common language."
- **Visual:** one strong photo of a mountain trail or pilgrim crowd. No text blocks.
- **Say:** "Imagine you're a pilgrim on the Kedarnath route. A landslide blocks the path, your phone shows no signal, you don't speak the local language, and a crowd is building up behind you. What happens next?"
- **Optional real example** (verify before using, see Section 3): North Sikkim, October 2023: a glacial lake burst, the Teesta flooded, and thousands of tourists were stranded around Lachen and Lachung.

### Slide 3 · Why it goes wrong
- **On the slide:** three columns with icons:
  1. **No warning:** people walk into closed or dangerous stretches without knowing.
  2. **No signal:** calls fail exactly where help is needed most.
  3. **No common language:** a pilgrim or foreign tourist can't explain where or what.
- Bottom line: *"And responders get dozens of confused, duplicate calls."*
- **Say (memorise):** "Today's safety depends on tourists spotting danger, having signal, and explaining their location clearly. In a mountain emergency, all three can fail at the same time. SafeTrail is built for exactly that moment."

### Slide 4 · SafeTrail in one line
- **On the slide:** *"One app that warns tourists before danger, keeps their SOS safe when there's no signal, and gives responders one clear picture."*
- Three promise chips: **Warn early** · **Never lose an SOS** · **Prove every response**
- Two small labels: **Tourist app** · **Responder console**, plus *Family link*
- **Say:** "It's one app with two sides. The tourist side works offline. The responder side turns chaos into one clear picture. And families see status, never location."

### Slide 5 · The tourist app
- **Visual:** 3 phone screenshots side by side: map with route + weather card, full-screen landslide alert, SOS tracker. (Shots 2, 3, 4 in Section 4.)
- **On the slide** (icons + 3–4 words each):
  - Danger-zone alerts, **offline**
  - Crowd warnings before you walk in
  - Hold-to-SOS: saved on the phone, sent on first signal
  - "Are you safe?" check after a disaster
  - Offline safety pack + "Show to a local" phrases
  - Live weather on every section
  - Family link: status only
- **Say:** "The phone checks your position against danger zones by itself, with no internet. Hold SOS and it's saved on the phone and sent automatically the moment any signal returns, by SMS if data is down. You can call for help by tapping, without speaking the language."

### Slide 6 · The responder console
- **Visual:** big screenshot of `/r` on the Kedarnath route with demo data, with the incident panel open (Shot 6).
- **On the slide:**
  - Live map: travellers, danger zones, crowd heat, weather
  - **40 SOS → 1 incident**, with exact counts
  - AI report in the responder's language + next steps from the SOP
  - Accept → the tourist sees "Help acknowledged"
  - Signed timeline: edits are detectable
- **Say:** "When a landslide hits, responders don't get 40 separate calls. They get one incident: how many people, how many injury reports, where, and what they wrote, translated. Counts come from code, not AI, so they're always exact. One tap on Accept, and every phone in that group shows help is coming."

### Slide 7 · Live demo
- **On the slide:** just "Live demo: scan to join" and the `/stage` projector view (switch to it live).
- **Do:** follow `docs/DEMO_SCRIPT.md` exactly (3 minutes): join → landslide here → crowd surge → airplane-mode SOS → more SOS → "Are you safe?" → Accept + Verify timeline → family link → AI & cost.
- **Say once:** "Demo zones and dispatches are simulated."

### Slide 8 · How it works
- **Visual:** the architecture diagram (Section 5): Phone → Server → Prune → models, plus OpenStreetMap and Open-Meteo.
- **On the slide, big:** *"The AI is never in the emergency path."*
- Small table:

| Works with **no internet** | Needs a connection |
|---|---|
| Zone and crowd alerts, safe way back | Sending the SOS (data, SMS or checkpoint) |
| Saving the SOS with its time and place | AI reports, translation, summaries |
| Safety pack, phrases, pass check | Live weather updates, the responder screen |
| Whistle, flash, compass to shelter (GPS works without mobile network) | |

- **Say:** "Everything that keeps you safe runs on the phone or as plain code on the server. The AI only writes and translates. If the AI is down or over budget, every alert and every SOS still works, and the screen shows standard text."

### Slide 9 · Where AI helps, and where it doesn't
- **On the slide:** two columns.
  - **AI writes** (via Prune): offline safety pack per route and language · zone warnings in each tourist's language · incident report + translation · group summary · responder next steps (citing the SOP) · reading free-text SMS · permit explainer card
  - **Plain code decides:** zone alerts · crowd detection · SOS saving and grouping · counts and priority · check-ins · pass signatures · weather warnings
- **Say:** "Rules decide; the AI only writes and translates. And our validators reject any AI text that invents a phone number, a count, an injury or an SOP step. It gets one repair attempt, then we use standard text."

### Slide 10 · Every AI call through Prune
- **Visual:** screenshot of **AI & cost** (Routing River + a receipt row expanded), Shot 8.
- **On the slide:**
  - One module, one base URL; a checker fails the build on any direct provider call
  - **Small model by default, large only when needed:** Gemini 3.1 Flash-Lite / Gemini 3.5 Flash
  - **Three budget layers:** our governor → Prune run budget + step limit → daily key cap
  - Prune injection detection + no personal data in prompts
  - **Signed receipt on every call** (Ed25519, verifiable at withprune.com/verify)
- **The honest twist (judges will love this):** *"We tested Prune's cache on real incident prompts. At first it returned one incident's summary for a different incident, even in exact mode. In an emergency app that's unacceptable, so every call now carries a fingerprint of the request and a strict setting. Only identical requests can match, and a live check fails if that ever changes."*
- **Say:** "Prune lets us make AI cheap and controlled, but we verified everything. Our Prune check script runs 11 live checks: receipts are signed, a run over budget gets stopped with a 429, injection attempts are flagged, and a different request never gets a cached answer."

### Slide 11 · What it costs
- **On the slide:** the measured numbers from the benchmark (fill in after it runs, Section 3):

| | R1 Naive (big model for everything) | R2 SafeTrail, no Prune features | R3 SafeTrail + Prune |
|---|---|---|---|
| Cost per monitored trip | [fill] | [fill] | [fill] |
| Cost per emergency | [fill] | [fill] | [fill] |
| Counts correct | [fill] | [fill] | [fill] |

- **Plus the levers that make it cheap** (true today):
  1. Safety logic is plain code: **zero AI cost** for alerts, crowd, SOS, grouping and weather warnings
  2. One safety pack per route + language + profile, **shared by every tourist** (pack #2 onward costs nothing)
  3. Small model by default; group summaries at most once a minute, max 3; SOS floods never trigger AI
  4. Hard budgets per job, enforced by Prune
- **Say:** "We don't guess costs. Every number comes from Prune's own receipts, and we compare four setups on the same 500-trip scenario."
- ⚠️ **If the benchmark hasn't run yet,** show only the levers and say: "Measured numbers are on our benchmark page after the run." Don't quote any rupee figure. See Section 3.

### Slide 12 · Trust and safety
- **Visual:** Verify timeline ✓ screenshot + Break-it "CAUGHT" screenshot (Shots 6 and 10).
- **On the slide:**
  - **Tamper-evident timeline:** every step hash-chained and signed
  - **Signed trip pass:** checked offline at checkpoints
  - **Abuse checks:** replayed SOS, forged pass, impossible GPS jumps, SOS floods, fake responders
  - **Privacy:** opt-in per trip, Stop sharing, location deleted 7 days after the trip, family sees status only, no names on the projector
  - **"Break it" round:** judges try 8 real tricks live
- **Say:** "Editing any step in the timeline breaks the chain, and the app shows exactly where. And you can try to break it yourself: forge a pass, replay an SOS, teleport your GPS. Every trick is a real way people abuse safety systems."

### Slide 13 · Real data, honestly labelled
- **Visual:** map screenshot of the real Kedarnath trail with the hospital and shelter pins, plus the weather card.
- **On the slide:**
  - Kedarnath trail from **OpenStreetMap**: the real 15.1 km trek path
  - Real hospital and rain shelters from OpenStreetMap
  - **Live weather** per section from Open-Meteo: e.g. −0.5 °C at Kedarnath, 3,549 m (31 Oct)
  - Medical posts, checkpoints, zones and responders: **simulated, and labelled that way**
- **Say:** "The trail, hospital, shelters and weather are real. What we couldn't get from official sources is clearly labelled simulated. A real rollout plugs in official zone and permit data."

### Slide 14 · Who it's for and how it pays
- **On the slide:**
  - **Pilots:** Kedarnath and the Char Dham Yatra · North East permit states (Sikkim, Arunachal) · national parks (e.g. Corbett)
  - **Customers:** state tourism departments, pilgrimage boards, park authorities (B2G)
  - **Model:** annual licence + a small fee per registered tourist
  - **Why it scales:** the AI cost per tourist stays tiny, because safety logic needs no AI and packs are shared
- **Say:** "Routes that already require registration or permits are the natural start, because the tourist list already exists."

### Slide 15 · What's next
- **On the slide:**
  - **Digital Tourist ID** linked to the e-Visa or e-ILP the traveller already has (built as a simulated demo)
  - Phone-to-phone relay: another trekker's phone carries your SOS out of a dead zone
  - Satellite SOS where phones and Indian rules allow
  - Official disaster-alert feeds turned into zones automatically
  - "Overdue at next checkpoint" alerts
  - Native app for background location
- **Say:** "The Digital Tourist ID already works in our demo with a simulated registry: the full ID number is never stored and never reaches the AI."

### Slide 16 · Close
- **On the slide:** *"SafeTrail doesn't replace 112. It's the safety layer before it."* · GitHub: `github.com/gaurvit06/Safetrail` · Thank you
- **Say:** "SafeTrail warns people before danger, keeps their SOS when there's no signal, and gives responders one clear picture, with every AI call through Prune and the AI never in the emergency path. Thank you."

### Backup slides (only for questions)
- **B1 · No network at all?** "Nothing can transmit with zero network: not our app, not 112. So we warn before people reach danger, the control room sees when someone goes silent and where they were last seen, and the phone guides them offline to the nearest shelter. Relay and satellite are next."
- **B2 · Why not just call 112?** "If any network is available, call 112, and our app tells you to. We add what a call can't: warnings before danger, an SOS that waits and sends itself, no need to speak the language, and 40 calls grouped into one incident."
- **B3 · Engineering proof:** 76 backend tests + 6 app tests · the whole demo played in real browsers with and without the map · a checker that fails on direct AI calls or committed keys · Prune check script: 10 of 11 live checks OK · signed receipt verified locally against Prune's public key, and a tampered copy fails.
- **B4 · Honest limits:** not yet tested on real phones in the mountains · the free Gemini key is sometimes busy, so standard text shows · our injection scanner matches English only (Hindi and Assamese rely on Prune's detection) · Sikkim and Corbett routes are drawn by hand and simulated.
- **B5 · The cache story:** the test results from `docs/DECISIONS.md` 28 (exact mode alone returned the first incident's summary for a different incident; with a request fingerprint and a strict setting, all six changes to a real prompt got their own correct answer, and a true repeat still hit the cache).

---

## 2. Pitches to memorise

**30 seconds:**
> "Imagine trekking to Kedarnath when a landslide blocks the path. No signal, no common language, and a crowd building behind you. SafeTrail is a safety app for treks, pilgrimages and parks. Your phone warns you before you walk into a landslide zone or a dangerous crowd, even offline. If you're in trouble, your SOS is saved instantly and sent on the first signal. Responders see one clear, grouped incident and accept it, and every step is signed so nobody can rewrite it. AI only writes and translates, every AI call goes through Prune, and if the AI fails, safety keeps working."

**Lines to remember:**
- "Rules decide; the AI only writes and translates."
- "We never claim it works with no network: it warns you offline, keeps your SOS, and sends it on the first signal."
- "We tested Prune's cache on real prompts, caught it mixing up incidents, and fixed it so only identical requests match."
- "Every number on our screens comes from Prune's receipts. If we don't know a number, the screen says n/a."

---

## 3. Numbers: what you can say and what you can't

**Safe to say (verified by us):**
- The Kedarnath trail in the app is the real OpenStreetMap trek path: **15.1 km**.
- Live weather from Open-Meteo, per section, refreshed every 15–30 minutes (example on 31 Oct: −0.5 °C at 3,549 m near Kedarnath).
- **76 backend tests and 6 app tests pass**; the no-direct-AI-calls checker passes.
- `scripts/prune_check.py`: **10 of 11 live checks OK** (the remaining warning is about a Prune dashboard setting; the app enforces the same limit itself).
- Prune returns a **signed receipt** on every call (Ed25519); a sample receipt passed a local check against Prune's public key, and a tampered copy failed.
- A run over budget is stopped by Prune with a **429**, and the app falls back to standard text.

**Fill in after the benchmark runs** (`backend\.venv\Scripts\python scripts\benchmark.py --trips 100`, results in `docs/BENCHMARK.md` and on `/benchmark`):
- Cost per monitored trip, cost per emergency, and counts correct for R1–R3.
- **Before quoting them:** check Prune's Gemini costs against Google's own usage page (`docs/DECISIONS.md` 35: Prune's reported Gemini costs ignore output).

**Do NOT say:**
- Any rupee or paise figure until it's measured and checked.
- "Works with no network", "guaranteed rescue", "predicts stampedes", "catches all GPS spoofing", "integrated with government permits", "Prune's cache saves us money" as a rupee figure (not checked yet), "Prune picks the cheapest model" (no call was rerouted in our tests).
- "PostgreSQL / PostGIS / React Native / WebSockets": we use SQLite, an installable web app (judges join by QR, no app store) and Server-Sent Events.
- "DBSCAN": say "density-based grouping, like DBSCAN: SOS within 150 m and 30 minutes form one incident".

**Real-world facts** (only use them after checking a news source, and cite it on the slide):
- North Sikkim, October 2023: a glacial lake outburst flooded the Teesta and stranded thousands of tourists around Lachen and Lachung. [verify the number]
- Kedarnath, June 2013: flash floods killed thousands of people. [verify the official figure]
- Kedarnath sees lakhs of pilgrims every season. [verify the latest season's count]
- 112 is India's single emergency number (ERSS).

---

## 4. Screenshot shot list

Take these on the demo laptop with the app running (`http://localhost:8000`). Load demo data first: `backend\.venv\Scripts\python scripts\seed_demo.py --reset`. For phone shots, use your phone over the tunnel, or the browser's mobile view (Chrome DevTools → device toolbar → iPhone).

| # | Shot | How |
|---|---|---|
| 1 | Judge join screen | `/j` on a phone |
| 2 | Trip map with the route and the weather card | Start a trip on **Gaurikund → Kedarnath** at `/t/new`, then open the bottom sheet |
| 3 | Full-screen landslide alert | Trip screen → **Demo: tap the map** → tap inside the red zone twice |
| 4 | SOS tracker: "Pending transmission", then "Help acknowledged" | Airplane mode → hold **SOS** → send; airplane mode off; accept it on `/r` |
| 5 | Safety pack → Phrases → "Show to a local" | Trip screen → **Phrases** → tap a phrase |
| 6 | Responder map + incident panel + **Verify timeline ✓** | `/r` (PIN 2468) → route **Gaurikund → Kedarnath** → open the P1 incident → **Timeline** → **Verify timeline** |
| 7 | Responder weather panel | `/r`, above the incident list |
| 8 | AI & cost: Routing River + an expanded receipt | `/r` → **AI & cost** (after a live round with keys) |
| 9 | Projector view with the Join QR and the counter | `/stage` (PIN 1357), or `/stage?route=kedarnath` |
| 10 | Break it → **CAUGHT** | `/break` → **Forge a pass** → **Try it** |
| 11 | Family view: status only | Trip screen → **Family** → open the link |
| 12 | Benchmark page | `/benchmark` after the benchmark run |
| 13 | Receipt verified on Prune | Paste `docs/receipts/sample_receipt.json` at withprune.com/verify (HANDOFF item) |

Crop tightly, keep the phone frame, and don't show real names or phone numbers.

---

## 5. Architecture diagram (draw it as 4 boxes)

```
 ┌─────────────────────────────┐        ┌──────────────────────────────────┐
 │  PHONE (works offline)      │  data  │  SERVER (FastAPI + SQLite)       │
 │  • zone + crowd alerts      │ ─────► │  • trips, zones, SOS, incidents  │
 │  • SOS queue (sends later)  │  SMS   │  • grouping with exact counts    │
 │  • safety pack, phrases     │ ─────► │  • crowd + quiet detection       │
 │  • pass check, compass      │        │  • signed, hash-chained log      │
 └─────────────────────────────┘        │  • live updates to screens       │
                                         └──────┬───────────────┬──────────┘
                                                │ every AI call │ real data
                                                ▼               ▼
                                   ┌──────────────────┐  ┌──────────────────────┐
                                   │  PRUNE gateway   │  │ OpenStreetMap (trail, │
                                   │  budgets, cache  │  │ hospital, shelters)   │
                                   │  receipts, shield│  │ Open-Meteo (weather)  │
                                   └────────┬─────────┘  └──────────────────────┘
                                            ▼
                                   Gemini 3.1 Flash-Lite (small)
                                   Gemini 3.5 Flash (large)
```

Put one red banner across the bottom: **"The AI is never in the emergency path."**

---

## 6. Judge Q&A cheat sheet

1. **Explain it in one sentence.** An offline-first safety app for treks, pilgrimages and parks that warns before danger, keeps an SOS when there's no signal, and gives responders one clear picture.
2. **Why do you need AI at all?** For language work: safety packs per route and language, warnings in each tourist's language, translating SOS notes, summarising a group of SOS. Everything safety-critical is plain code.
3. **Why Prune, not a direct API?** One gateway for every call: budgets and step limits it enforces, an exact cache, injection detection, and signed receipts so we can prove cost. Our checker fails the build if anything bypasses it.
4. **What if Prune or the AI is down?** Cards show standard text. Alerts, SOS, grouping and the timeline keep working. You'll see this on stage, because the free Gemini key is sometimes busy.
5. **How do you keep AI costs low?** No AI in safety logic; shared safety packs; small model by default; refresh limits; hard budgets per job; daily key caps.
6. **Do you use Prune's cache?** Yes, but only for identical requests. In testing, exact mode alone returned one incident's summary for a different incident, so every call now sends a fingerprint of the request and a strict setting, and a live check fails if that stops working. Our own job store also makes sure the same work is never paid for twice.
7. **How much does one tourist cost?** Give the benchmark numbers if they're measured and checked. Otherwise: "It's measured from Prune's receipts on our benchmark page. We don't quote a number we haven't verified."
8. **Can an SOS go out with zero signal?** No, and nothing can. It's saved with its exact time and place and sent on the first signal, by SMS if data is down, or at a checkpoint. If any network is available, the app tells you to call 112.
9. **Why not just 112?** We don't replace it. We add warnings before danger, an SOS that waits and sends itself, no need to speak, and grouped incidents.
10. **How do you group SOS?** SOS within 150 m and 30 minutes become one incident, like DBSCAN. Counts are computed by code; the AI only writes the summary, and a validator rejects any number that doesn't match.
11. **What if the AI hallucinates?** Validators check every output against the input: no invented phone numbers, counts, injuries or SOP steps. One repair attempt, then standard text. Priority is set by rules, never by the AI.
12. **What if someone types "ignore your instructions" in an SOS?** Our scanner and Prune's injection detection flag it, the SOS still goes through, and priority stays rule-based. Try it in the Break-it round.
13. **Can GPS be faked?** We flag impossible jumps and don't update the position from them. We don't claim to stop all spoofing.
14. **Privacy?** Opt-in per trip, Stop sharing anytime, location deleted 7 days after the trip, family sees status only, no names on the projector, and no personal data in AI prompts.
15. **Do you need Aadhaar?** No. Phase 2 links the permit the traveller already has (e-Visa for foreigners, e-ILP or yatra registration for Indians). Aadhaar is optional and only the last 4 digits are kept.
16. **Is the crowd number the real crowd?** It's the number of SafeTrail users in the area: an estimate, not a headcount. Official counts from checkpoints would make it better.
17. **What's real and what's simulated?** Real: the Kedarnath trail, hospital and shelters (OpenStreetMap), and live weather. Simulated and labelled: zones, medical posts, checkpoints, responders and the permit registry.
18. **Biggest limitation?** Communication in true dead zones, and the accuracy of hazard data. We'd need official zone feeds and relay or satellite for full coverage.
19. **Who pays?** State tourism departments, pilgrimage boards and park authorities: a licence plus a small per-tourist fee.
20. **Why a web app, not a native app?** Judges, and tourists at a checkpoint, join by scanning a QR code, with no app store. It still works offline once opened. A native app comes later for background location.

---

## 7. Design guide (match the app)

| Use | Colour |
|---|---|
| Brand / headings | `#0F766E` (teal) |
| Danger / SOS | `#D93025` |
| Caution / crowd | `#D97706` |
| Safe / acknowledged | `#1E8E3E` |
| Info | `#1A73E8` |
| Background | `#F6F5F1` (light slides) or `#111315` (demo and architecture slides) |
| Text | `#1B1D1F` |

- Font: **Inter** (titles 40–48 pt, body 24–28 pt). Use monospace only for numbers.
- Colour means status, exactly as in the app: red only for danger and SOS.
- Real screenshots beat icons. No clip-art, and no more than 4 lines of text per slide.
- Put "Simulated" labels on any screenshot that shows demo data.

---

## 8. Before you present

- [x] The public key stays on the small model: the app enforces it (`docs/DECISIONS.md` 40)
- [x] Verified the sample receipt at withprune.com/verify: `docs/receipts/receipt-verified.png` (shot 13)
- [ ] Check the benchmark's numbers against Google's usage page, then fill in slide 11
- [ ] Draw the real venue in `backend/seed/routes/hall.json`; test GPS with 3+ phones over the tunnel
- [ ] Rehearse `docs/DEMO_SCRIPT.md` twice with real phones (Android and iPhone); record a backup video
- [ ] Every teammate can give the 30-second pitch and answer questions 1–10 without notes
