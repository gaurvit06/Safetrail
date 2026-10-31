/** Sound and vibration. Audio must be unlocked by a tap (browsers block sound before a user gesture). */
let ctx: AudioContext | null = null;

export function unlockAudio() {
  try {
    ctx ??= new (window.AudioContext || (window as any).webkitAudioContext)();
    if (ctx.state === "suspended") ctx.resume();
    tone(660, 0.12, 0.05);
  } catch {
    /* no audio */
  }
}

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
