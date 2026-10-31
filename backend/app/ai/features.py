"""The five AI features (SPEC 5.8.1-5.8.5). Each one: build cacheable messages -> run_job (Prune, validators,
budgets, repair, escalation) -> store the result -> publish an event. Templates are always the fallback."""
import time

from sqlmodel import Session, select

from .. import events
from ..config import JOB_CFG, settings
from ..db import engine
from ..geo import haversine_m
from ..models import HelpPoint, Incident, SafetyPack, SosEvent, Trip, Zone, ZoneAdvisory
from ..seeddata import route_facts, route_seed, sops
from . import prompts, validators
from .jobs import run_job, spawn_later
from .templates import cluster_template, copilot_template, pack_template, permit_template, report_template, sms_template, zone_text

PEOPLE_MID = {"1": 1, "2-5": 3, "6+": 8}
_refresh_due: set[int] = set()  # cluster incidents with an AI summary refresh already scheduled


# ---------------------------------------------------------------- 5.8.1 safety pack

def pack_job_key(route_id: str, lang: str, bucket: str, suffix: str = "") -> str:
    return f"pack_{route_id}_{lang}_{bucket}_v{route_facts(route_id).get('version', 1)}{suffix}"


async def build_pack(route_id: str, lang: str, bucket: str, *, nonce: str = "", suffix: str = "",
                     policy: str | None = None, cache: str | None = None, benchmark_run_id: int | None = None,
                     key: str = "ops", extra_profile: str | None = None) -> dict:
    facts = route_facts(route_id)
    job_key = pack_job_key(route_id, lang, bucket, suffix)
    profile = bucket if extra_profile is None else f"{bucket}; {extra_profile}"
    res = await run_job(job_key=job_key, feature="pack", route_id=route_id, run_id=job_key,
                        messages=prompts.pack_messages(facts, lang, route_seed(route_id).get("local_lang", "hi"),
                                                       profile, nonce),
                        validate=lambda out: validators.validate_pack(out, facts),
                        template=lambda: pack_template(route_id, lang, bucket), policy=policy, cache=cache,
                        benchmark_run_id=benchmark_run_id, key=key)
    if benchmark_run_id is None:
        with Session(engine) as s:
            row = s.exec(select(SafetyPack).where(SafetyPack.job_key == job_key)).first() or SafetyPack(
                job_key=job_key, route_id=route_id, lang=lang, profile_bucket=bucket,
                facts_version=facts.get("version", 1))
            if res.source == "ai" or row.source != "ai":
                row.content, row.source, row.llm_call_ids, row.created_at = res.output, res.source, res.llm_call_ids, time.time()
            s.add(row)
            s.commit()
    return {"content": res.output, "source": res.source, "llm_call_ids": res.llm_call_ids}


def current_pack(s: Session, route_id: str, lang: str, bucket: str) -> dict:
    row = s.exec(select(SafetyPack).where(SafetyPack.job_key == pack_job_key(route_id, lang, bucket))).first()
    if row:
        return {"content": row.content, "source": row.source, "llm_call_ids": row.llm_call_ids, "pending": False}
    return {"content": pack_template(route_id, lang, bucket), "source": "template", "llm_call_ids": [], "pending": True}


# ---------------------------------------------------------------- 5.8.2 zone advisories

def _alt_hint(route_id: str) -> str:
    alts = route_facts(route_id).get("alternates") or []
    return alts[0]["name"] if alts else ""


async def build_advisories(zone_id: str, *, scanner=None, nonce: str = "", policy: str | None = None,
                           cache: str | None = None, benchmark_run_id: int | None = None) -> None:
    with Session(engine) as s:
        z = s.get(Zone, zone_id)
        if not z:
            return
        kind, severity, seg, note, route_id = z.kind, z.severity, z.segment_name, z.note, z.route_id
    if note and scanner and scanner(note):
        note = None  # flagged note: drop it, use the standard text
    langs = settings.advisory_langs
    run_id = f"adv_{zone_id}"
    out, ids, sources = {}, [], []
    for lang in langs:
        inp = {"zone_kind": kind, "severity": severity, "segment_name": seg or "this area", "language": lang,
               "alternate_hint": _alt_hint(route_id)}
        if note:
            inp["responder_note"] = note
        res = await run_job(job_key=f"{run_id}_{lang}{'_b' + str(benchmark_run_id) if benchmark_run_id else ''}",
                            feature="advisory", route_id=route_id, run_id=run_id,
                            messages=prompts.advisory_messages(inp, nonce),
                            validate=lambda o, inp=inp: validators.validate_advisory(o, inp),
                            template=lambda lang=lang: zone_text(lang, kind, seg),
                            budget_usd=JOB_CFG["advisory"]["budget_usd"],
                            max_steps=len(langs) + 2, run_budget_header=JOB_CFG["advisory"]["budget_usd"] * len(langs),
                            policy=policy, cache=cache, benchmark_run_id=benchmark_run_id)
        out[lang] = {**res.output, "source": res.source}
        ids += res.llm_call_ids
        sources.append(res.source)
    if benchmark_run_id is not None:
        return
    with Session(engine) as s:
        for lang, adv in out.items():
            row = s.exec(select(ZoneAdvisory).where(ZoneAdvisory.zone_id == zone_id, ZoneAdvisory.lang == lang)).first() \
                or ZoneAdvisory(zone_id=zone_id, lang=lang, title="", body="", action="")
            row.title, row.body, row.action, row.source = adv["title"], adv["body"], adv["action"], adv["source"]
            row.llm_call_ids = ids
            s.add(row)
        s.commit()
    src = "ai" if all(x == "ai" for x in sources) else ("template" if all(x == "template" for x in sources) else "mixed")
    events.publish("zone.advisory_ready", {"zone_id": zone_id, "advisories": out, "source": src, "llm_call_ids": ids},
                   events.ALL, route_id=route_id)


# ---------------------------------------------------------------- 5.8.3 incident report

def _nearest_help(s: Session, route_id: str, lat: float, lon: float):
    best, best_d = None, None
    for hp in s.exec(select(HelpPoint).where(HelpPoint.route_id == route_id)).all():
        d = haversine_m(lat, lon, hp.lat, hp.lon)
        if best_d is None or d < best_d:
            best, best_d = hp, d
    return best, best_d


def report_input(s: Session, inc: Incident, sos: SosEvent) -> dict:
    trip = s.get(Trip, sos.trip_id)
    hp, hd = _nearest_help(s, inc.route_id, sos.lat, sos.lon)
    mins = int((sos.created_at_device - trip.last_ping_at) / 60) if trip and trip.last_ping_at and \
        trip.last_ping_at < sos.created_at_device else 0
    return {"kind": sos.kind, "people_bucket": sos.people_bucket, "note_text": sos.note_text or "",
            "segment_name": inc.segment_name or "unknown", "nearest_help": hp.name if hp else "none",
            "distance_to_nearest_help_m": int(round(hd / 10.0) * 10) if hd is not None else None,
            "minutes_since_last_ping": max(mins, 0), "tourist_language": trip.language if trip else "en",
            "responder_language": "en", "flags": sorted(set(sos.flags or []) - {"breakit"})}


async def build_report(incident_id: int, *, key: str = "ops") -> None:
    with Session(engine) as s:
        inc = s.get(Incident, incident_id)
        if not inc:
            return
        rows = s.exec(select(SosEvent).where(SosEvent.incident_id == incident_id).order_by(SosEvent.id)).all()
        if not rows:
            return
        sos = rows[-1]
        inp = report_input(s, inc, sos)
        hp, hd = _nearest_help(s, inc.route_id, sos.lat, sos.lon)
        route_id, n, has_report = inc.route_id, len(rows), bool(inc.report)
    note = inp["note_text"]
    lang = inp["tourist_language"]
    tmpl = lambda: report_template("en", inp["kind"], inp["people_bucket"], inp["segment_name"],
                                   hp.name if hp else None, hd, note)
    if not has_report:  # the responder gets this now; the AI text replaces it when it arrives, however slow the model
        with Session(engine) as s:
            inc = s.get(Incident, incident_id)
            inc.report, inc.report_source = tmpl(), "template"
            s.add(inc)
            s.commit()
            flags = inc.flags
        events.publish("incident.report_ready", {"incident_id": incident_id, "source": "template", "content": tmpl(),
                                                 "llm_call_ids": [], "flags": flags, "escalated": False},
                       events.OPS, route_id=route_id)
    res = await run_job(job_key=f"inc_{incident_id}_{n}", feature="report", route_id=route_id,
                        run_id=f"inc_{incident_id}_{n}", messages=prompts.report_messages(inp),
                        validate=lambda o: validators.validate_report(o, inp), template=tmpl,
                        escalate_upfront=len(note) > 150 or lang not in settings.small_ok_langs,
                        allow_escalation=True, key=key)
    with Session(engine) as s:
        inc = s.get(Incident, incident_id)
        inc.report, inc.report_source, inc.report_llm_call_ids = res.output, res.source, res.llm_call_ids
        if "prompt_injection_signal" in res.shield_codes or "prompt_injection" in res.shield_codes:
            inc.flags = sorted(set(inc.flags or []) | {"suspicious_text", "prune_injection_signal"})
        s.add(inc)
        s.commit()
        flags = inc.flags
    events.publish("incident.report_ready", {"incident_id": incident_id, "source": res.source, "content": res.output,
                                             "llm_call_ids": res.llm_call_ids, "flags": flags,
                                             "escalated": res.escalated}, events.OPS, route_id=route_id)


# ---------------------------------------------------------------- 5.8.4 cluster summary

def cluster_counts(inc: Incident) -> dict:
    return {"people_total": inc.people_total, "injured_reports": inc.injured_total, "sos_reports": inc.member_count,
            "groups": inc.trip_count, "by_kind": inc.count_by_kind}


async def build_cluster_summary(incident_id: int, *, force: bool = False, governor: bool = True,
                                run_budget_header: float | None = None, key: str = "ops") -> None:
    with Session(engine) as s:
        inc = s.get(Incident, incident_id)
        if not inc or inc.type != "cluster":
            return
        now = time.time()
        if not force:
            if inc.summary_member_count == inc.member_count and inc.summary_source == "ai":
                return
            if inc.summary_last_at and now - inc.summary_last_at < settings.cluster_summary_min_interval_s:
                # Too soon for more AI, but the numbers on screen must stay exact: show them now, AI text follows.
                wait = settings.cluster_summary_min_interval_s - (now - inc.summary_last_at) + 0.5
                out = cluster_template("en", inc.people_total, inc.injured_total, inc.segment_name)
                route_id = inc.route_id
                inc.cluster_summary, inc.summary_source = out, "template"
                s.add(inc)
                s.commit()
                events.publish("incident.summary_ready", {"incident_id": incident_id, "source": "template", "content": out,
                                                          "llm_call_ids": []}, events.OPS, route_id=route_id)
                if incident_id not in _refresh_due:
                    _refresh_due.add(incident_id)

                    def again():
                        _refresh_due.discard(incident_id)
                        return build_cluster_summary(incident_id, key=key)
                    spawn_later(wait, again)
                return
        counts = cluster_counts(inc)
        notes = [r.note_text for r in s.exec(select(SosEvent).where(SosEvent.incident_id == incident_id)
                                              .order_by(SosEvent.id)).all() if r.note_text][:15]
        span = int((inc.last_sos_at - inc.first_sos_at) / 60)
        seg, route_id, members = inc.segment_name, inc.route_id, inc.member_count
        refreshes, has_summary = inc.summary_refreshes, bool(inc.cluster_summary)
        inc.summary_last_at = now
        s.add(inc)
        s.commit()
    tmpl = lambda: cluster_template("en", counts["people_total"], counts["injured_reports"], seg)
    shields: list[str] = []
    if refreshes >= 3 and not force:
        out = {**tmpl(), "budget_limit": True}
        source, ids = "template", []
    else:
        allowed = {**counts, "time_span_minutes": span}
        if not has_summary:  # same as the single report: template now, AI text when it arrives
            with Session(engine) as s:
                inc = s.get(Incident, incident_id)
                inc.cluster_summary, inc.summary_source = tmpl(), "template"
                s.add(inc)
                s.commit()
            events.publish("incident.summary_ready", {"incident_id": incident_id, "source": "template", "content": tmpl(),
                                                      "llm_call_ids": []}, events.OPS, route_id=route_id)
        res = await run_job(job_key=f"clu_{incident_id}_{members}{'_stress' if run_budget_header else ''}",
                            feature="cluster", route_id=route_id, run_id=f"clu_{incident_id}_{members}",
                            messages=prompts.cluster_messages(counts, seg, notes, span),
                            validate=lambda o: validators.validate_cluster(o, allowed), template=tmpl,
                            governor=governor, run_budget_header=run_budget_header, key=key)
        out, source, ids, shields = res.output, res.source, res.llm_call_ids, res.shield_codes
        if res.stopped_by in ("run_budget", "agent_step_budget", "governor", "spend_cap"):
            out = {**out, "budget_limit": True}
    with Session(engine) as s:
        inc = s.get(Incident, incident_id)
        if not inc or inc.member_count != members:  # more SOS arrived while the AI was writing, so its counts are old
            return
        inc.cluster_summary, inc.summary_source, inc.summary_llm_call_ids = out, source, ids
        inc.summary_member_count = members
        inc.summary_refreshes = refreshes + (1 if ids else 0)
        if "prompt_injection_signal" in shields or "prompt_injection" in shields:  # same rule as the single report
            inc.flags = sorted(set(inc.flags or []) | {"suspicious_text", "prune_injection_signal"})
        s.add(inc)
        s.commit()
    events.publish("incident.summary_ready", {"incident_id": incident_id, "source": source, "content": out,
                                              "llm_call_ids": ids}, events.OPS, route_id=route_id)


# ---------------------------------------------------------------- 5.8.5 responder copilot

async def build_brief(incident_id: int) -> None:
    with Session(engine) as s:
        inc = s.get(Incident, incident_id)
        if not inc:
            return
        kinds = sorted((inc.count_by_kind or {}).keys()) or ["unknown"]
        book = sops()
        snippets = [it for k in kinds for it in book.get(k, book["unknown"])]
        hps = sorted(s.exec(select(HelpPoint).where(HelpPoint.route_id == inc.route_id)).all(),
                     key=lambda h: haversine_m(inc.center_lat, inc.center_lon, h.lat, h.lon))[:4]
        help_points = [{"id": h.id, "name": h.name, "kind": h.kind} for h in hps]
        summary = inc.cluster_summary if inc.type == "cluster" and inc.cluster_summary else (inc.report or {})
        summary = {k: summary.get(k) for k in ("headline", "what_we_know", "summary", "needs") if summary.get(k)}
        route_id, n = inc.route_id, inc.member_count
    sop_ids = {x["sop_id"] for x in snippets}
    help_ids = {h["id"] for h in help_points}
    res = await run_job(job_key=f"cop_{incident_id}_{n}_v{book.get('version', 1)}", feature="copilot",
                        route_id=route_id, run_id=f"cop_{incident_id}_{n}",
                        messages=prompts.copilot_messages(summary, kinds, snippets, help_points),
                        validate=lambda o: validators.clean_copilot(o, sop_ids, help_ids),
                        template=lambda: {**copilot_template(kinds), "resources_nearby": [h["id"] for h in help_points[:2]]})
    with Session(engine) as s:
        inc = s.get(Incident, incident_id)
        inc.brief, inc.brief_source = {**res.output, "help_points": help_points}, res.source
        s.add(inc)
        s.commit()
    events.publish("incident.brief_ready", {"incident_id": incident_id, "source": res.source,
                                            "content": {**res.output, "help_points": help_points},
                                            "llm_call_ids": res.llm_call_ids}, events.OPS, route_id=route_id)


# ---------------------------------------------------------------- 5.8.6 SMS parse (free-text SMS only)

async def build_sms_parse(sms_id: int) -> None:
    """Read kind, people and a place from a free-text SMS. The SOS already exists; this only fills in detail."""
    from .. import sms
    from ..models import SmsInbound

    with Session(engine) as s:
        row = s.get(SmsInbound, sms_id)
        if not row or not row.text:
            return
        trip = s.get(Trip, row.trip_id) if row.trip_id else None
        route_id, text = (trip.route_id if trip else ""), row.text
    res = await run_job(job_key=f"sms_{sms_id}", feature="sms_parse", route_id=route_id, run_id=f"sms_{sms_id}",
                        messages=prompts.sms_messages(text), validate=lambda o: validators.validate_sms(o, text),
                        template=sms_template)
    with Session(engine) as s:
        sms.apply_parse(s, sms_id, res.output, res.source)


# ---------------------------------------------------------------- 17.3 permit explainer (Phase 2)

async def build_permit_card(trip_id: str) -> dict | None:
    """'What your permit allows' in the tourist's language. One job per (permit type, state, language), so every
    traveller with the same permit and language reuses the first answer: it's paid for once."""
    import re as _re

    from .. import permits
    from ..models import PermitRecord

    with Session(engine) as s:
        trip = s.get(Trip, trip_id)
        rec = s.exec(select(PermitRecord).where(PermitRecord.trip_id == trip_id).order_by(PermitRecord.id.desc())).first()
        if not trip or not rec:
            return None
        inp = permits.explainer_input(trip, rec)
    slug = _re.sub(r"[^a-z0-9]+", "-", f"{inp['state']}-{inp['permit_type']}".lower()).strip("-")[:60]
    key = f"permit_{slug}_{inp['language']}_v1"
    res = await run_job(job_key=key, feature="permit", route_id=trip.route_id, run_id=key,
                        messages=prompts.permit_messages(inp), validate=lambda o: validators.validate_permit(o, inp),
                        template=lambda: permit_template(inp), timeout=20)  # a tourist's screen waits on this one
    return {"content": res.output, "source": res.source, "llm_call_ids": res.llm_call_ids, "simulated": True}
