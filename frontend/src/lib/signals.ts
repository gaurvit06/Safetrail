/** Sound and vibration. Audio must be unlocked by a tap (browsers block sound before a user gesture). */
let ctx: AudioContext | null = null;

export function unlockAudio() {
  try {
    ctx ??= new (window.AudioContext || (window as any).webkitAudioContext)();
    if (ctx.state === "suspended") ctx.resume();
    tone(660, 0.12, 0.05);
    speechSynthesis.speak(new SpeechSynthesisUtterance("")); // iPhones only allow speech after one inside a tap
  } catch {
    /* no audio */
  }
}

export const soundReady = () => ctx?.state === "running";

function tone(freq: number, dur: number, vol = 0.4, at = 0, type: OscillatorType = "sine") {
  if (!ctx) return;
  const t = ctx.currentTime + at;
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, t);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(vol, t + 0.02);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g).connect(ctx.destination);
  o.start(t);
  o.stop(t + dur + 0.05);
}

export function vibrate(pattern: number | number[]) {
  try {
    navigator.vibrate?.(pattern);
  } catch {
    /* iOS has no vibration */
  }
}

/** Danger alert: two-tone siren, plus vibration where supported. */
export function dangerAlert() {
  for (let i = 0; i < 3; i++) {
    tone(880, 0.22, 0.5, i * 0.5, "square");
    tone(660, 0.22, 0.5, i * 0.5 + 0.25, "square");
  }
  vibrate([400, 200, 400, 200, 800]);
}

let siren: number | undefined;

/** The alarm for a red zone: it repeats until the person taps a button on the alert. */
export function startSiren() {
  stopSiren();
  dangerAlert();
  siren = window.setInterval(dangerAlert, 4000);
}

export function stopSiren() {
  clearInterval(siren);
  siren = undefined;
}

export const canNotify = () => "Notification" in window && "serviceWorker" in navigator;

export async function askNotify() {
  if (canNotify() && Notification.permission === "default") await Notification.requestPermission().catch(() => {});
}

/** A system notification where the phone allows one. Safari on iPhone doesn't, unless the app is on the Home Screen. */
export async function notify(title: string, body: string) {
  if (!canNotify() || Notification.permission !== "granted") return;
  try {
    const reg = await navigator.serviceWorker.ready;
    await reg.showNotification(title, { body, icon: "/icon.svg", tag: "safetrail-zone", renotify: true, requireInteraction: true } as NotificationOptions);
  } catch {
    /* the full-screen alert still shows */
  }
}

export function cautionChime() {
  tone(740, 0.18, 0.35, 0);
  tone(988, 0.25, 0.35, 0.2);
  vibrate([200, 100, 200]);
}

export function ackChime() {
  tone(523, 0.15, 0.3, 0);
  tone(659, 0.15, 0.3, 0.16);
  tone(784, 0.3, 0.3, 0.32);
  vibrate([120, 80, 120]);
}

/** Projector cheer when help is accepted: a short "ta-da" and a burst of synthesised applause. */
export function cheer() {
  if (!ctx) return;
  [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.18, 0.25, i * 0.09, "triangle"));
  [523, 659, 784].forEach((f) => tone(f, 0.9, 0.18, 0.4, "triangle"));
  try {
    const len = Math.floor(ctx.sampleRate * 0.03);
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3);
    for (let k = 0; k < 70; k++) {
      const src = ctx.createBufferSource();
      const bp = ctx.createBiquadFilter();
      const g = ctx.createGain();
      src.buffer = buf;
      bp.type = "bandpass";
      bp.frequency.value = 1200 + Math.random() * 1800;
      g.gain.value = 0.08 + Math.random() * 0.12;
      src.connect(bp).connect(g).connect(ctx.destination);
      src.start(ctx.currentTime + 0.35 + Math.random() * 1.6);
    }
  } catch {
    /* applause is a nice-to-have */
  }
}

/** Distress whistle: three loud blasts (the international distress signal), repeated. */
export function whistleBlasts() {
  for (let i = 0; i < 3; i++) tone(3150, 0.45, 0.9, i * 0.7, "square");
}

export function speak(text: string, lang: string) {
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang === "hi" ? "hi-IN" : "en-IN";
    u.rate = 0.9;
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  } catch {
    /* no speech */
  }
}
