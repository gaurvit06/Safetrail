import { kv } from "./offline";
import type { StartBundle, TripCreated } from "./types";

/** The tourist's trip lives on the phone: token in localStorage, the full start bundle in IndexedDB (works offline). */
export type TouristSession = TripCreated & { started?: boolean };

export function getSession(): TouristSession | null {
  try {
    const raw = localStorage.getItem("st_trip");
    return raw ? (JSON.parse(raw) as TouristSession) : null;
  } catch {
    return null;
  }
}

export function setSession(s: TouristSession | null) {
  if (s) localStorage.setItem("st_trip", JSON.stringify(s));
  else localStorage.removeItem("st_trip");
}

export const getBundle = () => kv.get<StartBundle>("bundle");
export const setBundle = (b: StartBundle) => kv.set("bundle", b);

export function getRoleToken(role: "responder" | "presenter"): string | null {
  return localStorage.getItem(`st_${role}`);
}
export function setRoleToken(role: "responder" | "presenter", token: string | null) {
  if (token) localStorage.setItem(`st_${role}`, token);
  else localStorage.removeItem(`st_${role}`);
}
export function anyStaffToken(): string | null {
  return getRoleToken("presenter") || getRoleToken("responder");
}
