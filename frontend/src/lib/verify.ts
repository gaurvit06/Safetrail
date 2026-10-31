import * as ed from "@noble/ed25519";

/** Verify the signed, hash-chained timeline in the browser (SPEC 5.14, CONTRACT_CHANGES 8). */
export type LogEntry = {
  seq: number;
  ts_server: number;
  type: string;
  entity_id: string;
  payload: unknown;
  payload_hash: string;
  prev_hash: string;
  hash: string;
  signature: string;
};

const hex = (b: ArrayBuffer | Uint8Array) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
const unhex = (s: string) => new Uint8Array(s.match(/.{2}/g)!.map((x) => parseInt(x, 16)));
const unb64 = (s: string) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

async function sha256hex(text: string): Promise<string> {
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)));
}

export type EntryCheck = { seq: number; hashOk: boolean; sigOk: boolean };

export async function verifyEntries(entries: LogEntry[], pubkeyB64: string): Promise<EntryCheck[]> {
  const pub = unb64(pubkeyB64);
  const out: EntryCheck[] = [];
  for (const e of entries) {
    const h = await sha256hex(`${e.prev_hash}|${e.type}|${e.entity_id}|${e.payload_hash}|${e.ts_server.toFixed(6)}`);
    let sigOk = false;
    try {
      sigOk = await ed.verifyAsync(unhex(e.signature), unhex(e.hash), pub);
    } catch {
      sigOk = false;
    }
    out.push({ seq: e.seq, hashOk: h === e.hash, sigOk });
  }
  return out;
}

export async function verifyPassOffline(qr: string, pubkeyB64: string): Promise<{ valid: boolean; reason: string; payload?: any }> {
  try {
    const [b, s] = qr.trim().split(".");
    const dec = (x: string) => Uint8Array.from(atob(x.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (x.length % 4)) % 4)), (c) => c.charCodeAt(0));
    const body = dec(b);
    const payload = JSON.parse(new TextDecoder().decode(body));
    const ok = await ed.verifyAsync(dec(s), body, unb64(pubkeyB64));
    if (!ok) return { valid: false, reason: "forged", payload };
    if (Date.now() / 1000 > payload.valid_to) return { valid: false, reason: "expired", payload };
    return { valid: true, reason: "ok", payload };
  } catch {
    return { valid: false, reason: "unreadable" };
  }
}
