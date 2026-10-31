"""Fact validators (SPEC 5.10): the core of "never invent facts". No LLM here.

Each validator returns (cleaned_output, errors). Empty errors means the AI output can be used.
"""
import json
import re
import unicodedata

NUM = re.compile(r"\d+(?:[.,]\d+)?")
PHRASE_KEYS = {"help", "injured", "lost", "water", "doctor", "police", "landslide", "which_way", "call_family", "thank_you"}
IF_KEYS = {"lost", "injured", "blocked", "crowd", "wildlife"}
ALLOWED_NEEDS = {"stretcher", "oxygen", "warm_clothing", "water", "food", "search_team", "crowd_control", "other"}
INJURY_WORDS = ("injur", "bleed", "fractur", "unconscious", "dead", "died", "robbed", "attack", "assault", "broken")
BANNED_ADVICE = ("enter the zone", "go inside the zone", "proceed into", "continue through the landslide")
PRIORITIES = {"P1", "P2", "P3", None, ""}


def parse_json(text: str) -> dict:
    t = (text or "").strip()
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("reply was not a JSON object")
    try:
        out = json.loads(t[start:end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e.msg}") from None
    if not isinstance(out, dict):
        raise ValueError("reply was not a JSON object")
    return out


def _strings(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in _strings(v)]
    return []


def _norm_num(raw: str) -> str:
    raw = "".join(str(unicodedata.digit(c)) if c.isdigit() else c for c in raw).replace(",", ".")
    try:
        f = float(raw)
    except ValueError:
        return raw
    return str(int(f)) if f == int(f) else str(round(f, 3))


def numbers_in(obj) -> set[str]:
    return {_norm_num(m.group(0)) for s in _strings(obj) for m in NUM.finditer(s)}


def allowed_numbers(*sources, small: bool = True) -> set[str]:
    # Search the JSON text, so numeric values (not just numbers inside strings) count as "in the input".
    text = json.dumps(list(sources), default=str, ensure_ascii=False)
    nums = {_norm_num(m.group(0)) for m in NUM.finditer(text)}
    if small:
        nums |= {str(i) for i in range(0, 11)}
    return nums


def _check_numbers(out, allowed: set[str], where: str) -> list[str]:
    bad = sorted(numbers_in(out) - allowed)
    return [f"{where}: number(s) {', '.join(bad)} are not in the input"] if bad else []


def _str(v, limit: int) -> bool:
    return isinstance(v, str) and 0 < len(v.strip()) <= limit


def validate_pack(out: dict, facts: dict):
    errs = []
    for k in ("briefing", "segments", "altitude_signs", "phrasebook", "if_cards"):
        if k not in out:
            errs.append(f"missing key {k}")
    if errs:
        return out, errs
    if not isinstance(out["briefing"], list) or not 1 <= len(out["briefing"]) <= 6 \
            or not all(_str(x, 200) for x in out["briefing"]):
        errs.append("briefing must be 1-6 short strings")
    seg_ids = {s["id"] for s in facts.get("segments", [])}
    help_ids = {h["id"] for h in facts.get("help_points", [])}
    for sg in out["segments"] if isinstance(out["segments"], list) else []:
        if sg.get("segment_id") not in seg_ids:
            errs.append(f"unknown segment_id {sg.get('segment_id')}")
        if sg.get("nearest_help_id") and sg["nearest_help_id"] not in help_ids:
            errs.append(f"unknown nearest_help_id {sg.get('nearest_help_id')}")
        if len(sg.get("risks", [])) > 3:
            errs.append("at most 3 risks per segment")
    keys = {p.get("key") for p in out["phrasebook"] if isinstance(p, dict)} if isinstance(out["phrasebook"], list) else set()
    if keys != PHRASE_KEYS:
        errs.append(f"phrasebook keys must be exactly {sorted(PHRASE_KEYS)}")
    for p in out["phrasebook"] if isinstance(out["phrasebook"], list) else []:
        if not (_str(p.get("local_text"), 200) and _str(p.get("user_text"), 200)):
            errs.append(f"phrase {p.get('key')} needs local_text and user_text")
    for c in out["if_cards"] if isinstance(out["if_cards"], list) else []:
        if c.get("key") not in IF_KEYS or not isinstance(c.get("steps"), list) or len(c["steps"]) > 4:
            errs.append(f"bad if_card {c.get('key')}")
    errs += _check_numbers(out, allowed_numbers(facts), "pack")
    return out, errs


def validate_advisory(out: dict, inp: dict):
    errs = []
    if not (_str(out.get("title"), 60) and _str(out.get("body"), 240) and _str(out.get("action"), 80)):
        errs.append("title (<=60 chars), body (<=240) and action (<=80) are required")
    text = " ".join(_strings(out)).lower()
    if any(b in text for b in BANNED_ADVICE):
        errs.append("must never tell people to enter the zone")
    errs += _check_numbers(out, allowed_numbers(inp), "advisory")
    return {k: out.get(k) for k in ("title", "body", "action")}, errs


def validate_report(out: dict, inp: dict):
    errs = []
    if not _str(out.get("headline"), 100):
        errs.append("headline (<=100 chars) is required")
    for k in ("what_we_know", "unknowns", "suggested_questions"):
        if not isinstance(out.get(k), list) or not all(isinstance(x, str) for x in out.get(k, [])):
            errs.append(f"{k} must be a list of strings")
    if isinstance(out.get("suggested_questions"), list) and len(out["suggested_questions"]) > 3:
        out["suggested_questions"] = out["suggested_questions"][:3]
    if out.get("priority_suggestion") not in PRIORITIES:
        errs.append("priority_suggestion must be P1, P2 or P3")
    note = inp.get("note_text") or ""
    tr = out.get("translated_note") or ""
    if not isinstance(tr, str):
        errs.append("translated_note must be a string")
    elif note:
        if numbers_in(tr) - numbers_in(note):
            errs.append("translated_note adds numbers that are not in the note")
        if len(tr) > 1.6 * len(note) + 20:
            errs.append("translated_note is much longer than the note")
    elif len(tr) > 5:
        errs.append("translated_note must be empty when there is no note")
    reported = inp.get("kind") in ("injured", "medical") or any(w in note.lower() for w in INJURY_WORDS)
    known = " ".join(out.get("what_we_know") or []).lower() + " " + (out.get("headline") or "").lower()
    if not reported and any(w in known for w in INJURY_WORDS):
        errs.append("report mentions injuries or crimes that were not reported")
    errs += _check_numbers({k: out.get(k) for k in ("headline", "what_we_know", "unknowns", "suggested_questions")},
                           allowed_numbers(inp), "report")
    return out, errs


def validate_cluster(out: dict, counts: dict):
    errs = []
    if not _str(out.get("summary"), 200):
        errs.append("summary (<=200 chars) is required")
    allowed = allowed_numbers(counts, small=False)
    bad = sorted(numbers_in(out.get("summary", "")) - allowed)
    if bad:
        errs.append(f"summary numbers {', '.join(bad)} must equal the computed counts")
    needs = out.get("needs") or []
    if not isinstance(needs, list) or any(n not in ALLOWED_NEEDS for n in needs):
        errs.append(f"needs must come from {sorted(ALLOWED_NEEDS)}")
    if not isinstance(out.get("notes_to_check", []), list):
        errs.append("notes_to_check must be a list")
    msg = out.get("message_to_group") or ""
    if msg and (len(msg) > 200 or numbers_in(msg) - allowed):
        errs.append("message_to_group is too long or has numbers not in the counts")
    return out, errs


def clean_copilot(out: dict, sop_ids: set[str], help_ids: set[str]):
    steps = [st for st in (out.get("steps") or []) if isinstance(st, dict) and st.get("sop_id") in sop_ids
             and _str(st.get("text"), 160)][:5]
    res = [h for h in (out.get("resources_nearby") or []) if h in help_ids]
    msg = out.get("message_to_tourists") or ""
    cleaned = {"steps": steps, "resources_nearby": res, "message_to_tourists": msg[:200]}
    errs = [] if steps else ["no step cites a real SOP id"]
    return cleaned, errs


SMS_KINDS = {"injured", "lost", "stuck", "medical", "unsafe", "unknown"}
SMS_BUCKETS = {"1", "2-5", "6+", "unknown"}


def validate_sms(out: dict, text: str):
    """sms_parse (5.8.6): only the allowed values, and a place only if it's copied from the SMS itself."""
    errs = []
    kind = str(out.get("kind", "")).strip().lower()
    bucket = str(out.get("people_bucket", "")).strip()
    place = str(out.get("place_hint") or "").strip()
    if kind not in SMS_KINDS:
        errs.append(f"kind must be one of {sorted(SMS_KINDS)}")
    if bucket not in SMS_BUCKETS:
        errs.append(f"people_bucket must be one of {sorted(SMS_BUCKETS)}")
    if len(place) > 60:
        errs.append("place_hint is longer than 60 characters")
    elif place and _fold(place) not in _fold(text):
        errs.append("place_hint must be copied from the SMS, not invented")
    return {"kind": kind, "people_bucket": bucket, "place_hint": place}, errs


def _fold(t: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", t or "").casefold().split())
