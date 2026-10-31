You are an expert pitch-deck designer. Build a presentation for our hackathon project, SafeTrail.

Use only the facts in this brief. If you need something that isn't here, add a clearly marked placeholder such as [TO FILL: ...]. Never invent a number, a user, a partner or a result. Judges can check our claims live.

# What to give me

- A 16:9 PowerPoint file (.pptx) with the 10 main slides and 3 backup slides below, with speaker notes on every slide.
- If you can't create a .pptx file, write out every slide (title, on-slide text, a description of the visual, speaker notes) so I can paste it into Google Slides, Canva or Gamma.
- End with a checklist of every placeholder I still have to fill in.

# The event

- BIOS V2 hackathon, Thapar Institute, Patiala. Prune challenge: "Ship It Lean: AI Apps on a Budget".
- The brief: build a useful AI app, route every LLM call through Prune with one base URL, keep costs low, keep provider keys out of code, and stop failures from running up the bill.
- We must submit: a working demo, cost per task, and Prune's signed receipts.
- Judging: Usefulness 40%, Cost efficiency 30%, Reliability and safety 20%, Demo 10%. Spend the deck's attention in roughly that proportion.
- The talk is a 90-second pitch around a 3-minute live demo where judges use their own phones. The deck frames the demo, so keep it light.
- Team: [TO FILL: team name] and [TO FILL: member names].
- Code: github.com/gaurvit06/Safetrail

# The project

- Name: SafeTrail
- Tagline: Warn early. Never lose an SOS. Prove every response.
- One line: SafeTrail warns tourists before danger, keeps their SOS safe when there's no signal, and gives responders one clear picture instead of 40 confused calls. Every AI call goes through Prune, and the AI is never in the emergency path.
- For: treks, pilgrimages and national parks. The main route is the Kedarnath trek. The live demo runs on a short loop around the CSED block at Thapar, which stands in for a mountain route.
- Format: one installable web app (a PWA) with a tourist mode and a responder mode, plus a projector view for the live demo.

# Slide plan

Write each title as a full sentence that makes the point. These are suggestions, so improve the wording but keep the meaning.

1. **Title.** SafeTrail, the tagline, the event and the team.

2. **Three things fail at the same moment.** Open with the real event: in October 2023 a glacial lake burst in North Sikkim, floods cut off the roads to Lachen and Lachung, and thousands of tourists were stranded. Every season, pilgrims on the Kedarnath route face landslides and crushing crowds. Then the three failures: nobody warns you, there's no signal, and you don't share a language with the people who can help. Responders get late, vague, duplicate calls.

3. **One app for the tourist and the responder.**
   - Tourist: danger zone and crowd warnings, an offline safety pack, one-hold SOS, an "Are you safe?" check-in, a family link, a signed pass.
   - Responder: a live map, drawing a danger zone, grouped incidents with exact counts, reports in their language, next-step suggestions, Accept.

4. **From danger to proof in five steps.** Show this as a flow:
   - Warn: the phone holds the danger zones and alerts you before you walk in, even offline.
   - Save: SOS is saved on the phone at once and sent on the first signal, by SMS if data is down.
   - Group: SOS alerts within 150 m and 30 minutes become one incident, with counts computed by plain code.
   - Accept: the officer accepts and the tourist sees "Help acknowledged".
   - Prove: every step goes into a signed, hash-chained log, so changing one line breaks it.

5. **The AI is never in the emergency path.** This is the most important idea in the deck. Use two columns:
   - Plain code, works with the AI off: zone alerts, crowd detection, SOS saving and sending, grouping and counts, check-ins, pass checks, the signed log, the family link.
   - AI writes and translates only: safety packs, zone warnings, incident reports, group summaries, responder next steps, SMS details, permit cards.
   - Underneath: "Rules decide. The AI only writes and translates. If it's slow, down or over budget, standard text shows instead, and that text appears first anyway."

6. **Every AI call goes through one gate.** Draw this flow with native shapes: Tourist phone (zones, SOS queue, pass, works offline) to SafeTrail server (rules, grouping, signed log) to Responder app. A dotted line runs from the server to the Prune gateway (budgets, injection check, signed receipts, exact cache) and on to a small model and a large model. Caption: "Dotted lines are the AI. Everything on the solid lines works without it." One module makes all AI calls, a checker fails the build if any code calls a provider directly, and keys never reach the browser.

7. **We spend AI only where words are needed.** Cost efficiency is 30% of the score. Our design choices:
   - Plain code does everything safety-critical, so those parts cost nothing in AI.
   - One safety pack per route, language and traveller type is shared by every tourist, not written per person.
   - Each AI job runs once and is saved, so repeat work isn't paid for twice.
   - Prune's exact cache reuses a truly identical request.
   - The small model does most jobs. The large model is kept for group summaries and hard cases.
   - An SOS flood never fans out into AI calls, and group summaries have a refresh limit.
   - Three budget layers: our own check before each call, Prune's budget and step limit on each job, and a daily spend cap on each key.
   - Show four big figures: about 3 paise per monitored trip, about 10 paise per emergency, 82% fewer tokens per trip than the naive way, and 72% of repeat-day calls served from cache.
   - Add a chart of tokens per monitored trip: naive 1,997 (a low estimate), SafeTrail design 369, SafeTrail with Prune first day 403, repeat day 0.
   - Small print: "100 simulated trips on the small model. Cost is Google's token counts times Google's list price. The live demo runs on a free key."

8. **Built to fail safely, and tested against the real thing.**
   - Validators reject AI answers with invented numbers or places, ask once more, then fall back to standard text.
   - No names, phone numbers or ID numbers go into a prompt.
   - An English prompt-injection attempt in an SOS note becomes a flag on the incident, and the SOS is never blocked. If asked: 2 of our 4 test notes were flagged, the English ones.
   - A run over its budget is stopped by Prune and the app carries on with standard text. We confirmed this live.
   - We checked a real Prune receipt against Prune's published public key: the signature was valid, and a tampered copy was rejected.
   - The strongest moment: live testing found a similar-looking emergency could get another incident's cached summary, with the wrong people and place. We now add a fingerprint of each request, so only identical requests match. We retested on real prompts by changing the count, place, time, emergency type and note, and each one got its own correct answer.
   - Present this as what we learned from testing with real prompts, not as a criticism of Prune.

9. **You're on the trail now.** The live demo slide. Show a large [TO FILL: Join QR code]. List the order: join, zone alert, crowd warning, offline SOS, one grouped incident, "Are you safe?", Accept, family link, signed receipt. Small print: "Demo zones and dispatches are simulated."

10. **The safety layer before 112.** Close with: "SafeTrail doesn't replace 112. It's the safety layer before it." Then what's next:
   - Phase 2, Digital Tourist ID: the pass links to the permit a traveller already holds. It's built with a simulated registry today.
   - Where it starts: routes that already need registration or permits, such as Kedarnath and the Char Dham yatra, the North East permit states, and national parks.
   - Possible model: a state or park licenses it, with a small fee per tourist.

**Backup 1, Questions judges will ask:**
- Why not just call 112? We warn before it happens, work across languages, keep the SOS when there's no signal, and give responders one grouped picture. We work alongside 112.
- Does it work with no network? Warnings, the pack and saving the SOS work offline. Sending needs some signal: data, SMS or a checkpoint.
- Is the AI deciding emergencies? No. Rules set priority and plain code counts people.
- Isn't this surveillance? It's opt-in per trip with a Stop button, location history is deleted after 7 days, and family see status only.
- Can GPS be faked? We flag impossible travel, replays and forged passes. We don't claim to stop all spoofing.

**Backup 2, What's real and what's simulated:**
- Real: the working app, the Kedarnath trail from OpenStreetMap (15.1 km), live weather from Open-Meteo, live AI through Prune using Gemini models, and signed receipts.
- Simulated and labelled: demo zones and dispatches, the permit registry (fake numbers), the help desk, lobby and door positions on the CSED block route, and the Sikkim and Corbett routes, which are approximate and not for navigation.
- Not built on purpose: real 112 integration (it needs official authorisation), real permit APIs, face recognition, satellite SOS, and a chatbot.

**Backup 3, Cost benchmark:** this table, from the same simulated scenario run four ways (100 trips, 9 emergencies):

| Run | Tokens per trip | Paise per trip | Paise per emergency | Calls to Google | From cache | Standard text |
|---|---|---|---|---|---|---|
| Naive (a low estimate) | 1,997 | 15.9 | n/a | 124 | 0% | 41 of 161 |
| SafeTrail design | 369 | 2.9 | 9.6 | 56 | 0% | 0 of 56 |
| SafeTrail + Prune, first day | 403 | 3.1 | 10.0 | 57 | 1.7% | 0 of 56 |
| SafeTrail + Prune, repeat day | 0 | 0 | 6.3 | 16 | 72.4% | 0 of 56 |

Underneath: cost is Google's token counts times its list price ($0.25 in, $1.50 out per million tokens, ₹88 to the dollar). Every run used the small model, because the free key ran out of large model quota. Google's limits stopped 41 of the naive run's jobs, so its true use is higher and its emergency cost isn't comparable. Prune rerouted no calls. Counts were 100% correct in all four runs.

# Rules you must not break

- Use only the cost figures in this brief. They come from Google's token counts at Google's list price, on 100 simulated trips, so never present them as real-world use. Never use Prune's reported dollar or paise figures, because they leave out output tokens.
- Don't claim pilots, users, downloads, field trials, government partners or real 112 integration. Don't add market sizes or statistics.
- The only real-world event you may cite is the October 2023 North Sikkim flood described above.
- Don't say it "works with no network". Say it "warns you offline, keeps your SOS, and sends it on the first signal".
- Call the report an "incident report draft", never an FIR.
- Say we "flag impossible travel", never that we "stop GPS spoofing".
- Don't say Prune picks the cheapest model for us or show routing savings: no call in our tests was rerouted. Using the small model first is our own design.
- Languages: English and Hindi are built and tested. Assamese notes are translated for responders. Nepali is partial and machine-translated. Don't claim more.
- There is no chatbot, so never show a chat window.
- Don't call the signed log a blockchain.

# Design

- 16:9, clean and calm: this is about safety, so no stock mountain clip art, gradients or decorative icons.
- Colours from the app: background #F6F5F1, text #1B1D1F, muted text #5F6368, brand teal #0F766E, danger red #D93025, caution amber #D97706, safe green #1E8E3E, info blue #1A73E8.
- Font: Inter, or a similar clean sans-serif.
- One idea per slide and under 30 words of body text where you can. The title carries the message.
- Build diagrams from native, editable shapes rather than images.
- Use red only for danger and green only for safe.
- For app visuals, use the screenshots I attach. If I attach none, add a labelled box such as [Screenshot: phone showing the landslide alert] or [Screenshot: responder map with one grouped incident].

# Speaker notes

Write plain, spoken English: short sentences that are easy to say aloud. Use one to three sentences per slide. Keep slides 1 to 8 to about 90 seconds in total, and put the demo's running order in the notes for slide 9. End on: "SafeTrail doesn't replace 112. It's the safety layer before it."
