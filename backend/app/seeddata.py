"""Seed files (routes, facts, SOPs, templates) and idempotent DB seeding."""
import json
from functools import lru_cache

from sqlmodel import Session, select

from .config import SEED_DIR
from .geo import nearest_segment
from .models import Checkpoint, HelpPoint, Route, RouteFacts, Zone, ZoneAdvisory


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache
def route_seed(route_id: str) -> dict:
    return _read(SEED_DIR / "routes" / f"{route_id}.json")


@lru_cache
def route_facts(route_id: str) -> dict:
    return _read(SEED_DIR / "route_facts" / f"{route_id}.json")


@lru_cache
def sops() -> dict:
    return _read(SEED_DIR / "sops" / "sops.json")


@lru_cache
def templates(lang: str) -> dict:
    path = SEED_DIR / "templates" / f"{lang}.json"
    if not path.exists():
        path = SEED_DIR / "templates" / "en.json"
    return _read(path)


def route_ids() -> list[str]:
    return sorted(p.stem for p in (SEED_DIR / "routes").glob("*.json"))


def segment_for(route_id: str, lat: float, lon: float) -> tuple[dict | None, float]:
    seg, d = nearest_segment(lat, lon, route_seed(route_id).get("segments", []))
    if seg is None:
        return None, d
    facts = {x["id"]: x for x in route_facts(route_id).get("segments", [])}
    return {**seg, **facts.get(seg["id"], {})}, d


def _bbox(coords):
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return [min(lons), min(lats), max(lons), max(lats)]


def seed_db(s: Session) -> None:
    from .ai.templates import zone_text

    for rid in route_ids():
        r = route_seed(rid)
        facts = route_facts(rid)
        bbox = _bbox(r["line"])
        route = s.get(Route, rid) or Route(id=rid, name=r["name"])
        route.name, route.region = r["name"], r.get("region", "")
        route.line = {"type": "LineString", "coordinates": r["line"]}
        route.bbox = bbox
        route.center = [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
        route.facts_version = facts.get("version", 1)
        route.simulated = r.get("simulated", True)
        route.local_lang = r.get("local_lang", "hi")
        s.add(route)
        rf = s.get(RouteFacts, rid) or RouteFacts(route_id=rid)
        rf.version, rf.facts = facts.get("version", 1), facts
        s.add(rf)
        # Upsert from the seed files, so re-generated data (e.g. scripts/fetch_osm.py) replaces old rows.
        keep = {hp["id"] for hp in r.get("help_points", [])}
        for old in s.exec(select(HelpPoint).where(HelpPoint.route_id == rid)).all():
            if old.id not in keep:
                s.delete(old)
        for hp in r.get("help_points", []):
            obj = s.get(HelpPoint, hp["id"]) or HelpPoint(id=hp["id"], route_id=rid, kind=hp["kind"], name=hp["name"],
                                                          lat=hp["lat"], lon=hp["lon"])
            obj.kind, obj.name, obj.lat, obj.lon = hp["kind"], hp["name"], hp["lat"], hp["lon"]
            obj.simulated, obj.source = hp.get("simulated", True), hp.get("source", "seed")
            s.add(obj)
        keep = {cp["id"] for cp in r.get("checkpoints", [])}
        for old in s.exec(select(Checkpoint).where(Checkpoint.route_id == rid)).all():
            if old.id not in keep:
                s.delete(old)
        for cp in r.get("checkpoints", []):
            obj = s.get(Checkpoint, cp["id"]) or Checkpoint(**cp, route_id=rid)
            obj.name, obj.lat, obj.lon = cp["name"], cp["lat"], cp["lon"]
            s.add(obj)
        for z in r.get("zones", []):
            existing = s.get(Zone, z["id"])
            if existing:
                existing.polygon, existing.segment_name = z["polygon"], z.get("segment_name", "")
                existing.kind, existing.severity = z["kind"], z.get("severity", "danger")
                s.add(existing)
                for adv in s.exec(select(ZoneAdvisory).where(ZoneAdvisory.zone_id == z["id"],
                                                             ZoneAdvisory.source == "template")).all():
                    t = zone_text(adv.lang, z["kind"], z.get("segment_name", ""))
                    adv.title, adv.body, adv.action = t["title"], t["body"], t["action"]
                    s.add(adv)
                continue
            s.add(Zone(id=z["id"], route_id=rid, kind=z["kind"], severity=z.get("severity", "danger"),
                       polygon=z["polygon"], source="seeded", segment_name=z.get("segment_name", ""),
                       simulated=True, created_by="seed"))
            from .config import settings
            for lang in settings.advisory_langs:
                t = zone_text(lang, z["kind"], z.get("segment_name", ""))
                s.add(ZoneAdvisory(zone_id=z["id"], lang=lang, source="template", **t))
    s.commit()


def existing_zone_ids(s: Session) -> set[str]:
    return set(s.exec(select(Zone.id)).all())
