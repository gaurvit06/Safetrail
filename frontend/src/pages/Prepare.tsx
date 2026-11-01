import { Bell, Check, Compass, MapPin, Volume2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Spinner, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useT } from "../lib/i18n";
import { askNotify, canNotify, cautionChime, unlockAudio } from "../lib/signals";
import { getSession, setBundle, setSession } from "../lib/session";
import type { StartBundle } from "../lib/types";

export default function Prepare() {
  const { t } = useT();
  const nav = useNavigate();
  const toast = useToast();
  const session = getSession();
  const [bundle, setB] = useState<StartBundle | null>(null);
  const [sound, setSound] = useState(false);
  const [loc, setLoc] = useState<"idle" | "asking" | "ok" | "denied">("idle");
  const [motion, setMotion] = useState(false);
  const [alerts, setAlerts] = useState(canNotify() && Notification.permission === "granted");

  useEffect(() => {
    if (!session) return void nav("/");
    api<StartBundle>(`/trips/${session.trip.id}/start`, { token: session.tourist_token, body: {} })
      .then(async (b) => {
        await setBundle(b);
        setSession({ ...session, started: true });
        setB(b);
      })
      .catch((e) => toast(e.message ?? "Couldn't prepare the trip", "danger"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const askLocation = () => {
    setLoc("asking");
    navigator.geolocation.getCurrentPosition(() => setLoc("ok"), () => setLoc("denied"), { enableHighAccuracy: true, timeout: 15000 });
  };
  const testSound = () => {
    unlockAudio();
    setTimeout(cautionChime, 150);
    setSound(true);
  };
  const askMotion = async () => {
    const D = (window as any).DeviceOrientationEvent;
    try {
      if (D?.requestPermission) await D.requestPermission();
      setMotion(true);
    } catch {
      setMotion(true);
    }
  };

  const items = [
    { label: t("prep_pack"), done: !!bundle, sub: bundle ? (bundle.pack.source === "ai" ? "AI-written for your route" : "Standard pack (AI version on its way)") : undefined },
    { label: t("prep_map"), done: !!bundle, sub: bundle ? `${bundle.route.help_points.length} help points` : undefined },
    { label: t("prep_zones"), done: !!bundle, sub: bundle ? `${bundle.route.zones.length} active` : undefined },
    { label: t("prep_pass"), done: !!bundle },
  ];

  return (
    <div className="mx-auto flex min-h-full max-w-lg flex-col px-5 pb-6 pt-8">
      <h1 className="text-5xl">{t("preparing")}</h1>
      <p className="mt-1 text-muted">{session?.trip.label} · {bundle?.route.name ?? "…"}</p>
      <div className="card mt-6 divide-y divide-line">
        {items.map((it) => (
          <div key={it.label} className="flex items-center gap-3 p-4">
            <div className={`grid h-8 w-8 place-items-center rounded-full ${it.done ? "bg-safe text-white" : "bg-black/5"}`}>{it.done ? <Check size={18} /> : <Spinner />}</div>
            <div>
              <p className="font-semibold">{it.label}</p>
              {it.sub && <p className="text-sm text-muted">{it.sub}</p>}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-3">
        <button className={`btn ${sound ? "bg-safe/10 text-safe" : "btn-ghost"}`} onClick={testSound}>
          {sound ? <Check size={18} /> : <Volume2 size={18} />} {t("prep_sound")}
        </button>
        <button className={`btn ${loc === "ok" ? "bg-safe/10 text-safe" : loc === "denied" ? "bg-danger/10 text-danger" : "btn-ghost"}`} onClick={askLocation}>
          {loc === "ok" ? <Check size={18} /> : loc === "asking" ? <Spinner /> : <MapPin size={18} />} {loc === "denied" ? t("no_gps") : t("prep_location")}
        </button>
        {canNotify() && (
          <button className={`btn ${alerts ? "bg-safe/10 text-safe" : "btn-ghost"}`} onClick={() => askNotify().then(() => setAlerts(Notification.permission === "granted"))}>
            {alerts ? <Check size={18} /> : <Bell size={18} />} {t("prep_notify")}
          </button>
        )}
        <button className={`btn ${motion ? "bg-safe/10 text-safe" : "btn-ghost"}`} onClick={askMotion}>
          {motion ? <Check size={18} /> : <Compass size={18} />} Compass (for "Guide me")
        </button>
      </div>
      {bundle && <p className="mt-5 rounded-xl bg-safe/10 p-3 text-sm font-semibold text-safe">{t("can_go_offline")}</p>}
      <div className="mt-auto pt-6">
        <button className="btn-primary w-full text-lg" disabled={!bundle} onClick={() => { unlockAudio(); nav("/t"); }}>{t("open_map")}</button>
      </div>
    </div>
  );
}
