# SafeTrail: instructions for Claude

SafeTrail is our BIOS V2 hackathon app (Thapar Institute; Prune track "Ship It Lean: AI Apps on a Budget"): a safety companion for treks, pilgrimages and national parks. Tourist mode warns before danger and keeps an SOS when there's no signal; responder mode groups SOS into incidents; stage mode runs the live demo. Every LLM call goes through Prune, and **the AI is never in the emergency path**.

## Read first
1. `HANDOFF.md`: what's built, how to run, and the checklist. Continue from the first unchecked item.
2. `CONTINUE.md`: how we hand work between laptops and Claude sessions, and ready-made prompts.
3. `docs/SESSION_LOG.md`: what was built in the long Claude session of 31 Oct 2026 and why.
4. `SPEC.md` is the source of truth for behaviour; `docs/DECISIONS.md` records where we chose differently.

## Commands (macOS/Linux; Windows uses `backend\.venv\Scripts\python`)
- Run everything: `bash scripts/run_local.sh` → http://localhost:8000 (responder PIN 2468, presenter PIN 1357, from `.env`)
- Backend tests: `cd backend && .venv/bin/python -m pytest -q`
- Frontend tests and type check: `cd frontend && npm test && npm run build`
- Safety check before every commit: `bash scripts/check_no_direct_calls.sh`
- Prune hour-1 checks (needs keys in `.env`): `backend/.venv/bin/python scripts/prune_check.py`
- Benchmark R1–R4 (needs keys, costs credits): `backend/.venv/bin/python scripts/benchmark.py --trips 100`

## Rules (non-negotiable, from SPEC Section 1)
- Every LLM call goes only through `backend/app/ai/prune_client.py` to `PRUNE_BASE_URL` (https://api.withprune.com/v1). No provider URLs or AI SDK imports anywhere else; the checker enforces it.
- Zone alerts, crowd, SOS, grouping counts, check-ins, passes, the event log and the family link must work with no AI. Every AI feature has a template fallback labelled "Standard text".
- No personal data in prompts (names, phone, ID numbers). Never invent facts; validators check AI output.
- Never fake a number: costs come from Prune's stored data; unknown values show "n/a".
- Label everything simulated as "Simulated". Honest copy: "sends on first signal", "incident report draft", "flags impossible travel".
- Never commit `.env`, `backend/keys/`, `*.db` or raw receipts with personal data.
- Prune's cache stays `off` on live calls, even though SPEC says `exact`: `exact` returned one incident's summary for another (`docs/DECISIONS.md`, 28).

## How we work
- Small steps. After each working step: run the tests and the checker, update the checklist in `HANDOFF.md` (and `docs/DECISIONS.md` if you chose something), commit with a clear message, then `git push origin main`.
- If pushing is impossible (no GitHub access), make a bundle so the next laptop can pull it: `git bundle create safetrail-work.bundle main`.
- The team are beginners: explain what you did in plain words, and ask for anything only a human can give (Prune keys, model names, the venue map, phone tests).
