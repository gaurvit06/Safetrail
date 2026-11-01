"""SafeTrail backend entry point: `uvicorn app.main:app --port 8000` from backend/."""
import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse

from . import events, stage
from .api import router
from .config import REPO_DIR, settings
from .db import engine, init_db
from .engines import start_engines
from .models import Trip
from .security import check_role_token, log_signer, pass_signer
from .seeddata import seed_db

logging.basicConfig(level=logging.INFO)
DIST = REPO_DIR / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    events.bind_loop(asyncio.get_running_loop())
    init_db()
    with Session(engine) as s:
        seed_db(s)
    pass_signer(), log_signer()  # create keys on first run
    with Session(engine) as s:
        stage.flag_csed(s, "auto")  # the demo starts with CSED already red, so nobody can forget to flag it
    tasks = start_engines()
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="SafeTrail", lifespan=lifespan)
origins = [o for o in [settings.frontend_origin, settings.public_url] if o]
app.add_middleware(CORSMiddleware, allow_origins=origins or ["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


def _audiences(token: str) -> tuple[set[str], dict]:
    role = check_role_token(token)
    if role == "presenter":
        return {"responder", "stage"}, {"role": role}
    if role == "responder":
        return {"responder", "stage"}, {"role": role}
    with Session(engine) as s:
        trip = s.exec(select(Trip).where(Trip.tourist_token == token)).first() if token else None
    if trip:
        return {"tourists", f"trip:{trip.id}"}, {"role": "tourist", "trip_id": trip.id}
    raise HTTPException(401, "A valid token is required for live updates")


@app.get("/api/events")
async def sse(request: Request, token: str = ""):
    audiences, who = _audiences(token)
    sub = events.subscribe(audiences)

    async def gen():
        try:
            yield {"data": json.dumps({"type": "hello", "data": who})}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    evt = await asyncio.wait_for(sub.queue.get(), timeout=15)
                    yield {"data": events.encode(evt)}
                except asyncio.TimeoutError:
                    yield {"comment": "keep-alive"}
        finally:
            events.unsubscribe(sub)

    return EventSourceResponse(gen())


@app.get("/api/events/poll")
def poll_events(after: int = -1, token: str = ""):
    audiences, _ = _audiences(token)
    return events.since(after, audiences)


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    """Serve the built app (frontend/dist) with SPA fallback, so everything is one origin behind one tunnel."""
    if path.startswith("api/"):
        raise HTTPException(404)
    if not DIST.exists():
        return {"message": "Backend is running. Build the app with `npm run build` in frontend/ to serve it here."}
    f = (DIST / path).resolve()
    if path and f.is_file() and DIST.resolve() in f.parents:
        return FileResponse(f)
    return FileResponse(DIST / "index.html")
