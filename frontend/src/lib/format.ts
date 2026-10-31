export function ago(ts: number | null | undefined, now = Date.now() / 1000): string {
  if (!ts) return "never";
  const s = Math.max(0, Math.round(now - ts));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  return `${Math.floor(s / 3600)} h ago`;
}

export function clock(ts: number | null | undefined): string {
  if (!ts) return "–";
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function hm(ts: number | null | undefined): string {
  if (!ts) return "–";
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function duration(s: number): string {
  if (s < 60) return `${Math.round(s)} s`;
  return `${Math.floor(s / 60)} m ${Math.round(s % 60)} s`;
}

export function usd(v: number | null | undefined, digits = 5): string {
  return v === null || v === undefined ? "n/a" : `$${v.toFixed(digits)}`;
}

export function inr(v: number | null | undefined, rate: number): string {
  if (v === null || v === undefined) return "n/a";
  const r = v * rate;
  return r < 1 ? `${(r * 100).toFixed(1)} paise` : `₹${r.toFixed(2)}`;
}

export const KIND_ICON: Record<string, string> = {
  landslide: "⛰",
  closed_trail: "⛔",
  restricted: "🛡",
  wildlife_core: "🐅",
  flood: "🌊",
  crowd: "👥",
  custom: "⚠",
};

export const KIND_LABEL: Record<string, string> = {
  landslide: "Landslide",
  closed_trail: "Closed trail",
  restricted: "Restricted area",
  wildlife_core: "Wildlife core",
  flood: "Flood",
  crowd: "Crowd",
  custom: "Custom",
};

export function weatherIcon(code: number): string {
  if (code >= 95) return "⛈️";
  if (code >= 71 && code <= 77) return "🌨️";
  if (code === 85 || code === 86) return "🌨️";
  if (code >= 61 || (code >= 80 && code <= 82)) return "🌧️";
  if (code >= 51) return "🌦️";
  if (code === 45 || code === 48) return "🌫️";
  if (code === 3) return "☁️";
  if (code === 2) return "⛅";
  return "☀️";
}

export function riskText(templates: Record<string, string> | undefined, key: string, value?: number): string {
  const t = templates?.[key] ?? key.replace("_", " ");
  return t.replace("{v}", value === undefined || value === null ? "" : String(Math.round(value * 10) / 10));
}

/** Short English labels for the responder screen (tourists get the full sentences from seed templates). */
export const RISK_SHORT: Record<string, string> = {
  thunderstorm: "Thunderstorm",
  heavy_rain: "Heavy rain {v} mm",
  rain: "Rain {v} mm",
  snow: "Snow {v} cm",
  wind: "Gusts {v} km/h",
  freezing: "Freezing {v} °C",
  cold: "Severe cold {v} °C",
  fog: "Fog",
};

export const SOS_ICON: Record<string, string> = { injured: "🩹", lost: "🧭", stuck: "🪨", medical: "❤️", unsafe: "⚠️", unknown: "❔" };
