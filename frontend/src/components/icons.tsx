import type { LucideIcon } from "lucide-react";
import {
  Ban, Bandage, CircleHelp, Cloud, CloudDrizzle, CloudFog, CloudLightning, CloudRain, CloudSnow, CloudSun, Compass,
  HeartPulse, Mountain, MountainSnow, PawPrint, ShieldAlert, ShieldBan, Sun, TriangleAlert, Users, Waves,
} from "lucide-react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

/** Line icons instead of emoji: they inherit the text colour and look the same on every phone. */
export const SOS_KIND_ICON: Record<string, LucideIcon> = {
  injured: Bandage, lost: Compass, stuck: MountainSnow, medical: HeartPulse, unsafe: ShieldAlert, unknown: CircleHelp,
};

export const ZONE_KIND_ICON: Record<string, LucideIcon> = {
  landslide: Mountain, closed_trail: Ban, restricted: ShieldBan, wildlife_core: PawPrint, flood: Waves, crowd: Users, custom: TriangleAlert,
};

/** WMO weather code (Open-Meteo) to an icon. */
export function weatherIconFor(code: number): LucideIcon {
  if (code >= 95) return CloudLightning;
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return CloudSnow;
  if (code >= 61 || (code >= 80 && code <= 82)) return CloudRain;
  if (code >= 51) return CloudDrizzle;
  if (code === 45 || code === 48) return CloudFog;
  if (code === 3) return Cloud;
  if (code === 2) return CloudSun;
  return Sun;
}

type P = { size?: number; strokeWidth?: number; className?: string };
const draw = (I: LucideIcon, p: P) => <I size={p.size ?? 18} strokeWidth={p.strokeWidth ?? 2} className={p.className} aria-hidden />;

export const SosKindIcon = ({ kind, ...p }: P & { kind: string }) => draw(SOS_KIND_ICON[kind] ?? CircleHelp, p);
export const ZoneIcon = ({ kind, ...p }: P & { kind: string }) => draw(ZONE_KIND_ICON[kind] ?? TriangleAlert, p);
export const WeatherIcon = ({ code, ...p }: P & { code: number }) => draw(weatherIconFor(code), p);
export const WarnIcon = (p: P) => draw(TriangleAlert, { size: 14, ...p });

/** SVG markup for map markers, which are plain DOM elements rather than React components. */
export function zoneIconSvg(kind: string, size = 16): string {
  return renderToStaticMarkup(createElement(ZONE_KIND_ICON[kind] ?? TriangleAlert, { size, strokeWidth: 2.4 }));
}
