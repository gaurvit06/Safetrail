export type Lang = "en" | "hi";
export type Polygon = { type: "Polygon"; coordinates: number[][][] };
export type Advisory = { title: string; body: string; action: string; source: string };

export type Zone = {
  id: string;
  route_id: string;
  kind: string;
  severity: "warn" | "danger";
  polygon: Polygon;
  source: string;
  note?: string | null;
  segment_name: string;
  simulated: boolean;
  active: boolean;
  created_at: number;
  expires_at?: number | null;
  advisories: Record<string, Advisory>;
};

export type HelpPoint = { id: string; route_id: string; kind: string; name: string; lat: number; lon: number; simulated: boolean; source?: string };

export type WeatherRisk = { key: string; level: "warn" | "danger"; value?: number };
export type WeatherSection = {
  segment_id: string;
  name: string;
  lat: number;
  lon: number;
  elevation_m: number | null;
  now: { temp_c: number; code: number; desc: string };
  next12h: { temp_min: number | null; temp_max: number | null; rain_12h: number; rain_prob_max: number; snow_12h: number; gust_max: number };
  risks: WeatherRisk[];
  level: "none" | "warn" | "danger";
};
export type Weather = {
  route_id: string;
  available: boolean;
  fetched_at?: number;
  source?: string;
  attribution: string;
  hours_ahead?: number;
  sections: WeatherSection[];
  level: string;
  stale?: boolean;
};
export type Checkpoint = { id: string; route_id: string; name: string; lat: number; lon: number };
export type Segment = { id: string; name: string; coords: number[][]; risky?: boolean; length_km?: number; nearest_help_id?: string };

export type RouteDetail = {
  id: string;
  name: string;
  region: string;
  line: { type: "LineString"; coordinates: number[][] };
  bbox: number[];
  center: number[];
  simulated: boolean;
  local_lang: string;
  segments: Segment[];
  help_points: HelpPoint[];
  checkpoints: Checkpoint[];
  zones: Zone[];
  facts: {
    route_name: string;
    distance_km: number;
    emergency_number: string;
    control_room_label: string;
    alternates: { id: string; name: string }[];
    crowd_wait_min: number;
    segment_capacity: number;
  };
};

export type RouteSummary = { id: string; name: string; region: string; center: number[]; bbox: number[]; simulated: boolean; distance_km: number };

export type Trip = {
  id: string;
  label: string;
  name: string;
  language: Lang;
  route_id: string;
  group_size: number;
  profile_bucket: string;
  start_at: number | null;
  end_at: number | null;
  status: string;
  sharing: boolean;
  last_ping_at: number | null;
  kind: string;
};

export type PackContent = {
  briefing: string[];
  segments: { segment_id: string; risks: string[]; nearest_help_id?: string }[];
  altitude_signs: { symptoms: string[]; do_now: string[] };
  phrasebook: { key: string; local_text: string; user_text: string }[];
  if_cards: { key: string; steps: string[] }[];
};
export type Pack = { content: PackContent; source: string; llm_call_ids: number[]; pending: boolean };

export type Templates = {
  zone: Record<string, { title: string; body: string; action: string }>;
  approach: string;
  crowd_inside: string;
  crowd_ahead: string;
  check: Record<string, string>;
  kind: Record<string, string>;
  phrases: Record<string, string>;
  ui: Record<string, string>;
  message_to_group: string;
  weather?: Record<string, string>;
};

export type Config = {
  public_url: string;
  sms_number: string | null;
  advisory_langs: string[];
  approach_m: number;
  sms_offer_after_s: number;
  usd_inr: number;
  pass_pubkey: string;
  log_pubkey: string;
  log_key_id: string;
};

export type StartBundle = {
  trip: Trip;
  route: RouteDetail;
  pack: Pack;
  templates: Templates;
  server_pubkey: string;
  pass_qr: string;
  pass: Record<string, unknown>;
  family_token: string;
  config: Config;
  weather?: Weather | null;
};

export type TripCreated = { trip: Trip; pass_qr: string; tourist_token: string; family_url: string; family_token: string };

export type IncidentSummary = {
  id: number;
  route_id: string;
  type: "single" | "cluster";
  status: string;
  priority: "P1" | "P2" | "P3";
  center_lat: number;
  center_lon: number;
  radius_m: number;
  segment_name: string;
  member_count: number;
  trip_count: number;
  people_total: number;
  people_breakdown: Record<string, number>;
  count_by_kind: Record<string, number>;
  injured_total: number;
  first_sos_at: number;
  last_sos_at: number;
  flags: string[];
  headline: string | null;
  headline_source: string | null;
  team: string | null;
  accepted_at: number | null;
  en_route_at: number | null;
  resolved_at: number | null;
};

export type LlmCallBrief = {
  id: number;
  feature: string;
  tier: string;
  requested_model: string;
  routed_model: string | null;
  route_applied: boolean | null;
  cache_hit: boolean | null;
  cost_with_prune_usd: number | null;
  cost_without_prune_usd: number | null;
  latency_ms: number | null;
  status: string;
  error_code: string | null;
  shield_code: string | null;
  escalated: boolean;
  receipt_signature: string | null;
  receipt_signing_key_id: string | null;
  created_at: number;
};

export type SosRow = {
  client_id: string;
  trip_label: string;
  name: string;
  kind: string;
  people_bucket: string;
  note_text: string | null;
  lat: number;
  lon: number;
  accuracy_m: number;
  channel: string;
  flags: string[];
  created_at_device: number;
  received_at_server: number;
  delay_s: number;
  cancelled_at: number | null;
};

export type IncidentDetail = IncidentSummary & {
  sos: SosRow[];
  report: any;
  report_source: string | null;
  cluster_summary: any;
  summary_source: string | null;
  brief: any;
  brief_source: string | null;
  llm_calls: LlmCallBrief[];
};

export type Tally = {
  check_id: number;
  asked: number;
  safe: number;
  need_help: number;
  no_answer: number;
  no_answer_trip_labels: string[];
  overdue: boolean;
  sent_at: number;
  zone_id: string | null;
};

export type Dot = {
  trip_label: string;
  name: string;
  lat: number;
  lon: number;
  accuracy_m: number | null;
  status: string;
  flags: string[];
  kind: string;
  route_id: string;
  last_ping_at: number | null;
};

export type CrowdHeat = { points: { lat: number; lon: number; n: number }[]; people: number; simulated: boolean };
export type HeatCell = { id: string; count: number; density: number; level: "green" | "amber" | "red"; trend: string; polygon: Polygon };

export type Evt = { type: string; ts: number; route_id?: string | null; trip_id?: string | null; data: any };

export type AiStats = {
  calls: number;
  ok_calls: number;
  errors: number;
  cost_usd: number | null;
  cost_inr: number | null;
  cost_known_calls: number;
  prune_estimate_without_usd: number | null;
  cache_hits: number;
  routed: number;
  escalations: number;
  template_fallbacks: number;
  validator_rejections: number;
  trips_started: number;
  incidents: number;
  cost_per_trip_usd: number | null;
  cost_per_emergency_usd: number | null;
  by_feature: Record<string, { calls: number; cost_usd: number; cost_known: number; cache_hits: number; routed: number }>;
  ai_configured: boolean;
  usd_inr: number;
};

/** The signed pass payload. Phase 2 fields appear once a permit is linked (SPEC 17.2). */
export type PassPayload = {
  pass_id: string;
  trip_label: string;
  route_id: string;
  valid_from: number;
  valid_to: number;
  kyc_level: "demo" | "verified" | "self_declared";
  id_type?: string;
  id_last4?: string;
  permit_type?: string;
  permit_valid_to?: number;
  permitted_zone_ids?: string[];
};

export type PermitInfo = {
  record_id: number;
  id_type: string;
  id_last4: string;
  permit_type: string;
  issuing_state: string;
  valid_from: number;
  valid_to: number;
  permitted_zone_ids: string[];
  permitted_zones: string[];
  covers_route: boolean;
  expired: boolean;
  verified_via: string;
  simulated: boolean;
};

export type PermitCard = { content: { title: string; allows: string[]; not_allowed: string[]; carry: string[] }; source: string; simulated: boolean };

export type RoundSummary = {
  round: number; minutes: number; judges: number; sos: number; incidents: number; accepted: number; safe: number;
  need_help: number; ai_calls: number; ai_cost_usd: number | null; tricks: number; tricks_caught: number;
};
export type RoundState = { round: number; started_at: number; last: RoundSummary | null };
