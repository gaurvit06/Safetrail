# How to continue SafeTrail (any laptop, any Claude)

Everything needed lives in this repository: the code, `HANDOFF.md` (checklist), `CLAUDE.md` (rules Claude reads automatically), `docs/SESSION_LOG.md` (what was done and why) and the prompts below. No chat history is needed.

## Step 0 (once): put the latest work on GitHub
The cloud Claude session of 31 Oct couldn't push to `gaurvit06/Safetrail`, so its commits came as a file, `safetrail-work.bundle`. On a Mac that has the bundle in Downloads:

```bash
cd ~/safetrail && git pull --no-rebase --no-edit ~/Downloads/safetrail-work.bundle main && git push origin main
```

If git asks for a password: GitHub needs a token. Install GitHub CLI (`brew install gh`), run `gh auth login`, then push again. After this, GitHub `main` is the source of truth and the bundle is no longer needed.

## A. Continue on your own desktop (Claude Code on the Mac)
1. Get the code (skip if `~/safetrail` exists): `git clone https://github.com/gaurvit06/Safetrail.git ~/safetrail`, then `cd ~/safetrail && git pull`.
2. Run the app once: `bash ~/safetrail/scripts/run_local.sh` (opens http://localhost:8000; stop with Ctrl+C).
3. Open Claude Code **in the `~/safetrail` folder**: in the Claude desktop app open Claude Code and pick that folder, or in Terminal run `cd ~/safetrail && claude`.
4. Paste **Prompt 1** below.

## B. Continue in another Claude when credits run out (from GitHub)
- **Claude Code on the web / another account:** start a session on the repository `gaurvit06/Safetrail`. That account needs GitHub access to the repo; the owner (gaurvit06) can install the Claude GitHub App on it at https://github.com/apps/claude/installations/select_target so the session can also push. Paste **Prompt 2**.
- **Another laptop (for example Gaurvit's):** `git clone https://github.com/gaurvit06/Safetrail.git` into a short path (Windows: `C:\Users\<you>\safetrail`), run the app (Mac/Linux: `bash scripts/run_local.sh`; Windows: "Run it" in README.md), open Claude Code in that folder, paste **Prompt 2**.

## Prompts (copy the text inside each box)

### Prompt 1: resume on my desktop
```
You're continuing SafeTrail, our BIOS V2 hackathon app for the Prune track. Read CLAUDE.md, HANDOFF.md, CONTINUE.md and docs/SESSION_LOG.md first (SPEC.md for detail). Run `git status` and `git log --oneline -15`, then the backend tests, the frontend tests and scripts/check_no_direct_calls.sh, and tell me in 5 short lines where the project stands. Then continue from the first unchecked item in HANDOFF.md. Ask me for anything only I can give (Prune keys, model names, the venue map, phone tests). After every working step: run the tests and the checker, update HANDOFF.md, commit, and push to origin main. Explain what you did in simple words.
```

### Prompt 2: resume from GitHub in another Claude
```
You're picking up SafeTrail, a hackathon app (BIOS V2, Prune track), from another Claude session. The repository gaurvit06/Safetrail is the source of truth. Pull the latest main (clone it into a short path if it isn't here). Read CLAUDE.md, HANDOFF.md, CONTINUE.md and docs/SESSION_LOG.md completely, then SPEC.md where you need detail. Don't redo finished work. Check that the latest commits include "Projector live counter, confetti on Accept, one-tap Next round" and "Add scripts/run_local.sh"; if they don't, the newest work is still in a git bundle: ask me for it (CONTINUE.md, Step 0). Run the tests and scripts/check_no_direct_calls.sh, summarise the state in 5 lines, then continue from the first unchecked item in HANDOFF.md. After every working step: tests, update HANDOFF.md, commit, push to main (if you can't push, make a bundle as CLAUDE.md says and tell me).
```

### Prompt 3: switch the AI on (after putting keys in `.env`)
```
I've added PRUNE_API_KEY, PRUNE_PUBLIC_API_KEY, MODEL_SMALL and MODEL_LARGE to .env (PRUNE_BASE_URL is https://api.withprune.com/v1). Run scripts/prune_check.py, read docs/PRUNE_FIELDS.md, and fix any field name it reports as missing in backend/app/ai/prune_client.py::_extract. Rerun the tests and the check. Then walk me through verifying one signed receipt on withprune.com/verify and saving a screenshot to docs/receipts/. Update HANDOFF.md, commit and push. Never print or commit the keys.
```

### Prompt 4: run the benchmark for the cost slide
```
Help me run the SafeTrail benchmark (SPEC 10.3). First tell me roughly how many AI calls R1–R4 will make with --trips 100 and remind me to raise the Prune ops key's daily cap. When I say go, run `backend/.venv/bin/python scripts/benchmark.py --trips 100 --yes`. Then explain docs/BENCHMARK.md in plain words for our cost slide: cost per trip and per emergency in paise, and what SafeTrail's design, Prune routing and Prune's cache each saved. Commit docs/BENCHMARK.md and docs/benchmark_results.json and push. Remind me to lower the cap again.
```

### Prompt 5: use the real venue map
```
Here is our venue route drawn on geojson.io: <paste the GeoJSON>. Replace backend/seed/routes/hall.json with it, keeping the same schema (line, one segment named "Hall demo loop", help points, checkpoints); add a help desk and two door checkpoints where I tell you; update backend/seed/route_facts/hall.json if needed; make sure the "Landslide here" demo zone (DEMO_ZONE_RADIUS_M) covers the whole hall. Run the tests, commit and push.
```

### Prompt 6: phone test and rehearsal
```
Help me test SafeTrail on real phones and rehearse docs/DEMO_SCRIPT.md. Start the app, start a tunnel (cloudflared tunnel --url http://localhost:8000), put the https URL in PUBLIC_URL in .env and restart. Then give me a short checklist for 3+ phones (Android and iPhone): join by QR, zone alert, crowd, airplane-mode SOS, grouping, "Are you safe?", Accept with confetti, family link, Next round. After the test I'll tell you what broke; fix it, run the tests, commit and push.
```

## Good to know
- PINs: responder **2468**, presenter **1357** (`.env`: RESPONDER_PIN, PRESENTER_PIN).
- Prune base URL: **https://api.withprune.com/v1** (already the default). Keys go only in `.env`, which is never committed.
- Safari phone view: Develop → Enter Responsive Design Mode (⌥⌘R). Chrome: ⌥⌘I, then ⇧⌘M.
- Demo permit numbers for Phase 2 (all fake) are in README.md.
