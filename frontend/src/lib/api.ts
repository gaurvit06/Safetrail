import type { Evt } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function deviceId(): string {
  try {
    let id = localStorage.getItem("st_device");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("st_device", id);
    }
    return id;
  } catch {
    return "no-storage";
  }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; token?: string | null; timeoutMs?: number } = {}): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 15000);
  try {
    const res = await fetch("/api" + path, {
      method: opts.method ?? (opts.body !== undefined ? "POST" : "GET"),
      headers: {
        "Content-Type": "application/json",
        "X-Device-Id": deviceId(),
        ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
      },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: ctrl.signal,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = await res.json();
        detail = typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) ? j.detail.map((d: any) => d.msg).join(", ") : detail;
      } catch {
        /* no body */
      }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export function isNetworkError(e: unknown): boolean {
  return !(e instanceof ApiError);
}

/** Live events: an SSE stream with automatic reconnect, plus a fetch of anything missed every 2 seconds, because
 *  free Cloudflare tunnels hold back streams and nothing would arrive. Each event is handled once, whichever way it
 *  came first. Returns a function that stops both. */
export function connectEvents(token: string, onEvent: (e: Evt) => void, onState?: (open: boolean) => void): () => void {
  let es: EventSource | null = null;
  let closed = false;
  let retry = 1000;
  let live = false;
  let after = -1;
  let timer: number | undefined;
  const seen = new Set<number>();
  const state = (on: boolean) => {
    if (on !== live) onState?.((live = on));
  };
  const deliver = (e: Evt) => {
    if (e.seq != null) {
      if (seen.has(e.seq)) return;
      seen.add(e.seq);
      if (seen.size > 1000) seen.delete(seen.values().next().value as number);
    }
    onEvent(e);
  };
  const open = () => {
    if (closed) return;
    es = new EventSource(`/api/events?token=${encodeURIComponent(token)}`);
    es.onopen = () => {
      retry = 1000;
      state(true);
    };
    es.onmessage = (m) => {
      try {
        deliver(JSON.parse(m.data));
      } catch {
        /* ignore malformed */
      }
    };
    es.onerror = () => {
      es?.close();
      if (!closed) setTimeout(open, (retry = Math.min(retry * 2, 15000)));
    };
  };
  const poll = async () => {
    try {
      const r = await api<{ seq: number; events: Evt[] }>(`/events/poll?after=${after}&token=${encodeURIComponent(token)}`, { timeoutMs: 8000 });
      after = r.seq;
      r.events.forEach(deliver);
      state(true);
    } catch {
      state(false);
    }
    if (!closed) timer = window.setTimeout(poll, 2000);
  };
  open();
  poll();
  return () => {
    closed = true;
    es?.close();
    clearTimeout(timer);
  };
}
