# SafeTrail live demo (3 minutes, judges take part)

Order (SPEC 10.4): join → zone alert → crowd → offline SOS → cluster → safety check → accept → family → receipt. Then the Break-it round if time allows. The words come from SPEC 15.1; the buttons below are the app's real labels.

Say once, early: **"Demo zones and dispatches are simulated."**

## Before judging (start 30 minutes early)

- [ ] Backend running on the demo laptop (`uvicorn app.main:app --port 8000` from `backend/`).
- [ ] Tunnel running (`cloudflared tunnel --url http://localhost:8000`). Put the https URL in `PUBLIC_URL` in `.env` and restart the backend, so the QR codes point to it. Phones need https for GPS.
- [ ] The `hall` route is the real venue (drawn on geojson.io), and the landslide zone covers **the whole room**: indoor GPS is only accurate to 10–30 m.
- [ ] Checkpoint QR printed and stuck on a door (backup way to fix a phone's location).
- [ ] Projector: `/stage` (presenter PIN, default 1357), showing the **Join** QR.
- [ ] Presenter's phone: `/stage/control` (presenter PIN).
- [ ] Responder: a judge on `/jr` (responder PIN, default 2468), or a teammate on `/r`.
- [ ] Prune keys in `.env`, `scripts/prune_check.py` passed, daily cap set. The demo was rehearsed twice, so Prune's normal-rate baseline includes demo traffic.
- [ ] Phone hotspot ready for the laptop.
- [ ] On Stage control, hold **Hold to reset the demo**.

## Run of show

| Time | Say | Do | Judges see |
|---|---|---|---|
| 0:00–0:20 | "A pilgrim on the Kedarnath route. A landslide, no signal, no common language." | One photo on the projector. | The problem in one sentence. |
| 0:20–0:45 | "You're all on the trail now." | Judges scan the **Join** QR on `/stage` and join on `/j`. | Their own dots appear on the projector. |
| 0:45–1:05 | "A landslide has just closed this stretch." | Stage control: **Landslide here**. | Every phone in the zone goes full-screen red ("Landslide: route closed") with **Show safe way back**, in each judge's language. |
| 1:05–1:20 | "The lobby is getting crowded." | Stage control: **Crowd surge** (40 simulated people over 20 s). | The area turns red; phones heading in get the amber crowd warning. |
| 1:20–1:50 | "One of you is hurt and has no signal." | A judge turns on airplane mode, holds **SOS**, picks **Injured**, taps **Send SOS**, sees "Pending transmission", then turns airplane mode off. | The SOS pin drops on the projector with how long it waited. |
| 1:50–2:10 | "Three more of you press SOS." | 2–3 more judges send an SOS. | One incident card, not four: exact counts (computed by code) and a summary for the responder. |
| 2:10–2:25 | "Is everyone safe?" | Stage control: **Send "Are you safe?"** | Judges tap **I'm safe** or **I need help**; the tally updates live. |
| 2:25–2:40 | "The control room accepts." | The responder judge taps **Accept**, then **Verify timeline**. | The SOS judge's phone shows **Help acknowledged**; the timeline shows ✓ on every step. |
| 2:40–2:50 | "Your family sees only this." | A judge opens their family link (**Family** on the trip screen). | "On trip · last check-in …", never the location. |
| 2:50–3:00 | "Every AI call went through Prune. Here's the cost." | Responder → **AI & cost**: open a receipt and **Verify on Prune**; then open `/benchmark`. | Cost for this session, cost per trip vs naive, a verified signed receipt. |

Optional if there's time: Stage control → **Budget stress test**. Prune stops the AI with a 429, the card switches to standard text, and zone alerts and SOS keep working.

Optional Phase 2 teaser (30 s, if a judge asks about IDs): on a phone on the Sikkim route, **Pass → Link your permit → Foreign visitor → e-Visa** `EV2026IN0042137` → **Add to my pass**. Then on the responder, **Verify pass**, set "Checking entry to" to the road beyond Yumthang, and paste or scan the pass: "Not permitted for this area". Say: "Simulated registry. The full number is never stored and never reaches the AI."

Then **Break it**: switch the projector QR to **Break it** (`/break`). Judges try replaying an SOS, forging a pass, teleporting, injecting the AI, flooding SOS and more. Each attempt shows on the stage board as caught, flagged or slipped through.

## If something goes wrong

- **GPS is bad indoors:** leave "Place zones at my location" off so zones go around the judges; use **Walk simulation**; on a tourist phone use **Demo: tap the map to set your location** (in the trip screen's bottom sheet); or scan the door's checkpoint QR.
- **Venue Wi-Fi is bad:** put the laptop on the phone hotspot; phones use their own mobile data through the tunnel.
- **Prune is down or over budget:** cards show "Standard text". Say: "This is the safety rule working: the AI is never in the emergency path."
- **Responder screen shows "Reconnecting…":** it retries on its own; refresh if it takes more than a few seconds.
- **iPhone doesn't vibrate:** it uses sound and a full-screen flash instead; ask judges to turn the volume up.
- **Between rehearsals:** hold **Hold to reset the demo** on Stage control.

## Lines to remember

- "SafeTrail doesn't replace 112. It's the safety layer before it, for paise per trip."
- "Rules decide; the AI only writes and translates."
- "We never claim it works with no network: it warns you offline, keeps your SOS, and sends it on the first signal."
