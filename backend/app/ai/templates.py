"""Template fallbacks (SPEC 1.3): every AI feature has one, and the UI labels it "Standard text"."""
from ..seeddata import route_facts, route_seed, sops, templates

BUCKET_PEOPLE = {"1": 1, "2-5": 3, "6+": 8}
PEOPLE_LABEL = {"1": "1 person", "2-5": "2–5 people", "6+": "6+ people"}


def zone_text(lang: str, kind: str, segment: str) -> dict:
    t = templates(lang)["zone"].get(kind) or templates(lang)["zone"]["custom"]
    seg = segment or "this area"
    return {"title": t["title"], "body": t["body"].replace("{segment}", seg), "action": t["action"]}


def pack_template(route_id: str, lang: str, bucket: str) -> dict:
    facts = route_facts(route_id)
    t = templates(lang)
    local = templates(route_seed(route_id).get("local_lang", "hi"))
    p = t["pack"]
    fill = {"{route}": facts["route_name"], "{distance}": str(facts.get("distance_km", "")),
            "{emergency}": facts.get("emergency_number", "112"), "{control}": facts.get("control_room_label", "")}
    briefing = []
    for line in p["briefing"]:
        for k, v in fill.items():
            line = line.replace(k, v)
        briefing.append(line)
    return {
        "briefing": briefing,
        "segments": [{"segment_id": sg["id"], "risks": sg.get("risks", [])[:3], "nearest_help_id": sg.get("nearest_help_id")}
                     for sg in facts.get("segments", [])],
        "altitude_signs": p["altitude_signs"] if facts.get("altitude_relevant") else {"symptoms": [], "do_now": []},
        "phrasebook": [{"key": k, "local_text": local["phrases"][k], "user_text": t["phrases"][k]} for k in t["phrases"]],
        "if_cards": [{"key": k, "steps": v} for k, v in p["if_cards"].items()],
    }


def report_template(lang: str, kind: str, people_bucket: str, segment: str, help_name: str | None,
                    help_dist_m: float | None, note: str | None) -> dict:
    t = templates(lang)
    kind_txt = t["kind"].get(kind, kind)
    headline = t["report_headline"].replace("{kind}", kind_txt).replace("{people}", PEOPLE_LABEL.get(people_bucket, people_bucket)) \
        .replace("{segment}", segment or "unknown location")
    facts = [f"Reported: {kind_txt}", f"Group: {PEOPLE_LABEL.get(people_bucket, people_bucket)}"]
    if segment:
        facts.append(f"Location: near {segment}")
    if help_name and help_dist_m is not None:
        facts.append(f"Nearest help: {help_name}, about {int(help_dist_m)} m away")
    return {"headline": headline, "what_we_know": facts, "unknowns": ["Exact condition of the people involved"],
            "translated_note": note or "", "suggested_questions": [
                "Is anyone unconscious or bleeding heavily?", "Can the group move to a safer spot?",
                "Is the path behind you clear?"], "priority_suggestion": None}


def cluster_template(lang: str, people: int, injured: int, segment: str) -> dict:
    t = templates(lang)
    s = t["cluster_summary"].replace("{people}", str(people)).replace("{injured}", str(injured)) \
        .replace("{segment}", segment or "the same area")
    return {"summary": s, "needs": [], "notes_to_check": [], "message_to_group": t["message_to_group"]}


def copilot_template(kinds: list[str]) -> dict:
    book = sops()
    steps = []
    for k in kinds or ["unknown"]:
        for item in book.get(k, book["unknown"])[:3]:
            if len(steps) < 5:
                steps.append({"text": item["text"], "sop_id": item["sop_id"]})
    return {"steps": steps, "resources_nearby": [], "message_to_tourists": templates("en")["message_to_group"]}


def sms_template() -> dict:
    """5.8.6 fallback: nothing extracted, so the SOS stays kind=unknown and the card says to call back."""
    return {"kind": "unknown", "people_bucket": "unknown", "place_hint": ""}


def permit_template(inp: dict) -> dict:
    """Permit card fallback: the official (simulated) text itself, labelled Standard text in the app."""
    return {"title": inp["permit_type"], "allows": [inp["official_text"]] if inp["official_text"] else [], "not_allowed": [],
            "carry": []}
