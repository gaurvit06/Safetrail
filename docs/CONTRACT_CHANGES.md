# Contract changes

Differences from SPEC.md Sections 6–8 that the app must follow. Newest last.

1. **Timestamps** are unix epoch seconds (float) in every API response and event.
2. **Auth:** REST calls send `Authorization: Bearer <token>`. The event stream can't send headers, so it uses `GET /api/events?token=<token>`. A tourist token only receives its own trip's events plus broadcast events (zones, crowd, checks).
3. **`POST /api/trips`** returns `{trip, pass_qr, tourist_token, family_url}`. `trip` never includes phone numbers or the emergency contact.
4. **Zone objects:** `{id, route_id, kind, severity, polygon, source, note, segment_name, simulated, active, created_at, expires_at, advisories: {<lang>: {title, body, action, source}}}`. `polygon` is a GeoJSON Polygon geometry.
5. **Extra event `crowd.warn`** (sent to one trip): `{zone_id, people, wait_min, alt_name, message: {<lang>: text}}`, for a tourist heading toward a red crowd zone.
6. **Incident counts:** `people_total` is the sum of each trip's latest people bucket (1 → 1, 2–5 → 3, 6+ → 8), with the split in `people_breakdown`. `injured_total` counts *reports* of kind injured or medical, so the UI says "3 injured reports".
7. **Pass QR format:** `base64url(payload).base64url(signature)`. The payload is canonical JSON (sorted keys, no spaces). The server's public key (base64, raw Ed25519) is in the trip start bundle as `server_pubkey`.
8. **Timeline verification:** each log entry has `hash`, `prev_hash`, `payload_hash`, `signature` (hex). The app checks each entry's hash, `sha256(prev_hash|type|entity_id|payload_hash|ts_server)` with `ts_server.toFixed(6)`, and its Ed25519 signature with the log key. `GET /api/log/verify` also returns the server's full-chain check.
