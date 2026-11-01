import { LifeBuoy, QrCode, Route, ShieldCheck, Siren } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useT } from "../lib/i18n";
import { getSession } from "../lib/session";

export function LangSwitch({ dark }: { dark?: boolean }) {
  const { lang, setLang } = useT();
  return (
    <div className={`flex rounded-full border p-0.5 text-sm font-semibold ${dark ? "border-night-line bg-night-surface" : "border-line bg-white"}`}>
      {(["en", "hi"] as const).map((l) => (
        <button key={l} onClick={() => setLang(l)} className={`rounded-full px-3 py-1.5 ${lang === l ? (dark ? "bg-night-text text-ink" : "bg-ink text-white") : dark ? "text-night-text/70" : "text-muted"}`}>
          {l === "en" ? "EN" : "हिं"}
        </button>
      ))}
    </div>
  );
}

/** The four stages of a trip, drawn like the deck's tourist slide: colour dots on a dashed gold line. */
export default function Welcome() {
  const { t } = useT();
  const nav = useNavigate();
  const session = getSession();
  const flow = [
    { icon: <QrCode size={20} />, tone: "bg-brand", title: t("flow_before"), text: t("flow_before_text") },
    { icon: <Route size={20} />, tone: "bg-brand", title: t("flow_trail"), text: t("how_1") },
    { icon: <Siren size={20} />, tone: "bg-danger", title: t("flow_trouble"), text: t("how_2") },
    { icon: <LifeBuoy size={20} />, tone: "bg-safe", title: t("flow_help"), text: t("flow_help_text") },
  ];
  return (
    <div className="min-h-full bg-night-bg text-night-text">
      <div className="mx-auto flex min-h-full max-w-lg flex-col px-5 pb-8 pt-5">
        <div className="flex items-center justify-between">
          <p className="text-sm text-night-text/70">Treks · Pilgrimages · National parks</p>
          <LangSwitch dark />
        </div>
        <h1 className="mt-8 text-7xl text-white">SafeTrail</h1>
        <p className="mt-2 font-display text-3xl font-bold leading-tight text-gold">{t("motto")}</p>
        <p className="mt-3 text-lg leading-snug">{t("tagline")}</p>
        <ol className="mt-8">
          {flow.map((x, i) => (
            <li key={x.title} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span className={`flow-dot ${x.tone}`}>{x.icon}</span>
                {i < flow.length - 1 && <span className="flow-line my-1 flex-1 border-l-2" />}
              </div>
              <div className="pb-5">
                <p className="font-display text-2xl font-bold leading-tight text-white">{x.title}</p>
                <p className="text-sm leading-snug text-night-text/80">{x.text}</p>
              </div>
            </li>
          ))}
        </ol>
        <div className="mt-auto space-y-3 pt-4">
          {session && (
            <button className="btn-primary w-full text-lg" onClick={() => nav(session.started ? "/t" : "/t/prepare")}>
              {t("continue_trip")} · {session.trip.label}
            </button>
          )}
          <button className={`${session ? "btn-dark" : "btn-primary"} w-full text-lg`} onClick={() => nav("/t/new")}>
            {t("start_trip")}
          </button>
          <button className="btn-dark w-full" onClick={() => nav("/r")}>
            <ShieldCheck size={18} /> {t("im_responder")}
          </button>
        </div>
      </div>
    </div>
  );
}
