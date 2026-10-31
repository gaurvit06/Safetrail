"""End-to-end smoke test against a running backend: python scripts/smoke_test.py [base_url]

Creates a judge trip, starts it, sends pings, places a landslide zone over it, sends an SOS from two people,
checks the incident, accepts it, and verifies the timeline. Uses only the public API.
"""
import json
import sys
import time
import urllib.request
import uuid

# 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and waits ~2 s per request.
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/") + "/api"


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def main():
    print("health", call("GET", "/health"))
    presenter = call("POST", "/auth/login", {"role": "presenter", "pin": "1357"})["token"]
    hall = call("GET", "/routes/hall")
    lat, lon = hall["center"][1], hall["center"][0]
    trips = []
    for name in ("Judge-A", "Judge-B"):
        t = call("POST", "/join", {"name": name})
        call("POST", f"/trips/{t['trip']['id']}/start", {}, t["tourist_token"])
        call("POST", f"/trips/{t['trip']['id']}/pings", [{"lat": lat, "lon": lon, "accuracy_m": 10,
                                                          "ts_device": time.time()}], t["tourist_token"])
        trips.append(t)
    z = call("POST", "/stage/scenario", {"action": "landslide"}, presenter)
    print("zone", z["zone"]["id"], z["zone"]["advisories"].get("en", {}).get("title"))
    for i, t in enumerate(trips):
        r = call("POST", "/sos", {"client_id": uuid.uuid4().hex, "trip_id": t["trip"]["id"], "kind": "injured" if i == 0 else "stuck",
                                  "people_bucket": "2-5", "lat": lat + i * 0.0001, "lon": lon,
                                  "created_at_device": time.time() - 90}, t["tourist_token"])
        print("sos", r)
    inc_id = r["incident_id"]
    detail = call("GET", f"/incidents/{inc_id}", token=presenter)
    print("incident", detail["type"], detail["people_total"], detail["injured_total"], detail["priority"], detail["headline"])
    print("accept", call("POST", f"/incidents/{inc_id}/status", {"status": "accepted"}, presenter)["status"])
    chk = call("POST", "/stage/scenario", {"action": "safety_check"}, presenter)
    print("check", chk)
    tl = call("GET", f"/incidents/{inc_id}/timeline", token=presenter)
    print("timeline", len(tl["entries"]), tl["entries_check"], tl["chain_check"])
    print("family", call("GET", f"/family/{trips[0]['family_token']}"))
    print("stats", {k: v for k, v in call("GET", "/ai/stats", token=presenter).items() if k != "by_feature"})
    print("breakit", call("POST", "/breakit/attempts", {"nickname": "smoke", "consent": True, "trick": "forged_pass"}))


if __name__ == "__main__":
    main()
