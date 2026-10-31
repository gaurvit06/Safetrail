"""Load clearly labelled demo data into a running backend, so every screen has something to show.

    python scripts/seed_demo.py [base_url] [--reset]

Then open /r (pick "Gaurikund → Kedarnath") or /stage?route=kedarnath.
Uses the presenter PIN from PRESENTER_PIN (default 1357).
"""
import json
import os
import sys
import urllib.request

args = [a for a in sys.argv[1:] if not a.startswith("--")]
# 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and waits ~2 s per request.
BASE = (args[0] if args else "http://127.0.0.1:8000").rstrip("/") + "/api"


def call(path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"null")


def main():
    token = call("/auth/login", {"role": "presenter", "pin": os.getenv("PRESENTER_PIN", "1357")})["token"]
    if "--reset" in sys.argv:
        print("reset:", call("/stage/scenario", {"action": "reset"}, token))
    r = call("/stage/scenario", {"action": "demo_data", "route_id": "kedarnath"}, token)
    print(r.get("message", r))
    site = BASE[:-4]
    print(f"\nResponder:  {site}/r   (choose 'Gaurikund -> Kedarnath')")
    print(f"Projector:  {site}/stage?route=kedarnath")


if __name__ == "__main__":
    main()
