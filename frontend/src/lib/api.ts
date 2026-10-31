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

/** Live events over SSE with automatic reconnect. Returns a function that closes the stream. */
export function connectEvents(token: string, onEvent: (e: Evt) => void, onState?: (open: boolean) => void): () => void {
  let es: EventSource | null = null;
  let closed = false;
  let retry = 1000;
  const open = () => {
    if (closed) return;
    es = new EventSource(`/api/events?token=${encodeURIComponent(token)}`);
    es.onopen = () => {
      retry = 1000;
      onState?.(true);
    };
    es.onmessage = (m) => {
      try {
        onEvent(JSON.parse(m.data));
      } catch {
        /* ignore malformed */
      }
    };
    es.onerror = () => {
      onState?.(false);
      es?.close();
      if (!closed) setTimeout(open, (retry = Math.min(retry * 2, 15000)));
    };
  };
  open();
  return () => {
    closed = true;
    es?.close();
  };
}
