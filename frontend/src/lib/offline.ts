import { openDB, type IDBPDatabase } from "idb";
import { api, ApiError } from "./api";

/** Offline storage (SPEC 5.6, 7): the SOS queue, queued pings and the trip bundle live in IndexedDB. */
let dbp: Promise<IDBPDatabase> | null = null;
function db() {
  dbp ??= openDB("safetrail", 1, {
    upgrade(d) {
      d.createObjectStore("sos", { keyPath: "client_id" });
      d.createObjectStore("pings", { autoIncrement: true });
      d.createObjectStore("kv");
    },
  });
  return dbp;
}

export const kv = {
  get: async <T = any>(k: string): Promise<T | undefined> => (await db()).get("kv", k),
  set: async (k: string, v: unknown) => (await db()).put("kv", v, k),
  del: async (k: string) => (await db()).delete("kv", k),
};

export type QueuedSos = {
  client_id: string;
  trip_id: string;
  kind: string;
  people_bucket: string;
  note: string | null;
  lat: number;
  lon: number;
  accuracy_m: number;
  created_at_device: number;
  channel: "data" | "sms";
  status: "queued" | "received" | "failed" | "cancelled";
  received_at?: number;
  incident_id?: number;
  incident_status?: string | null;
  accepted_at?: number | null;
  team?: string | null;
  sms_offered?: boolean;
  last_error?: string;
};

export const sosStore = {
  put: async (s: QueuedSos) => (await db()).put("sos", s),
  all: async (): Promise<QueuedSos[]> => (await db()).getAll("sos"),
  get: async (id: string): Promise<QueuedSos | undefined> => (await db()).get("sos", id),
};

export type QueuedPing = { lat: number; lon: number; accuracy_m: number; ts_device: number; source: string };

export const pingQueue = {
  add: async (p: QueuedPing) => (await db()).add("pings", p),
  take: async (limit = 200): Promise<{ keys: IDBValidKey[]; items: QueuedPing[] }> => {
    const d = await db();
    const keys = (await d.getAllKeys("pings")).slice(0, limit);
    const items = await Promise.all(keys.map((k) => d.get("pings", k)));
    return { keys, items: items.filter(Boolean) as QueuedPing[] };
  },
  remove: async (keys: IDBValidKey[]) => {
    const tx = (await db()).transaction("pings", "readwrite");
    await Promise.all(keys.map((k) => tx.store.delete(k)));
    await tx.done;
  },
  count: async () => (await db()).count("pings"),
};

type Listener = () => void;
const listeners = new Set<Listener>();
export function onQueueChange(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
const emit = () => listeners.forEach((f) => f());

/** Send queued SOS first (oldest first), then queued pings. Delete an SOS only after the server confirms it. */
export async function flush(tripId: string, token: string): Promise<{ sent: number; online: boolean }> {
  let sent = 0;
  try {
    const all = (await sosStore.all()).filter((s) => s.status === "queued").sort((a, b) => a.created_at_device - b.created_at_device);
    for (const s of all) {
      try {
        const r = await api<{ received_at: number; incident_id: number; duplicate: boolean }>("/sos", {
          token,
          body: { client_id: s.client_id, trip_id: s.trip_id, kind: s.kind, people_bucket: s.people_bucket, note: s.note, lat: s.lat, lon: s.lon, accuracy_m: s.accuracy_m, created_at_device: s.created_at_device, channel: s.channel },
        });
        await sosStore.put({ ...s, status: "received", received_at: r.received_at, incident_id: r.incident_id });
        sent += 1;
        emit();
      } catch (e) {
        if (e instanceof ApiError && e.status >= 400 && e.status < 500) {
          await sosStore.put({ ...s, status: "failed", last_error: e.message });
          emit();
        } else throw e;
      }
    }
    const { keys, items } = await pingQueue.take();
    if (items.length) {
      await api(`/trips/${tripId}/pings`, { token, body: items });
      await pingQueue.remove(keys);
      emit();
    }
    return { sent, online: true };
  } catch {
    return { sent, online: false };
  }
}

export async function queueSos(s: QueuedSos) {
  await sosStore.put(s);
  emit();
}
