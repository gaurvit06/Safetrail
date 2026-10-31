"""All settings come from backend/.env (see .env.example). Nothing secret is hardcoded."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
SEED_DIR = BACKEND_DIR / "seed"
load_dotenv(REPO_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env", override=True)


def _s(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


class Settings:
    public_url = _s("PUBLIC_URL")
    db_path = _s("DB_PATH", str(BACKEND_DIR / "safetrail.db"))

    prune_base_url = _s("PRUNE_BASE_URL", "https://api.withprune.com/v1")
    prune_api_key = _s("PRUNE_API_KEY")
    prune_public_api_key = _s("PRUNE_PUBLIC_API_KEY")
    prune_model_policy = _s("PRUNE_MODEL_POLICY", "balanced")
    prune_cache_mode = _s("PRUNE_CACHE_MODE", "exact")
    prune_injection_mode = _s("PRUNE_INJECTION_MODE", "detect")
    model_small = _s("MODEL_SMALL")
    model_large = _s("MODEL_LARGE")
    small_ok_langs = [x for x in _s("SMALL_OK_LANGS", "en,hi").split(",") if x]
    advisory_langs = [x for x in _s("ADVISORY_LANGS", "en,hi").split(",") if x]

    usd_inr = _f("USD_INR", 88.0)
    max_concurrent_ai_jobs = _i("MAX_CONCURRENT_AI_JOBS", 3)
    max_calls_per_min = _i("MAX_CALLS_PER_MIN", 60)
    public_budget_usd = _f("PUBLIC_BUDGET_USD", 0.50)

    pass_signing_key = _s("PASS_SIGNING_KEY")
    log_signing_key = _s("LOG_SIGNING_KEY")
    responder_pin = _s("RESPONDER_PIN", "2468")
    presenter_pin = _s("PRESENTER_PIN", "1357")
    token_secret = _s("TOKEN_SECRET", "change-me-in-env")

    sos_sms_number = _s("SOS_SMS_NUMBER")
    sms_webhook_secret = _s("SMS_WEBHOOK_SECRET")

    approach_m = _f("APPROACH_M", 80)
    crowd_cell_m = _f("CROWD_CELL_M", 25)
    crowd_tick_s = _f("CROWD_TICK_S", 10)
    cluster_eps_m = _f("CLUSTER_EPS_M", 150)
    cluster_summary_min_interval_s = _f("CLUSTER_SUMMARY_MIN_INTERVAL_S", 60)
    quiet_min_risky = _f("QUIET_MIN_RISKY", 15)
    quiet_min = _f("QUIET_MIN", 30)
    check_no_answer_min = _f("CHECK_NO_ANSWER_MIN", 10)
    sms_offer_after_s = _f("SMS_OFFER_AFTER_S", 120)
    max_trek_speed_kmh = _f("MAX_TREK_SPEED_KMH", 30)
    ping_retention_days = _f("PING_RETENTION_DAYS", 7)
    demo_zone_radius_m = _f("DEMO_ZONE_RADIUS_M", 60)
    frontend_origin = _s("FRONTEND_ORIGIN")


settings = Settings()

# Per-job budgets (Section 5.12). Placeholders: tune after real runs, log changes in docs/DECISIONS.md.
JOB_CFG = {
    "pack": {"budget_usd": 0.01, "max_steps": 3, "tier": "small", "max_tokens": 900},
    "advisory": {"budget_usd": 0.005, "max_steps": 2, "tier": "small", "max_tokens": 200},  # per language; run scales
    "report": {"budget_usd": 0.02, "max_steps": 4, "tier": "small", "max_tokens": 450},
    "cluster": {"budget_usd": 0.03, "max_steps": 3, "tier": "large", "max_tokens": 350},
    "copilot": {"budget_usd": 0.01, "max_steps": 3, "tier": "small", "max_tokens": 400},
}

# Planning-only price table (USD per 1M tokens) used by the governor to ESTIMATE before a call.
# Never shown as an actual cost. Actual costs always come from Prune's metadata.
PRICE_TABLE = {
    "small": {"in": _f("PRICE_SMALL_IN_PER_M", 0.15), "out": _f("PRICE_SMALL_OUT_PER_M", 0.60)},
    "large": {"in": _f("PRICE_LARGE_IN_PER_M", 2.50), "out": _f("PRICE_LARGE_OUT_PER_M", 10.00)},
}


def model_for(tier: str) -> str:
    return settings.model_large if tier == "large" else settings.model_small
