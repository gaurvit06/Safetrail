# Decisions

Deviations from SPEC.md and why. Newest last.

1. **Repo lives at a short path** (`C:\Users\gaurv\safetrail`). Windows' 260-character path limit broke Python DLL loading (and would break `node_modules`) inside the long scratch folder.
2. **Times are unix epoch seconds (float, UTC)** everywhere: database, API and events. Simpler than ISO strings and identical in Python and JavaScript.
3. **Pure-Python geometry** (`backend/app/geo.py`) instead of shapely, and **incremental clustering** (an SOS joins an open incident on the same route within `CLUSTER_EPS_M` and 30 minutes; nearby incidents merge) instead of scikit-learn DBSCAN. Same result as DBSCAN with `min_samples=2` for the small numbers here, and no heavy dependencies on Python 3.14.
4. **Advisory and template languages start with English and Hindi** (`ADVISORY_LANGS=en,hi`). More languages are a config change once their templates exist in `backend/seed/templates/`.
5. **The hall route coordinates are placeholders.** Stage scenarios ("Landslide here", "Crowd surge") place zones and simulated people around the judges' live positions, so the demo works anywhere. Replace `backend/seed/routes/hall.json` with the real venue when possible.
6. **SMS parsing (5.8.6) is deferred.** It's first in the cut order. Coded SMS can still be added later without AI.
7. **`.env` is read from the repo root**, then `backend/.env` (overrides), so `.env.example` sits at the root as in SPEC.md Section 11.
8. **Signing keys** are generated into `backend/keys/` on first run when `PASS_SIGNING_KEY` / `LOG_SIGNING_KEY` are empty. That folder is git-ignored.
9. **Map tiles are OpenStreetMap raster tiles** (CARTO basemaps now require an API key). Light use only, never bulk-prefetched; viewed tiles are cached by the service worker. Offline, the route, zones and help points still draw as GeoJSON on a plain background. The projector uses a dimmed copy.
10. **No shadcn/ui generator:** small Tailwind components in `frontend/src/components/ui.tsx` instead, to avoid a CLI step.
11. **Hold-to-SOS completes on a timer**, not on animation frames, so it can't get stuck when the browser throttles frames.
12. **`db.init_db()` adds missing columns** to an existing SQLite database (forward-only), so pulling an update never breaks a local database.
13. **Demo location mode** (tourist sheet → "Demo: tap the map") moves your dot by tapping the map, for rehearsals and indoor demos where GPS is poor. It's clearly labelled on screen.
14. **Weather only suggests zones.** The responder weather panel's "Draw a zone here" pre-fills the zone tool (custom kind, 250 m circle, 6 h expiry, the warning as the note). The officer reviews and publishes; weather never publishes a zone by itself.
15. **`prune_client.probe()`** makes the raw diagnostic calls for `scripts/prune_check.py` (no retry, no logging), so the OpenAI SDK stays in one module. Diagnostics log into a throwaway database and never count in cost per trip.
16. **Benchmark scenario uses the seeded routes only** (`kedarnath`, `hall`); `sikkim` and `park` from SPEC 10.1 aren't seeded yet. Notes are in English, Hindi and Assamese. Regenerate with `scripts/make_benchmark_scenario.py` (deterministic).
17. **Benchmark runs in its own database** (`backend/benchmark.db`), so demo screens never show benchmark trips. SOS are replayed through the real grouping code; cluster summaries follow the app's refresh limits in scenario time (one per `CLUSTER_SUMMARY_MIN_INTERVAL_S`, at most 3); R1 re-summarises after every SOS; copilot is one brief per incident. Each run tags its Prune run ids (`_b<run>`) so step and budget guards never carry over between runs.
18. **Benchmark overrides go through a context variable** (`ai/jobs.py::BENCH`: nonce, policy, cache, forced tier, naive = no governor and no run-budget header). The live app never sets it, so feature code has no benchmark branches.
19. **Cluster summaries now flag Prune injection signals** on the incident, the same way single reports already did, so a suspicious note inside a cluster is flagged too.
20. **The injection scanner is English pattern matching.** The benchmark shows it catches the English tricks and misses Hindi and Assamese ones; those rely on Prune's injection detection. Don't claim more than that.
