# SafeTrail pitch for two presenters

For the 6-slide deck (`docs/SafeTrail-Pitch-6-slides.pptx`). The main version is **5 minutes, then questions**. A 3-minute and an 8-minute version are in section 4. Every number here comes from `docs/BENCHMARK.md` or `docs/DECK_CREDITS.md`.

Before you rehearse, write your names in place of **A** and **B**, and add the team names to slide 1.

## 1. Who does what

| | **A · the traveller** | **B · the control room** |
|---|---|---|
| Slides | 1 Problem · 2 Tourist · 5 Permits · the closing line | 3 Responders · 4 AI safety pack · 6 How it's built and what it costs |
| Live demo | Holds the tourist phone (joined at `/j`) and shows it to the judges | Drives the laptop: responder page `/r` (PIN 2468) |
| Questions | People and use: no network, 112, privacy, permits, who pays | Tech: AI, Prune, cost, security, the stack |

- Run the demo from the laptop that has the Prune keys in `.env` (HANDOFF says that's Hardik's Mac). B sits there and changes the slides for both of you.
- Say the other person's name at every handoff. The handoff lines are in **bold** below.
- One voice at a time. Whoever isn't talking points at the screen or holds up the phone.

## 2. Ten minutes before

1. Start everything: `bash scripts/run_phones.sh`. It prints four links, which change every time. Keep that Terminal window open: closing it stops the app.
2. If an earlier round left things behind, tap **Next round** on Stage control (`/stage/control`, PIN 1357) **before** step 3, because it clears everything.
3. A's phone: open the `/j` link, allow location, join, tap **Alert sound tested** and **Location permission**, then **Open map**, and open **Safety pack** once. Volume up.
4. Laptop: the deck on slide 1, and `/r` logged in, in a browser window you can switch to in one move. It should show **1 on trail** and no red zone (if CSED is already red, click **Clear CSED red zone**). Tip: open the deck's PDF in a browser tab next to `/r`, so one Ctrl+Tab switches between them.
5. Optional: `/stage` on a second screen with the **Join** QR, for any judge who wants to try. Don't wait for them.
6. Practise switching A's phone to airplane mode and back. It's the riskiest 20 seconds of the demo.

## 3. The 5-minute pitch

At about 140 words a minute, each block fits its time if you don't rush.

### 0:00–0:40 · A · Slide 1 (the problem)

> "Hi, we're [team name]. I'm [A], and this is [B].
>
> A landslide on the Kedarnath trek. No signal, no common language, and a crowd building behind you. Staying safe depends on spotting the danger, having signal, and explaining where you are, and in the mountains all three fail at once.
>
> It isn't rare. Over 16.5 lakh pilgrims went to Kedarnath in 2025, and after the 2024 cloudburst more than 15,000 people were evacuated from this one trek. SafeTrail is built for that moment."

### 0:40–1:10 · A · Slide 2 (the tourist)

> "One app, two sides. For the traveller: you join by scanning a QR, no app store. On the trail, your phone checks where you are against the danger zones by itself, so you're warned before you walk in, even with no internet. If you're in trouble, hold SOS: three taps, no typing. It's saved on the phone and sends itself on the first signal.
>
> **Now the other side. [B]?**"

### 1:10–1:35 · B · Slide 3 (responders)

> "I'm the control room. When a landslide hits, I don't get 40 separate calls. SOS within 150 metres and 30 minutes become one incident, with exact counts, because code counts them, not the AI. The AI only writes the summary, through Prune. One tap on Accept, and every phone in that group sees that help is coming.
>
> **Let's show you, live.**"

B switches the laptop to `/r`.

### 1:35–3:30 · Live demo (both)

| # | Who | Do | Say |
|---|---|---|---|
| 1 | B | Click **Flag CSED red zone**. | "We're in the CSED block. I've just marked it a red zone: think of it as the landslide." |
| 2 | A | The phone goes full-screen red, **Red zone: do not enter**, with sound. Tap **Show safe way back**. | "My phone worked that out by itself. Once a zone is on the phone, the warning needs no signal. And it points me out." |
| 3 | A | Turn on airplane mode. Hold **SOS** for 2 seconds, then **Injured**, **2–5**, **Send SOS**. Show the screen: "Pending transmission". | "Now I'm hurt, and there's no signal. Three taps, no typing. It's saved with the time and place." |
| 4 | A | Turn airplane mode off. | "Signal's back." |
| 5 | B | Talk while the phone reconnects (5 to 20 seconds). | "That SOS waited in the phone's storage. It retries every 10 seconds, and if only SMS gets through, the phone offers a coded SMS instead." |
| 6 | B | The SOS appears. Open the incident card. | "There it is: where, how many, what happened. The counts come from code. If the AI is slow, the card says 'Standard text', and the counts don't wait for it." |
| 7 | B | Tap **Accept**. | |
| 8 | A | Hold up the phone: **Help acknowledged**. | "And now I know help is coming." |
| 9 | B | **Timeline** tab, then **Verify timeline**. | "Every step is hash-chained and signed. Change anything, and this check fails." |

- **No alert at step 2** (GPS is weak indoors): A pulls up the bottom sheet and taps **Simulate walking into CSED**. The dot walks in over about 17 seconds: an amber "m ahead" warning, then the full-screen alert. Say: "GPS is weak indoors, so I'm simulating the walk. The warning and the alert are the real ones."
- **A judge wants to try:** hand them A's phone for steps 3 and 4.
- **On a big stage** the projector can't show the phone, so A says what it shows and holds it up.
- **Running behind:** skip step 9.

B switches back to the deck, slide 4.

### 3:30–3:55 · B · Slide 4 (the AI safety pack)

> "The AI's main job happens before the trip. Prune's small model writes a safety pack for your route, in your language: the risks on each stretch, the nearest help point, altitude sickness signs, and phrases to show a local. Validators reject anything invented. It's made once per route and language, so the second pilgrim's pack costs nothing, and it opens offline.
>
> **[A]?**"

### 3:55–4:10 · A · Slide 5 (permits, Phase 2)

> "Next, for permit states like Sikkim: your pass links the e-Visa or inner-line permit you already hold, and checkpoints check it offline. Today that runs on a simulated registry.
>
> **[B], what does it cost?**"

If the clock is past 4:00 when slide 4 ends, B goes straight to slide 6, and A answers permits in questions.

### 4:10–4:50 · B · Slide 6 (how it's built, what it costs)

> "Everything that keeps you safe is plain code. The AI only writes and translates, and every call goes through Prune: budgets it enforces, injection checks, and a signed receipt for every call. We tested Prune's cache on real incident prompts and caught it giving one incident's summary to another, so we added a fingerprint, and now only identical requests can match.
>
> On 100 simulated trips: 82% fewer tokens per trip than the naive way, about 3 paise a trip at Google's list price, 72% of repeat-day calls from Prune's cache, and counts 100% correct.
>
> **[A]?**"

### 4:50–5:05 · A · Slide 6 (the close)

> "Who pays? State tourism departments, pilgrimage boards and park authorities, with a licence and a small fee per tourist. SafeTrail doesn't replace 112. It's the safety layer before it. Thank you. We'd love your questions."

Then stop talking, and leave slide 6 up.

## 4. A shorter or longer slot

**3 minutes**

| Time | Who | What |
|---|---|---|
| 0:00–0:40 | A | Slide 1 |
| 0:40–2:05 | Both | Demo steps 1 to 8. During step 5's wait, B says slide 3's line: "SOS within 150 metres and 30 minutes become one incident, with exact counts from code." |
| 2:05–2:45 | B | Slide 6 |
| 2:45–3:00 | A | The close |

Keep slides 2 to 5 for questions.

**8 minutes:** the 5-minute pitch, plus:

- At slide 2, show the **Join** QR from `/stage` and invite the judges to join. At demo step 1 their phones get the alert too, and two or more of them can send an SOS: it still shows as one incident.
- After step 9, open the **AI & cost** tab and one receipt. B: "Each AI call, its cost, and Prune's signed receipt."
- After slide 6, Stage control → **Budget stress test**. B: "Prune stops the AI at its budget, the card switches to standard text, and SOS still works."
- At slide 5, the permit demo from `docs/DEMO_SCRIPT.md` (e-Visa `EV2026IN0042137`, simulated registry).
- At the end, switch the `/stage` QR to **Break it** and invite the judges to try to fool the app.

## 5. If something goes wrong

| What | Who | Do and say |
|---|---|---|
| A card says "Standard text" | B | "That's our safety rule working: the AI is never in the emergency path." Carry on. |
| No alert indoors | A | **Simulate walking into CSED**, and say it's simulated. |
| The SOS hasn't arrived 30 seconds after airplane mode | B | Move on to slide 4. It will still arrive; point at it when it does. |
| The link stops working | B | Don't restart it during the pitch. Play `docs/SafeTrail-Backup-Walkthrough.mp4` (75 seconds) and talk over it. Say it's a walkthrough of the real app on emulated phones. |
| An iPhone doesn't vibrate | A | It uses sound and the full-screen red instead. Volume up. |
| A judge asks something mid-demo | Whoever owns the topic | One sentence, then "we'll come back to that", and carry on. |

## 6. Questions: who answers

The owner answers in one or two sentences. The other person adds one sentence, only if something important was missed. If neither of you knows: "We haven't measured that yet." Never guess a number. More answers are in `docs/PRESENTATION.md` section 6.

**A answers**

1. *Explain it in one sentence.* "An offline-first safety app for treks, pilgrimages and parks: it warns before danger, keeps your SOS when there's no signal, and gives responders one clear picture."
2. *What if there's no network at all?* "Nothing can send with zero network, not us and not 112. So we warn before people reach danger, keep the SOS and send it on the first signal, by SMS if data is down or at a checkpoint, and the control room sees who has gone quiet and where they were last seen."
3. *Why not just call 112?* "If you have signal, call 112, and the app tells you to. We add what a call can't: a warning before the danger, an SOS that waits, no need to speak the language, and 40 calls grouped into one incident."
4. *Will pilgrims install an app?* "No install. They scan a QR at registration or a checkpoint. It's a web app that saves itself on the phone and then works offline."
5. *What about privacy?* "Your family sees your status, never your location. No names or phone numbers go into AI prompts. Permit numbers are hashed at once, and only the last 4 characters are kept."
6. *Is the tourist ID real?* "It's Phase 2, built on a simulated registry with fake numbers. It links the e-Visa, e-ILP or yatra registration you already hold. Aadhaar is optional, last 4 digits only."
7. *Who pays?* "State tourism departments, pilgrimage boards and park authorities: a licence and a small fee per tourist. The AI costs about 3 paise a trip at Google's list price, so it doesn't eat the fee."
8. *Have you tested it in the field?* Say only what you've done. If you haven't tested on real phones at the venue yet: "We tested the full demo in real browsers with emulated phones, through a real public link, on the real OpenStreetMap trail. A test with real phones in the field is next."
9. *Where do the danger zones come from?* "Officers mark them on the map, or with one tap like you saw. Crowd zones come from how many people are in each spot, and weather warnings come from live Open-Meteo data for each section."

**B answers**

10. *Why do you need AI at all?* "For language work: the safety pack for each route and language, warnings in each language, translating SOS notes, and summarising a group. Every safety decision is plain code."
11. *Why Prune and not a direct API?* "One gateway for every call: budgets and step limits it enforces, an exact cache, injection checks, and signed receipts so we can prove cost. Our checker fails the build if any code calls an AI directly."
12. *What if Prune or the AI is down?* "Cards show our standard text. Alerts, SOS, grouping and the timeline keep working. You may see it today, because our free Gemini key is sometimes busy."
13. *Isn't a cache dangerous in an emergency app?* "Yes, so we tested it. Exact mode alone gave one incident's summary to another. Now every call sends a fingerprint of the request and a strict setting. All six changes in our test got their own answer, and a live check fails if that ever changes."
14. *How did you measure cost?* "Four setups on the same 100 simulated trips. We priced Google's own token counts at Google's list price, because Prune's Gemini cost figure leaves out output tokens. The naive run hit our free key's limits, so it's a low estimate, and the real saving is bigger."
15. *Does Prune pick cheaper models for you?* "Not in our run: it rerouted nothing, so we don't claim that. We use the small model by default and move up to the large one only when the small one's answer fails our checks."
16. *How do you stop the AI inventing things?* "Validators reject any number, phone number, injury or SOP step that isn't in the input. Then one repair, then the larger model, then our standard text."
17. *What about prompt injection in SOS notes?* "Notes go in marked as untrusted text. Our scanner catches English tricks, and Prune's detector is a second check. An SOS is never blocked; the officer just sees a flag."
18. *What about fake SOS or GPS spoofing?* "We flag impossible travel, like jumping 5 km in 2 minutes, and floods of SOS from one phone. We flag, never block, and judges can try it in our Break-it round."
19. *What's the stack?* "An installable web app in React and TypeScript, with an offline SOS queue and MapLibre on OpenStreetMap. A FastAPI and SQLite server with live updates. Signed passes and a signed, hash-chained log. Gemini 3.1 Flash-Lite and 3.5 Flash, through Prune."
20. *Is it blockchain?* "No. It's a hash-chained log signed with Ed25519: you can tell if anything was changed, without the cost of a blockchain."
21. *What does a signed receipt prove?* "Prune signs each call's record. We checked one on withprune.com/verify and got 'Signature valid', and a changed copy fails our own check."

## 7. Numbers: say them exactly like this

| Say | Where it's from |
|---|---|
| "Over 16.5 lakh pilgrims went to Kedarnath in 2025" (counted by early October) | ETV Bharat and Organiser, Oct 2025 (`docs/DECK_CREDITS.md`) |
| "More than 15,000 evacuated from the Kedarnath trek after the July 2024 cloudburst" | Deccan Herald and All India Radio, Aug 2024 |
| "Up to 3,000 stranded at Lachen and Lachung in October 2023" | Telangana Today (ANI), Oct 2023 |
| "82% fewer tokens per trip than the naive way" (at least: the naive run is a low estimate) | `docs/BENCHMARK.md`, 100 simulated trips |
| "About 3 paise per monitored trip and about 10 paise per emergency, at Google's list price" (what a paid key would cost; the demo runs on a free key, so it isn't a bill) | `docs/BENCHMARK.md` |
| "72% of repeat-day calls served from Prune's cache" | `docs/BENCHMARK.md`, run R4 |
| "Counts 100% correct, because code computes them" | `docs/BENCHMARK.md` |
| "The Kedarnath trail in the app is the real OpenStreetMap path, 15.1 km" | `backend/seed/route_facts/kedarnath.json` |
| "Our Prune check passes 10 of 11 live checks" (the 11th is a dashboard setting the app enforces itself) | HANDOFF, last run on Hardik's Mac |
| "85 backend tests and 6 app tests pass" | run on 1 Nov |

## 8. Don't say

- "Works with no network", "guaranteed rescue", "predicts stampedes", "catches all GPS spoofing", "integrated with government permits".
- "Prune picks the cheapest model for us": it rerouted nothing in our run.
- Prune's own dollar or paise figures (they leave out output tokens), or the naive run's cost per emergency (not comparable).
- "Tested in the mountains" or "tested on real phones", unless you have.
- "DBSCAN" on its own: say "like DBSCAN: SOS within 150 metres and 30 minutes form one incident".
- PostgreSQL, PostGIS, React Native or WebSockets: we use SQLite, an installable web app and live event streams.

## 9. Rehearse twice, with a timer

- Run the whole 5 minutes twice. Where you run over, cut words, not the demo.
- Swap roles once, so either of you can carry on alone if the other is stuck on the demo.
- Agree a silent signal, like a tap on the table, for "skip to slide 6".
- Each of you says the 30-second version aloud, without notes:

> "SafeTrail is a safety app for treks, pilgrimages and parks. It warns you before you walk into danger, even with no internet. If you're hurt, your SOS is saved and sends itself on the first signal. The control room sees one clear incident instead of 40 calls. The AI writes the safety pack, translations and summaries, through Prune, for about 3 paise a trip, and it's never in the emergency path."
