"""SQLModel tables (SPEC Section 6). Times are unix epoch seconds (float, UTC)."""
import time
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def now() -> float:
    return time.time()


def J(default=None):
    """A JSON column."""
    return Field(default=default, sa_column=Column(JSON))


class Route(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    region: str = ""
    line: Any = J()  # GeoJSON LineString geometry
    bbox: Any = J()  # [minLon, minLat, maxLon, maxLat]
    center: Any = J()  # [lon, lat]
    facts_version: int = 1
    simulated: bool = True
    local_lang: str = "hi"


class RouteFacts(SQLModel, table=True):
    route_id: str = Field(primary_key=True)
    version: int = 1
    facts: Any = J()


class HelpPoint(SQLModel, table=True):
    id: str = Field(primary_key=True)
    route_id: str = Field(index=True)
    kind: str  # medical|shelter|police|checkpoint|ranger
    name: str
    lat: float
    lon: float
    simulated: bool = True
    source: str = "seed"  # seed (simulated) | osm (OpenStreetMap, real)


class Checkpoint(SQLModel, table=True):
    id: str = Field(primary_key=True)
    route_id: str = Field(index=True)
    name: str
    lat: float
    lon: float


class Zone(SQLModel, table=True):
    id: str = Field(primary_key=True)
    route_id: str = Field(index=True)
    kind: str  # landslide|closed_trail|restricted|wildlife_core|flood|crowd|red_zone|custom
    severity: str = "danger"  # warn|danger
    polygon: Any = J()  # GeoJSON Polygon geometry
    source: str = "seeded"  # seeded|drawn|auto_crowd
    note: Optional[str] = None
    segment_name: str = ""
    simulated: bool = True
    active: bool = True
    created_by: str = "seed"
    created_at: float = Field(default_factory=now)
    expires_at: Optional[float] = None


class ZoneAdvisory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    zone_id: str = Field(index=True)
    lang: str
    title: str
    body: str
    action: str
    source: str = "template"  # ai|template
    llm_call_ids: Any = J([])


class Trip(SQLModel, table=True):
    id: str = Field(primary_key=True)
    label: str = Field(index=True)
    name: str
    phone: str = ""
    emergency_contact_name: str = ""
    emergency_contact_phone: str = ""
    language: str = "en"
    route_id: str = Field(index=True)
    group_size: int = 1
    profile_bucket: str = "standard"  # standard|senior|with_children|medical_note
    start_at: Optional[float] = None
    end_at: Optional[float] = None
    status: str = "planned"  # planned|active|quiet|quiet_red|sos|safe|ended
    sharing: bool = False
    last_ping_at: Optional[float] = None
    last_lat: Optional[float] = None
    last_lon: Optional[float] = None
    last_accuracy_m: Optional[float] = None
    last_segment: str = ""
    family_token: str = Field(index=True)
    family_revoked: bool = False
    consent_version: str = ""
    consent_at: Optional[float] = None
    tourist_token: str = Field(index=True)
    kind: str = "tourist"  # tourist|sim|breakit
    created_at: float = Field(default_factory=now)


class Pass(SQLModel, table=True):
    id: str = Field(primary_key=True)
    trip_id: str = Field(index=True)
    payload: Any = J()
    qr: str
    valid_from: float
    valid_to: float
    kyc_level: str = "demo"


class PermitRecord(SQLModel, table=True):
    """Phase 2 (SPEC 17.5). The full ID number is never stored: only a salted hash and the last 4 characters."""
    id: Optional[int] = Field(default=None, primary_key=True)
    trip_id: str = Field(index=True)
    id_type: str  # visa|evisa|eilp|yatra|passport|digilocker|voter|aadhaar_masked
    id_last4: str
    id_hash: str
    permit_type: str
    issuing_state: str = ""
    valid_from: float
    valid_to: float
    permitted_zone_ids: Any = J([])
    routes: Any = J([])
    verified_via: str = "mock_registry"  # mock_registry|manual
    created_at: float = Field(default_factory=now)


class PassRevocation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pass_id: str = Field(index=True)
    reason: str = ""
    revoked_by: str = "responder"
    revoked_at: float = Field(default_factory=now)


class Ping(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    trip_id: str = Field(index=True)
    lat: float
    lon: float
    accuracy_m: float = 20
    ts_device: float
    ts_server: float = Field(default_factory=now)
    source: str = "gps"  # gps|checkpoint|sim
    flags: Any = J([])


class SosEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: str = Field(index=True, unique=True)
    trip_id: str = Field(index=True)
    kind: str  # injured|lost|stuck|medical|unsafe|unknown
    people_bucket: str = "1"  # 1|2-5|6+
    note_text: Optional[str] = None
    lat: float
    lon: float
    accuracy_m: float = 20
    created_at_device: float
    received_at_server: float = Field(default_factory=now)
    channel: str = "data"  # data|sms|checkpoint
    flags: Any = J([])
    incident_id: Optional[int] = Field(default=None, index=True)
    cancelled_at: Optional[float] = None


class SmsInbound(SQLModel, table=True):
    """An SMS from the gateway (SPEC 5.6 SMS inbound). The sender's number is never stored: only a salted hash
    (to recognise repeats) and the last 4 digits (for the call-back card). The text is cleared after 30 days."""
    id: Optional[int] = Field(default=None, primary_key=True)
    from_hash: str = Field(default="", index=True)
    from_last4: str = ""
    text: Optional[str] = None
    parsed_via: str = ""  # coded|free_text|unmatched|duplicate
    trip_id: Optional[str] = None
    sos_client_id: Optional[str] = None
    ai_source: Optional[str] = None  # ai|template, once the sms_parse job has run
    ai_result: Any = J(None)
    received_at: float = Field(default_factory=now)


class Incident(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    route_id: str = Field(index=True)
    type: str = "single"  # single|cluster
    status: str = "new"  # new|accepted|en_route|resolved|cancelled
    priority: str = "P3"
    center_lat: float = 0
    center_lon: float = 0
    radius_m: float = 0
    segment_name: str = ""
    member_count: int = 0
    trip_count: int = 0
    people_total: int = 0
    people_breakdown: Any = J({})
    count_by_kind: Any = J({})
    injured_total: int = 0
    first_sos_at: float = Field(default_factory=now)
    last_sos_at: float = Field(default_factory=now)
    report: Any = J(None)
    report_source: Optional[str] = None
    report_llm_call_ids: Any = J([])
    cluster_summary: Any = J(None)
    summary_source: Optional[str] = None
    summary_llm_call_ids: Any = J([])
    summary_refreshes: int = 0
    summary_last_at: Optional[float] = None
    summary_member_count: int = 0
    brief: Any = J(None)
    brief_source: Optional[str] = None
    flags: Any = J([])
    team: Optional[str] = None
    accepted_by: Optional[str] = None
    accepted_at: Optional[float] = None
    en_route_at: Optional[float] = None
    resolved_at: Optional[float] = None


class SafetyCheck(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    route_id: str = ""
    zone_id: Optional[str] = None
    polygon: Any = J(None)
    message_key: str = "check_landslide"
    targets: Any = J([])  # trip ids
    sent_by: str = ""
    sent_at: float = Field(default_factory=now)


class CheckResponse(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    check_id: int = Field(index=True)
    trip_id: str
    answer: str  # safe|need_help
    ts: float = Field(default_factory=now)


class SafetyPack(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_key: str = Field(index=True, unique=True)
    route_id: str
    lang: str
    profile_bucket: str
    facts_version: int
    content: Any = J()
    source: str = "template"
    llm_call_ids: Any = J([])
    created_at: float = Field(default_factory=now)


class AiJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_key: str = Field(index=True, unique=True)
    feature: str
    status: str = "queued"  # queued|running|done|template|failed_soft
    source: Optional[str] = None  # ai|template
    budget_usd: float = 0
    spent_usd: float = 0
    steps_used: int = 0
    stopped_by: Optional[str] = None
    validator_rejections: int = 0
    escalated: bool = False
    output: Any = J(None)
    llm_call_ids: Any = J([])
    error: Optional[str] = None
    benchmark_run_id: Optional[int] = None
    created_at: float = Field(default_factory=now)
    completed_at: Optional[float] = None


class LlmCall(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_key: str = Field(index=True)
    run_id: str = ""
    feature: str = Field(index=True)
    route_id: str = ""
    tier: str = ""  # small|large (what SafeTrail asked for)
    requested_model: str = ""
    original_model: Optional[str] = None
    routed_model: Optional[str] = None
    route_applied: Optional[bool] = None
    route_reason: Optional[str] = None
    route_fallback: Optional[str] = None
    provider: Optional[str] = None
    cache_mode: str = ""
    model_policy: str = ""
    cache_hit: Optional[bool] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    tokens_saved: Optional[int] = None
    optimizations_applied: Any = J(None)
    pii_shield: Any = J(None)
    shield_code: Optional[str] = None
    http_status: Optional[int] = None
    cost_with_prune_usd: Optional[float] = None
    cost_without_prune_usd: Optional[float] = None
    cost_saved_usd: Optional[float] = None
    estimated_cost_usd: Optional[float] = None  # governor estimate, never displayed as actual
    latency_ms: Optional[int] = None
    receipt_signature: Optional[str] = None
    receipt_signing_key_id: Optional[str] = None
    raw_metadata: Any = J(None)
    raw_headers: Any = J(None)
    prompt_preview: str = ""  # PII-scrubbed, truncated
    status: str = "ok"  # ok|error|retried|repair
    error_code: Optional[str] = None
    escalated: bool = False
    key_used: str = "ops"
    benchmark_run_id: Optional[int] = None
    created_at: float = Field(default_factory=now)


class EventLog(SQLModel, table=True):
    seq: Optional[int] = Field(default=None, primary_key=True)
    ts_server: float
    type: str
    entity_type: str = Field(index=True)
    entity_id: str = Field(index=True)
    payload: Any = J()
    payload_hash: str
    prev_hash: str
    hash: str
    signature: str
    key_id: str


class BreakItAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nickname: str
    consent: bool = False
    trick: str
    detail: Any = J({})
    outcome: str  # caught|flagged|slipped|not_flagged
    caught_by: Any = J([])
    self_report: Optional[bool] = None
    created_at: float = Field(default_factory=now)


class BenchmarkRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    config: str  # naive|lean_no_prune|prune_cold|prune_warm
    nonce: str = ""
    status: str = "queued"
    metrics: Any = J(None)
    created_at: float = Field(default_factory=now)
    completed_at: Optional[float] = None


class DemoState(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: Any = J(None)
