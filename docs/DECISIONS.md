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
