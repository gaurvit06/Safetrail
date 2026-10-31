import { BellRing, MapPinned, ShieldCheck, Users } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useT } from "../lib/i18n";
import { getSession } from "../lib/session";

export function LangSwitch() {
  const { lang, setLang } = useT();
  return (
    <div className="flex rounded-full border border-line bg-white p-0.5 text-sm font-semibold">
      {(["en", "hi"] as const).map((l) => (
        <button key={l} onClick={() => setLang(l)} className={`rounded-full px-3 py-1.5 ${lang === l ? "bg-ink text-white" : "text-muted"}`}>
          {l === "en" ? "EN" : "हिं"}
        </button>
      ))}
    </div>
  );
}

export default function Welcome() {
  const { t } = useT();
  const nav = useNavigate();
  const session = getSession();
  return (
    <div className="mx-auto flex min-h-full max-w-lg flex-col px-5 pb-8 pt-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-lg font-bold">
          <img src="/icon.svg" alt="" className="h-9 w-9" /> SafeTrail
        </div>
        <LangSwitch />
      </div>
      <div className="mt-10">
        <h1 className="text-[34px] font-bold leading-tight">{t("tagline")}</h1>
        <p className="mt-3 text-muted">Treks · Pilgrimages · National parks</p>
      </div>
      <div className="mt-8 space-y-3">
        {[
          { icon: <BellRing className="text-caution" />, text: t("how_1") },
          { icon: <MapPinned className="text-danger" />, text: t("how_2") },
          { icon: <Users className="text-safe" />, text: t("how_3") },
        ].map((x, i) => (
          <div key={i} className="card flex items-start gap-3 p-4">
            <div className="mt-0.5">{x.icon}</div>
            <p>{x.text}</p>
          </div>
        ))}
      </div>
      <div className="mt-auto space-y-3 pt-8">
        {session && (
          <button className="btn-primary w-full text-lg" onClick={() => nav(session.started ? "/t" : "/t/prepare")}>
            {t("continue_trip")} · {session.trip.label}
          </button>
        )}
        <button className={`${session ? "btn-ghost" : "btn-primary"} w-full text-lg`} onClick={() => nav("/t/new")}>
          {t("start_trip")}
        </button>
        <button className="btn-ghost w-full" onClick={() => nav("/r")}>
          <ShieldCheck size={18} /> {t("im_responder")}
        </button>
      </div>
    </div>
  );
}
