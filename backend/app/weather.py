"""Live weather along each route section, from Open-Meteo (free, no key; data CC BY 4.0).

Plain code, no AI: warnings come from fixed thresholds, so they never depend on the AI or its budget.
Results are cached for 30 minutes per route, and the last good result is kept if a refresh fails.
"""
import logging
import threading
import time

import httpx

from .seeddata import route_seed

URL = "https://api.open-meteo.com/v1/forecast"
HEADERS = {"User-Agent": "SafeTrail-hackathon/1.0 (https://github.com/gaurvit06/Safetrail)"}
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"
MAX_AGE_S = 1800
HOURS_AHEAD = 12

log = logging.getLogger("safetrail.weather")
_cache: dict[str, dict] = {}
_lock = threading.Lock()

WMO = {0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Freezing fog",
       51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
       61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain", 71: "Light snow",
       73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Rain showers", 81: "Rain showers",
       82: "Violent rain showers", 85: "Snow showers", 86: "Heavy snow showers", 95: "Thunderstorm",
       96: "Thunderstorm with hail", 99: "Thunderstorm with hail"}
LEVELS = {"none": 0, "warn": 1, "danger": 2}


def section_points(route_id: str) -> list[tuple[str, str, float, float]]:
    out = []
    for seg in route_seed(route_id).get("segments", []):
        c = seg["coords"]
        lon, lat = c[len(c) // 2]
        out.append((seg["id"], seg["name"], lat, lon))
    return out


def risks_for(s: dict) -> list[dict]:
    """Fixed thresholds (per hour / next 12 h). IMD calls ≥ 7.6 mm/h heavy rain."""
    r = []
    codes = set(s["codes"])
    if codes & {95, 96, 99}:
        r.append({"key": "thunderstorm", "level": "danger"})
    if s["rain_max_h"] >= 7.6 or s["rain_12h"] >= 35:
        r.append({"key": "heavy_rain", "level": "danger", "value": s["rain_12h"]})
    elif s["rain_max_h"] >= 2.5 or s["rain_prob_max"] >= 70:
        r.append({"key": "rain", "level": "warn", "value": s["rain_12h"]})
    if s["snow_12h"] >= 5:
        r.append({"key": "snow", "level": "danger", "value": s["snow_12h"]})
    elif s["snow_12h"] >= 0.5:
        r.append({"key": "snow", "level": "warn", "value": s["snow_12h"]})
    if s["gust_max"] >= 90:
        r.append({"key": "wind", "level": "danger", "value": s["gust_max"]})
    elif s["gust_max"] >= 60:
        r.append({"key": "wind", "level": "warn", "value": s["gust_max"]})
    if s["temp_min"] is not None and s["temp_min"] <= -8:
        r.append({"key": "cold", "level": "danger", "value": s["temp_min"]})
    elif s["temp_min"] is not None and s["temp_min"] <= 0:
        r.append({"key": "freezing", "level": "warn", "value": s["temp_min"]})
    if codes & {45, 48}:
        r.append({"key": "fog", "level": "warn"})
    return r


def _worst(levels) -> str:
    return max(levels, key=lambda x: LEVELS[x], default="none")


def summarise(hourly: dict, now: float) -> dict:
    times = hourly["time"]
    idx = [i for i, t in enumerate(times) if now - 3600 <= t <= now + HOURS_AHEAD * 3600] or [0]
    g = lambda k: [hourly[k][i] for i in idx if hourly[k][i] is not None]
    temps = g("temperature_2m")
    return {"temp_now": hourly["temperature_2m"][idx[0]], "code_now": hourly["weather_code"][idx[0]],
            "temp_min": min(temps) if temps else None, "temp_max": max(temps) if temps else None,
            "rain_12h": round(sum(g("precipitation")), 1), "rain_max_h": max(g("precipitation"), default=0),
            "rain_prob_max": max(g("precipitation_probability"), default=0),
            "snow_12h": round(sum(g("snowfall")), 1), "gust_max": round(max(g("wind_gusts_10m"), default=0)),
            "codes": g("weather_code")}


def fetch(route_id: str) -> dict:
    pts = section_points(route_id)
    params = {"latitude": ",".join(f"{p[2]:.4f}" for p in pts), "longitude": ",".join(f"{p[3]:.4f}" for p in pts),
              "hourly": "temperature_2m,precipitation,precipitation_probability,weather_code,wind_gusts_10m,snowfall",
              "forecast_days": 2, "timezone": "Asia/Kolkata", "timeformat": "unixtime"}
    resp = httpx.get(URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        data = [data]
    now = time.time()
    sections = []
    for (sid, name, lat, lon), d in zip(pts, data):
        s = summarise(d["hourly"], now)
        risks = risks_for(s)
        sections.append({"segment_id": sid, "name": name, "lat": lat, "lon": lon, "elevation_m": d.get("elevation"),
                         "now": {"temp_c": s["temp_now"], "code": s["code_now"], "desc": WMO.get(s["code_now"], "—")},
                         "next12h": {k: s[k] for k in ("temp_min", "temp_max", "rain_12h", "rain_prob_max",
                                                       "snow_12h", "gust_max")},
                         "risks": risks, "level": _worst(r["level"] for r in risks)})
    return {"route_id": route_id, "available": True, "fetched_at": now, "source": "Open-Meteo",
            "attribution": ATTRIBUTION, "hours_ahead": HOURS_AHEAD, "sections": sections,
            "level": _worst(x["level"] for x in sections)}


def get(route_id: str, max_age_s: float = MAX_AGE_S) -> dict:
    with _lock:
        cached = _cache.get(route_id)
    if cached and time.time() - cached["fetched_at"] < max_age_s:
        return cached
    try:
        w = fetch(route_id)
        with _lock:
            _cache[route_id] = w
        return w
    except Exception as e:  # network down or service busy: keep the last good forecast, marked stale
        log.warning("weather fetch failed for %s: %s", route_id, e)
        if cached:
            return {**cached, "stale": True}
        return {"route_id": route_id, "available": False, "sections": [], "level": "none", "attribution": ATTRIBUTION}


def cached(route_id: str) -> dict | None:
    with _lock:
        return _cache.get(route_id)
