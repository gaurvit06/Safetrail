import { QRCodeSVG } from "qrcode.react";
import { ArrowUp, Copy, Megaphone, Mic, Navigation, Share2, Sun, Volume2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { ago, clock, duration, riskText } from "../lib/format";
import { SosKindIcon, WarnIcon, WeatherIcon, ZoneIcon } from "./icons";
import { bearing, cardinal, fmtDistance, haversine } from "../lib/geo";
import { useT } from "../lib/i18n";
import type { QueuedSos } from "../lib/offline";
import { speak, vibrate, whistleBlasts } from "../lib/signals";
import type { HelpPoint, PackContent, PassPayload, PermitCard, PermitInfo, Segment, StartBundle, Weather, Zone } from "../lib/types";
import { HoldButton, Overlay, SheetHeader, SourceTag, Step } from "./ui";

export type Fix = { lat: number; lon: number; accuracy: number };

export function zoneText(z: Zone, lang: string, b: StartBundle | null) {
  const a = z.advisories?.[lang] ?? z.advisories?.en;
  if (a) return a;
  const t = b?.templates.zone[z.kind] ?? b?.templates.zone.custom;
  return { title: t?.title ?? z.kind, body: (t?.body ?? "").replace("{segment}", z.segment_name || "this area"), action: t?.action ?? "", source: "template" };
}

/* ---------------------------------------------------------------- zone alert (full screen) */
export function ZoneAlert({ zone, bundle, onWayBack, onClose, notPermitted }: { zone: Zone; bundle: StartBundle | null; onWayBack: () => void; onClose: () => void; notPermitted?: string }) {
  const { t, lang } = useT();
  const a = zoneText(zone, lang, bundle);
  const warn = !notPermitted && (zone.kind === "crowd" || zone.severity === "warn");
  return (
    <div className={`fixed inset-0 z-[60] flex flex-col px-6 pb-8 pt-14 text-white ${warn ? "bg-caution" : "bg-danger"}`} role="alertdialog">
      <ZoneIcon kind={zone.kind} size={72} strokeWidth={1.75} />
      {notPermitted && <p className="mt-4 rounded-xl bg-white px-3 py-2 text-lg font-extrabold text-danger">{t("not_permitted")} · {notPermitted}</p>}
      <h1 className="mt-6 text-6xl leading-none">{a.title}</h1>
      <p className="mt-4 text-xl leading-snug">{a.body}</p>
      {a.action && <p className="mt-4 rounded-2xl bg-white/15 p-4 text-xl font-bold">→ {a.action}</p>}
      {zone.simulated && <p className="mt-3 text-sm opacity-80">Simulated demo zone</p>}
      <div className="mt-auto space-y-3">
        <button className="btn w-full bg-white text-lg text-ink" onClick={onWayBack}><Navigation size={20} /> {t("show_way_back")}</button>
        <button className="btn w-full border-2 border-white/70 text-lg text-white" onClick={onClose}>{t("i_understand")}</button>
        <p className="text-center text-xs opacity-80">{a.source === "ai" ? t("ai_translated") + " · " + t("receipt") + " ✓" : t("standard_text")}</p>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- "Are you safe?" */
export function SafetyCheckPrompt({ message, onAnswer }: { message: string; onAnswer: (a: "safe" | "need_help") => void }) {
  const { t } = useT();
  return (
    <div className="fixed inset-0 z-[65] flex flex-col bg-ink px-6 pb-8 pt-16 text-white">
      <p className="text-sm font-semibold uppercase tracking-wide opacity-70">SafeTrail · Control room</p>
      <h1 className="mt-4 text-4xl font-extrabold leading-tight">{message || t("are_you_safe")}</h1>
      <div className="mt-auto grid gap-4">
        <button className="btn-safe min-h-[96px] text-2xl" onClick={() => onAnswer("safe")}>{t("im_safe")}</button>
        <button className="btn-danger min-h-[96px] text-2xl" onClick={() => onAnswer("need_help")}>{t("need_help")}</button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- SOS flow */
const KINDS = ["injured", "lost", "stuck", "medical", "unsafe"] as const;

export function SosFlow({ bundle, preset, onSend, onClose }: { bundle: StartBundle | null; preset?: string; onSend: (kind: string, people: string, note: string) => void; onClose: () => void }) {
  const { t, lang } = useT();
  const [kind, setKind] = useState<string | null>(preset ?? null);
  const [people, setPeople] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [listening, setListening] = useState(false);
  const step = !kind ? 0 : !people ? 1 : 2;
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  const listen = () => {
    if (!SR) return;
    const rec = new SR();
    rec.lang = lang === "hi" ? "hi-IN" : "en-IN";
    rec.interimResults = false;
    rec.onresult = (e: any) => setNote((n) => (n ? n + " " : "") + e.results[0][0].transcript);
    rec.onend = () => setListening(false);
    setListening(true);
    rec.start();
  };
  const kindLabel = (k: string) => bundle?.templates.kind[k] ?? k;
  return (
    <div className="fixed inset-0 z-[55] flex flex-col bg-white">
      <div className="flex items-center justify-between bg-danger px-5 py-4 text-white">
        <h1 className="text-xl font-bold">SOS</h1>
        <button onClick={onClose} className="grid h-10 w-10 place-items-center rounded-full bg-white/20" aria-label={t("close")}><X /></button>
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-5">
        <h2 className="text-lg font-bold">{t("what_happened")}</h2>
        <div className="mt-3 grid grid-cols-2 gap-3">
          {KINDS.map((k) => (
            <button key={k} onClick={() => { vibrate(20); setKind(k); }} className={`tile ${kind === k ? "tile-on" : ""} ${k === "unsafe" ? "col-span-2" : ""}`}>
              <SosKindIcon kind={k} size={30} strokeWidth={1.75} />{kindLabel(k)}
            </button>
          ))}
        </div>
        {step >= 1 && (
          <>
            <h2 className="mt-6 text-lg font-bold">{t("how_many")}</h2>
            <div className="mt-3 grid grid-cols-3 gap-3">
              {[["1", t("just_me")], ["2-5", t("two_five")], ["6+", t("six_plus")]].map(([v, l]) => (
                <button key={v} onClick={() => { vibrate(20); setPeople(v); }} className={`tile ${people === v ? "tile-on" : ""}`}>{l}</button>
              ))}
            </div>
          </>
        )}
        {step >= 2 && (
          <>
            <h2 className="mt-6 text-lg font-bold">{t("anything_else")}</h2>
            <div className="mt-3 flex gap-2">
              <textarea className="input min-h-[96px] py-3" maxLength={280} placeholder={t("note_ph")} value={note} onChange={(e) => setNote(e.target.value)} />
              {SR && <button onClick={listen} className={`btn-ghost w-14 shrink-0 px-0 ${listening ? "animate-flash text-danger" : ""}`} aria-label={t("speak_note")}><Mic /></button>}
            </div>
          </>
        )}
      </div>
      <div className="border-t border-line p-4">
        <button className="btn-danger w-full text-xl" style={{ minHeight: 64 }} disabled={!kind || !people} onClick={() => onSend(kind!, people!, note.trim())}>{t("send_sos")}</button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- SOS status tracker */
export function SosStatus({ sos, label, smsNumber, offerAfterS, onCancel, onClose, groupMessage }: { sos: QueuedSos; label: string; smsNumber: string | null; offerAfterS: number; onCancel: () => void; onClose: () => void; groupMessage?: string | null }) {
  const { t } = useT();
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => {
    const i = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(i);
  }, []);
  const received = sos.status === "received";
  const acked = !!sos.accepted_at || sos.incident_status === "accepted" || sos.incident_status === "en_route" || sos.incident_status === "resolved";
  const waiting = now - sos.created_at_device;
  const kindCode = { injured: "INJ", lost: "LOST", stuck: "STK", medical: "MED", unsafe: "UNS" }[sos.kind] ?? "SOS";
  const hhmm = new Date(sos.created_at_device * 1000).toTimeString().slice(0, 5).replace(":", "");
  const sms = `SOS ${label} ${sos.lat.toFixed(5)} ${sos.lon.toFixed(5)} ${kindCode} ${sos.people_bucket} ${hhmm} ${sos.client_id.slice(0, 8)}`;
  return (
    <Overlay onClose={onClose}>
      <SheetHeader title={t("sos_title")} onClose={onClose} sub={`${label} · ${clock(sos.created_at_device)}`} />
      <div className="px-5 py-5">
        <Step done label={t("st_saved")} sub={clock(sos.created_at_device)} />
        <Step done={received} active={!received} label={received ? t("st_received") : t("st_sending")} sub={received ? `${clock(sos.received_at)} · ${t("delay")} ${duration((sos.received_at ?? 0) - sos.created_at_device)}` : `${t("st_pending")} (${duration(waiting)})`} />
        <Step done={acked} active={received && !acked} label={t("st_ack")} sub={acked ? `${sos.team ?? ""} ${sos.accepted_at ? "· " + clock(sos.accepted_at) : ""}` : undefined} last />
        {groupMessage && <p className="mt-2 rounded-xl bg-info/10 p-3 text-info">{groupMessage}</p>}
        {!received && waiting > offerAfterS && smsNumber && (
          <div className="mt-4 rounded-2xl border-2 border-caution bg-caution/5 p-4">
            <p className="font-bold">{t("send_sms")}</p>
            <p className="mt-1 text-sm text-muted">{t("sms_explain")}</p>
            <p className="mt-2 break-all rounded-lg bg-white p-2 font-mono text-sm">{sms}</p>
            <a className="btn-primary mt-3 w-full" href={`sms:${smsNumber}?&body=${encodeURIComponent(sms)}`}>{t("send_sms")}</a>
          </div>
        )}
        {!acked && (
          <HoldButton onDone={onCancel} label={t("cancel_sos")} ringColor="#5F6368" className="btn-ghost mt-6 w-full text-muted">
            {t("cancel_sos")}
          </HoldButton>
        )}
      </div>
    </Overlay>
  );
}

/* ---------------------------------------------------------------- safety pack */
export function PackSheet({ pack, source, helpPoints, segments, currentSegment, me, initialTab, onGuide, onShowLocal, onClose }: { pack: PackContent; source: string; helpPoints: HelpPoint[]; segments: Segment[]; currentSegment: string; me: Fix | null; initialTab?: number; onGuide: (hp: HelpPoint) => void; onShowLocal: (p: { local: string; user: string }) => void; onClose: () => void }) {
  const { t, lang } = useT();
  const [tab, setTab] = useState(initialTab ?? 0);
  const tabs = [t("briefing"), t("phrases"), t("if_cards"), t("help_points")];
  const IF_TITLE: Record<string, string> = { lost: "If you are lost", injured: "If someone is injured", blocked: "If the path is blocked", crowd: "If the crowd is too dense", wildlife: "If you see wild animals" };
  return (
    <Overlay onClose={onClose}>
      <SheetHeader title={t("safety_pack")} onClose={onClose} />
      <div className="flex gap-1 overflow-x-auto border-b border-line px-3 py-2">
        {tabs.map((x, i) => <button key={x} onClick={() => setTab(i)} className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold ${tab === i ? "bg-ink text-white" : "text-muted"}`}>{x}</button>)}
      </div>
      <div className="space-y-3 px-5 py-4">
        {tab === 0 && (
          <>
            {pack.briefing.map((b, i) => <p key={i} className="flex gap-2"><span className="font-bold text-brand">{i + 1}.</span>{b}</p>)}
            {pack.altitude_signs.symptoms.length > 0 && (
              <div className="card mt-3 p-4">
                <p className="font-bold">Altitude sickness</p>
                <ul className="mt-2 list-disc pl-5 text-sm">{pack.altitude_signs.symptoms.map((s) => <li key={s}>{s}</li>)}</ul>
                <p className="mt-2 font-semibold">Do now</p>
                <ul className="list-disc pl-5 text-sm">{pack.altitude_signs.do_now.map((s) => <li key={s}>{s}</li>)}</ul>
              </div>
            )}
            {pack.segments.some((sg) => sg.risks.length > 0) && <p className="pt-2 font-bold">{t("section_risks")}</p>}
            {pack.segments.filter((sg) => sg.risks.length > 0).map((sg) => {
              const name = segments.find((x) => x.id === sg.segment_id)?.name ?? sg.segment_id;
              const help = helpPoints.find((hp) => hp.id === sg.nearest_help_id);
              const here = name === currentSegment;
              return (
                <div key={sg.segment_id} className={`card p-4 ${here ? "border-2 border-brand" : ""}`}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-bold">{name}</p>
                    {here && <span className="chip shrink-0 bg-brand/10 text-brand">{t("you_are_here")}</span>}
                  </div>
                  <ul className="mt-2 list-disc pl-5 text-sm">{sg.risks.map((r) => <li key={r}>{r}</li>)}</ul>
                  {help && <button className="mt-2 flex items-center gap-1 text-left text-sm font-semibold text-brand" onClick={() => onGuide(help)}><Navigation size={16} /> {t("nearest_help")}: {help.name}</button>}
                </div>
              );
            })}
          </>
        )}
        {tab === 1 && pack.phrasebook.map((p) => (
          <div key={p.key} className="card flex items-center gap-3 p-3">
            <button className="flex-1 text-left" onClick={() => onShowLocal({ local: p.local_text, user: p.user_text })}>
              <p className="text-lg font-bold">{p.local_text}</p>
              <p className="text-sm text-muted">{p.user_text}</p>
            </button>
            <button className="btn-ghost w-12 px-0" onClick={() => speak(p.local_text, "hi")} aria-label="Speak"><Volume2 size={20} /></button>
          </div>
        ))}
        {tab === 1 && <p className="text-center text-xs text-muted">{t("tap_to_flip")} · {t("show_local")}</p>}
        {tab === 2 && pack.if_cards.map((c) => (
          <div key={c.key} className="card p-4">
            <p className="font-bold">{IF_TITLE[c.key] ?? c.key}</p>
            <ol className="mt-2 list-decimal space-y-1 pl-5">{c.steps.map((s) => <li key={s}>{s}</li>)}</ol>
          </div>
        ))}
        {tab === 3 && [...helpPoints].sort((a, b) => (me ? haversine(me.lat, me.lon, a.lat, a.lon) - haversine(me.lat, me.lon, b.lat, b.lon) : 0)).map((hp) => (
          <div key={hp.id} className="card flex items-center justify-between p-3">
            <div>
              <p className="font-bold">{hp.name}</p>
              <p className="text-sm text-muted">{hp.kind}{me ? ` · ${fmtDistance(haversine(me.lat, me.lon, hp.lat, hp.lon))} ${cardinal(bearing(me.lat, me.lon, hp.lat, hp.lon))}` : ""}</p>
              <span className={`chip mt-1 ${hp.source === "osm" ? "bg-safe/10 text-safe" : "bg-black/5 text-muted"}`}>{hp.source === "osm" ? "OpenStreetMap" : "simulated"}</span>
            </div>
            <button className="btn-ghost" onClick={() => onGuide(hp)}><Navigation size={18} /> {t("guide_me")}</button>
          </div>
        ))}
        <div className="pt-2 text-center"><SourceTag source={source} /></div>
      </div>
    </Overlay>
  );
}

/* ---------------------------------------------------------------- show to a local */
export function PhraseShow({ local, user, onClose }: { local: string; user: string; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[70] flex flex-col items-center justify-center bg-white px-6 text-center" onClick={onClose}>
      <p className="text-[clamp(36px,9vw,72px)] font-extrabold leading-tight">{local}</p>
      <p className="mt-6 text-xl text-muted">{user}</p>
      <button className="btn-ghost mt-10" onClick={(e) => { e.stopPropagation(); speak(local, "hi"); }}><Volume2 /> Speak</button>
      <p className="absolute bottom-8 text-sm text-muted">Tap anywhere to close</p>
    </div>
  );
}

/* ---------------------------------------------------------------- signal tools */
export function SignalSheet({ me, segment, nearestHelp, emergency, onStrobe, onClose }: { me: Fix | null; segment: string; nearestHelp: string; emergency: string; onStrobe: () => void; onClose: () => void }) {
  const { t } = useT();
  const [whistling, setWhistling] = useState(false);
  const timer = useRef<number>();
  useEffect(() => () => clearInterval(timer.current), []);
  const toggleWhistle = () => {
    if (whistling) {
      clearInterval(timer.current);
      setWhistling(false);
    } else {
      whistleBlasts();
      timer.current = window.setInterval(whistleBlasts, 4000);
      setWhistling(true);
    }
  };
  const locText = me ? `I am at latitude ${me.lat.toFixed(5)}, longitude ${me.lon.toFixed(5)}${segment ? `, near ${segment}` : ""}${nearestHelp ? `. Nearest help point: ${nearestHelp}` : ""}.` : "Location not available yet.";
  return (
    <Overlay onClose={onClose}>
      <SheetHeader title={t("signal")} onClose={onClose} />
      <div className="space-y-4 px-5 py-4">
        <button onClick={toggleWhistle} className={`card flex w-full items-center gap-4 p-4 text-left ${whistling ? "border-2 border-danger bg-danger/5" : ""}`}>
          <Megaphone className={whistling ? "animate-flash text-danger" : "text-ink"} size={32} />
          <div><p className="text-lg font-bold">{whistling ? t("stop") : t("whistle")}</p><p className="text-sm text-muted">{t("whistle_explain")}</p></div>
        </button>
        <button onClick={onStrobe} className="card flex w-full items-center gap-4 p-4 text-left">
          <Sun size={32} />
          <div><p className="text-lg font-bold">{t("strobe")}</p><p className="text-sm text-muted">{t("strobe_explain")}</p></div>
        </button>
        <div className="card p-4">
          <p className="font-bold">{t("read_to_operator")} ({emergency})</p>
          <p className="mt-2 rounded-lg bg-black/5 p-3 font-mono text-sm">{locText}</p>
          <div className="mt-3 flex gap-2">
            <button className="btn-ghost flex-1" onClick={() => navigator.clipboard?.writeText(locText)}><Copy size={16} /> {t("copy")}</button>
            {"share" in navigator && <button className="btn-ghost flex-1" onClick={() => navigator.share({ text: locText }).catch(() => {})}><Share2 size={16} /> {t("share")}</button>}
            <a className="btn-danger flex-1" href={`tel:${emergency}`}>Call {emergency}</a>
          </div>
        </div>
      </div>
    </Overlay>
  );
}

export function Strobe({ onClose }: { onClose: () => void }) {
  return (
    <div className="strobe fixed inset-0 z-[80] flex items-end justify-center pb-10" onClick={onClose}>
      <span className="rounded-full bg-black/60 px-4 py-2 text-sm font-semibold text-white">Tap to stop</span>
    </div>
  );
}

/* ---------------------------------------------------------------- pass + family */
export function PassSheet({ qr, label, pass, tripId, token, revoked, onUpgraded, onClose }: {
  qr: string; label: string; pass: PassPayload | null; tripId: string; token: string; revoked?: boolean;
  onUpgraded: (qr: string, pass: PassPayload) => void; onClose: () => void;
}) {
  const { t } = useT();
  const linked = pass && pass.kyc_level !== "demo";
  return (
    <Overlay onClose={onClose}>
      <SheetHeader title={t("pass")} onClose={onClose} sub="Show this at checkpoints. It works offline." />
      <div className="flex flex-col items-center px-5 py-6">
        {revoked && <p className="mb-3 w-full rounded-xl bg-danger p-3 text-center font-semibold text-white">{t("pass_revoked")}</p>}
        <div className={`rounded-2xl bg-white p-3 shadow-float ${revoked ? "opacity-30" : ""}`}><QRCodeSVG value={qr} size={240} level="M" /></div>
        <p className="mt-4 font-mono text-2xl font-bold">{label}</p>
        {pass?.valid_to && <p className="text-sm text-muted">Valid until {new Date(pass.valid_to * 1000).toLocaleString()}</p>}
        {linked ? (
          <p className="mt-2 text-center text-sm font-semibold text-safe">✓ {pass!.permit_type} · …{pass!.id_last4}{pass!.kyc_level === "self_declared" ? " (self-declared)" : ""}</p>
        ) : (
          <p className="mt-2 text-xs text-muted">Signed trip pass (demo).</p>
        )}
      </div>
      <div className="px-5 pb-6">
        {!linked && !revoked && pass && <PermitLink tripId={tripId} token={token} passId={pass.pass_id} onUpgraded={onUpgraded} />}
        {linked && <PermitCardView tripId={tripId} token={token} />}
      </div>
    </Overlay>
  );
}

const ID_TYPES: Record<"foreign" | "indian", [string, string][]> = {
  foreign: [["evisa", "e-Visa"], ["visa", "Visa"], ["passport", "Passport"]],
  indian: [["yatra", "Yatra registration"], ["eilp", "e-ILP"], ["digilocker", "DigiLocker permit"], ["passport", "Passport"], ["voter", "Voter ID"], ["aadhaar_masked", "Aadhaar (last 4 only)"]],
};

/** Phase 2 (SPEC 17.2), simulated registry: look up a permit, show what it covers, add it to the signed pass. */
function PermitLink({ tripId, token, passId, onUpgraded }: { tripId: string; token: string; passId: string; onUpgraded: (qr: string, pass: PassPayload) => void }) {
  const { t } = useT();
  const [visitor, setVisitor] = useState<"foreign" | "indian">("foreign");
  const [idType, setIdType] = useState("evisa");
  const [num, setNum] = useState("");
  const [busy, setBusy] = useState(false);
  const [found, setFound] = useState<PermitInfo | null>(null);
  const [msg, setMsg] = useState("");
  const day = (ts: number) => new Date(ts * 1000).toLocaleDateString();
  const check = async () => {
    setBusy(true);
    setMsg("");
    setFound(null);
    try {
      const r = await api<{ found: boolean; reason?: string; permit?: PermitInfo }>("/permits/lookup", { token, body: { trip_id: tripId, id_type: idType, id_number: num } });
      if (r.found && r.permit) setFound(r.permit);
      else setMsg(r.reason === "too_many_lookups" ? t("too_many_lookups") : t("permit_not_found"));
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setNum(""); // the number leaves the form as soon as it has been checked
      setBusy(false);
    }
  };
  const add = async () => {
    if (!found) return;
    setBusy(true);
    try {
      const r = await api<{ pass_qr: string; pass: PassPayload }>(`/passes/${passId}/upgrade`, { token, body: { trip_id: tripId, record_id: found.record_id } });
      onUpgraded(r.pass_qr, r.pass);
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="card space-y-3 p-4">
      <div>
        <p className="font-bold">{t("permit_title")}</p>
        <p className="text-xs font-semibold text-caution">{t("permit_sub")}</p>
        <p className="mt-1 text-sm text-muted">{t("permit_explain")}</p>
      </div>
      <div className="flex gap-2">
        {(["foreign", "indian"] as const).map((v) => (
          <button key={v} onClick={() => { setVisitor(v); setIdType(ID_TYPES[v][0][0]); setFound(null); setMsg(""); }} className={`chip border px-3 py-1.5 text-sm ${visitor === v ? "border-brand bg-brand text-white" : "border-line"}`}>{t(v === "foreign" ? "visitor_foreign" : "visitor_indian")}</button>
        ))}
      </div>
      <label className="block"><span className="label">{t("id_type")}</span>
        <select className="input mt-1" value={idType} onChange={(e) => { setIdType(e.target.value); setFound(null); }}>
          {ID_TYPES[visitor].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </label>
      <label className="block"><span className="label">{t("id_number")}</span>
        <input className="input mt-1 font-mono uppercase" autoComplete="off" spellCheck={false} maxLength={40} value={num} onChange={(e) => setNum(e.target.value)} />
      </label>
      {idType === "aadhaar_masked" && <p className="text-xs text-muted">{t("aadhaar_note")}</p>}
      <button className="btn-primary w-full" disabled={busy || num.trim().length < 4} onClick={check}>{t("permit_check")}</button>
      <p className="text-xs text-muted">{t("permit_privacy")}</p>
      {msg && <p className="text-sm font-semibold text-danger">{msg}</p>}
      {found && (
        <div className={`rounded-xl p-3 text-sm ${found.expired || !found.covers_route ? "bg-danger/10" : "bg-safe/10"}`}>
          <p className="font-bold">{found.permit_type} · …{found.id_last4}</p>
          <p>{t("permit_valid", { from: day(found.valid_from), to: day(found.valid_to) })}</p>
          <p>{t("permit_zones")}: {found.permitted_zones.length ? found.permitted_zones.join(", ") : t("permit_none")}</p>
          <p className="text-xs text-muted">{found.verified_via === "manual" ? "Self-declared" : "Simulated registry"}</p>
          {found.expired && <p className="mt-1 font-semibold text-danger">{t("permit_expired")}</p>}
          {!found.expired && !found.covers_route && <p className="mt-1 font-semibold text-danger">{t("permit_other_route")}</p>}
          {!found.expired && <button className="btn-primary mt-3 w-full" disabled={busy} onClick={add}>{t("permit_add")}</button>}
        </div>
      )}
    </div>
  );
}

/** "What your permit allows", written by the AI through Prune (or the official text as standard text). */
function PermitCardView({ tripId, token }: { tripId: string; token: string }) {
  const { t } = useT();
  const [card, setCard] = useState<PermitCard | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    api<PermitCard>(`/trips/${tripId}/permit-card`, { token }).then(setCard).catch(() => setErr(true));
  }, [tripId, token]);
  if (err) return null;
  if (!card) return <p className="text-center text-sm text-muted">…</p>;
  const c = card.content;
  const list = (title: string, xs: string[], cls: string) => xs.length > 0 && (
    <div><p className={`text-xs font-bold uppercase ${cls}`}>{title}</p><ul className="ml-4 list-disc text-sm">{xs.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
  );
  return (
    <div className="card space-y-2 p-4">
      <p className="font-bold">{t("permit_card")}: {c.title}</p>
      {list(t("permit_allows"), c.allows, "text-safe")}
      {list(t("permit_not_allowed"), c.not_allowed, "text-danger")}
      {list(t("permit_carry"), c.carry, "text-muted")}
      <p className="text-xs text-muted">{card.source === "ai" ? t("ai_translated") : t("standard_text")} · Simulated permit text</p>
    </div>
  );
}

export function FamilySheet({ url, token, tripId, touristToken, onClose }: { url: string; token: string; tripId: string; touristToken: string; onClose: () => void }) {
  const { t } = useT();
  const [preview, setPreview] = useState<any>(null);
  const [revoked, setRevoked] = useState(false);
  useEffect(() => {
    api(`/family/${token}`).then(setPreview).catch(() => setPreview(null));
  }, [token]);
  return (
    <Overlay onClose={onClose}>
      <SheetHeader title={t("family_title")} onClose={onClose} sub={t("family_explain")} />
      <div className="space-y-4 px-5 py-4">
        <p className="break-all rounded-xl bg-black/5 p-3 font-mono text-sm">{url}</p>
        <div className="flex gap-2">
          {"share" in navigator && <button className="btn-primary flex-1" onClick={() => navigator.share({ title: "SafeTrail", text: "Follow my trip status", url }).catch(() => {})}><Share2 size={16} /> {t("share")}</button>}
          <button className="btn-ghost flex-1" onClick={() => navigator.clipboard?.writeText(url)}><Copy size={16} /> {t("copy")}</button>
          <a className="btn-ghost flex-1" href={`https://wa.me/?text=${encodeURIComponent("Follow my trip status: " + url)}`} target="_blank" rel="noreferrer">WhatsApp</a>
        </div>
        <div className="card p-4">
          <p className="label">{t("family_preview")}</p>
          {preview ? (
            <div className="mt-2"><p className="text-lg font-bold">{preview.first_name}</p><p className="text-sm text-muted">{preview.route_name} · {preview.status.replace("_", " ")} · last check-in {preview.last_check_in_ago_s == null ? "not yet" : ago(Date.now() / 1000 - preview.last_check_in_ago_s)}</p><p className="mt-1 text-xs text-muted">No map. No coordinates.</p></div>
          ) : <p className="mt-2 text-sm text-muted">{revoked ? "Link turned off." : "Preview unavailable offline."}</p>}
        </div>
        {!revoked && <button className="btn-ghost w-full text-danger" onClick={() => api(`/family/${tripId}/revoke`, { token: touristToken, body: {} }).then(() => { setRevoked(true); setPreview(null); })}>{t("revoke")}</button>}
      </div>
    </Overlay>
  );
}

/* ---------------------------------------------------------------- live weather along the route */
export function WeatherSheet({ weather, templates, current, online, onClose }: { weather: Weather | null; templates?: Record<string, string>; current: string; online: boolean; onClose: () => void }) {
  const { t } = useT();
  const sub = weather?.fetched_at ? `${weather.stale || !online ? t("last_update") : t("updated")} ${ago(weather.fetched_at)} · ${weather.source ?? ""}` : undefined;
  return (
    <Overlay onClose={onClose}>
      <SheetHeader title={t("weather_title")} sub={sub} onClose={onClose} />
      <div className="space-y-3 px-5 py-4">
        {!weather?.available && <p className="text-muted">{t("weather_unavailable")}</p>}
        {weather?.sections.map((s) => (
          <div key={s.segment_id} className={`card p-3 ${s.name === current ? "border-2 border-brand" : ""}`}>
            <div className="flex items-center justify-between gap-2">
              <p className="flex items-center gap-1.5 font-bold"><WeatherIcon code={s.now.code} size={18} /> {s.name}</p>
              <span className="font-mono text-xl font-bold">{Math.round(s.now.temp_c)}°</span>
            </div>
            <p className="text-sm text-muted">
              {s.now.desc}{s.elevation_m ? ` · ${Math.round(s.elevation_m)} m` : ""} · {t("next_12h")}: {s.next12h.temp_min != null ? Math.round(s.next12h.temp_min) : "–"}° to {s.next12h.temp_max != null ? Math.round(s.next12h.temp_max) : "–"}°, {s.next12h.rain_12h} mm, {s.next12h.gust_max} km/h
            </p>
            {s.risks.map((r) => <p key={r.key} className={`mt-1 text-sm font-semibold ${r.level === "danger" ? "text-danger" : "text-caution"}`}><WarnIcon className="-mt-0.5 mr-1 inline" />{riskText(templates, r.key, r.value)}</p>)}
            {s.name === current && <p className="mt-1 text-xs font-semibold text-brand">{t("you_are_here")}</p>}
          </div>
        ))}
        {weather?.available && <p className="text-center text-xs text-muted">{weather.attribution}</p>}
      </div>
    </Overlay>
  );
}

/* ---------------------------------------------------------------- guide to a help point (compass) */
export function useHeading(enabled: boolean): number | null {
  const [h, setH] = useState<number | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const on = (e: any) => {
      const v = e.webkitCompassHeading ?? (e.absolute && e.alpha != null ? 360 - e.alpha : null);
      if (v != null) setH(v);
    };
    window.addEventListener("deviceorientationabsolute", on as any);
    window.addEventListener("deviceorientation", on as any);
    return () => {
      window.removeEventListener("deviceorientationabsolute", on as any);
      window.removeEventListener("deviceorientation", on as any);
    };
  }, [enabled]);
  return h;
}

export function GuideCard({ hp, me, heading, onClose }: { hp: HelpPoint; me: Fix | null; heading: number | null; onClose: () => void }) {
  const { t } = useT();
  const d = me ? haversine(me.lat, me.lon, hp.lat, hp.lon) : null;
  const b = me ? bearing(me.lat, me.lon, hp.lat, hp.lon) : null;
  const rot = b != null ? (heading != null ? b - heading : b) : 0;
  return (
    <div className="absolute inset-x-3 top-20 z-30 mx-auto max-w-lg animate-slideup">
      <div className="card flex items-center gap-4 p-4 shadow-float">
        <div className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-safe/10">
          <ArrowUp size={40} className="text-safe transition-transform" style={{ transform: `rotate(${rot}deg)` }} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-bold">{hp.name}</p>
          <p className="text-2xl font-extrabold">{d != null ? fmtDistance(d) : "–"} <span className="text-base font-semibold text-muted">{b != null ? cardinal(b) : ""}</span></p>
          <p className="text-xs text-muted">{heading != null ? "Arrow follows your compass" : "Arrow points from north (compass unavailable)"}</p>
        </div>
        <button onClick={onClose} className="grid h-10 w-10 place-items-center rounded-full bg-black/5" aria-label={t("close")}><X size={18} /></button>
      </div>
    </div>
  );
}
