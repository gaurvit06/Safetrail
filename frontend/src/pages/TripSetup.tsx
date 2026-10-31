import { ArrowLeft, Check, Minus, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "../components/ui";
import { api } from "../lib/api";
import { useT } from "../lib/i18n";
import { setSession } from "../lib/session";
import type { RouteSummary, TripCreated } from "../lib/types";
import { LangSwitch } from "./Welcome";

const todayISO = () => new Date().toISOString().slice(0, 10);
const plusDaysISO = (d: number) => new Date(Date.now() + d * 86400000).toISOString().slice(0, 10);

export default function TripSetup() {
  const { t, lang } = useT();
  const nav = useNavigate();
  const toast = useToast();
  const [step, setStep] = useState(0);
  const [routes, setRoutes] = useState<RouteSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ name: "", phone: "", ec_name: "", ec_phone: "", group: 1, profile: "standard", route: "", start: todayISO(), end: plusDaysISO(2), consent: false });
  const up = (k: keyof typeof f, v: any) => setF((x) => ({ ...x, [k]: v }));

  useEffect(() => {
    api<RouteSummary[]>("/routes").then((r) => {
      setRoutes(r);
      if (!f.route && r.length) up("route", r.find((x) => x.id === "kedarnath")?.id ?? r[0].id);
    }).catch(() => toast("Can't reach the server. Check your connection.", "danger"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const valid = [f.name.trim().length > 0, !!f.route, f.consent][step];

  const submit = async () => {
    setBusy(true);
    try {
      const r = await api<TripCreated>("/trips", {
        body: {
          name: f.name.trim(), phone: f.phone, emergency_contact_name: f.ec_name, emergency_contact_phone: f.ec_phone,
          language: lang, route_id: f.route, group_size: f.group, profile_bucket: f.profile, consent: true,
          start_at: new Date(f.start).getTime() / 1000, end_at: new Date(f.end).getTime() / 1000 + 86399,
        },
      });
      setSession({ ...r, started: false });
      nav("/t/prepare");
    } catch (e: any) {
      toast(e.message ?? "Something went wrong", "danger");
    } finally {
      setBusy(false);
    }
  };

  const titles = [t("about_you"), t("your_route"), t("consent")];
  return (
    <div className="mx-auto flex min-h-full max-w-lg flex-col px-5 pb-6 pt-4">
      <div className="flex items-center justify-between">
        <button className="grid h-11 w-11 place-items-center rounded-full bg-black/5" onClick={() => (step ? setStep(step - 1) : nav("/"))} aria-label={t("back")}>
          <ArrowLeft />
        </button>
        <LangSwitch />
      </div>
      <div className="mt-4 flex gap-2">
        {titles.map((_, i) => <div key={i} className={`h-1.5 flex-1 rounded-full ${i <= step ? "bg-brand" : "bg-line"}`} />)}
      </div>
      <h1 className="mt-5 text-2xl font-bold">{titles[step]}</h1>

      {step === 0 && (
        <div className="mt-5 space-y-4">
          <label className="block"><span className="label">{t("name")}</span><input className="input mt-1" value={f.name} onChange={(e) => up("name", e.target.value)} autoComplete="name" /></label>
          <label className="block"><span className="label">{t("phone")}</span><input className="input mt-1" inputMode="tel" value={f.phone} onChange={(e) => up("phone", e.target.value)} autoComplete="tel" /></label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block"><span className="label">{t("ec_name")}</span><input className="input mt-1" value={f.ec_name} onChange={(e) => up("ec_name", e.target.value)} /></label>
            <label className="block"><span className="label">{t("ec_phone")}</span><input className="input mt-1" inputMode="tel" value={f.ec_phone} onChange={(e) => up("ec_phone", e.target.value)} /></label>
          </div>
          <div>
            <span className="label">{t("group_size")}</span>
            <div className="mt-1 flex items-center gap-3">
              <button className="btn-ghost w-12 px-0" onClick={() => up("group", Math.max(1, f.group - 1))} aria-label="minus"><Minus /></button>
              <span className="w-10 text-center text-2xl font-bold">{f.group}</span>
              <button className="btn-ghost w-12 px-0" onClick={() => up("group", Math.min(50, f.group + 1))} aria-label="plus"><Plus /></button>
            </div>
          </div>
          <div>
            <span className="label">{t("profile")}</span>
            <div className="mt-2 flex flex-wrap gap-2">
              {(["standard", "senior", "with_children", "medical_note"] as const).map((p) => (
                <button key={p} onClick={() => up("profile", p)} className={`chip border px-3 py-2 text-sm ${f.profile === p ? "border-brand bg-brand text-white" : "border-line bg-white"}`}>
                  {t(`p_${p}` as any)}
                </button>
              ))}
            </div>
            {f.profile === "medical_note" && <p className="mt-2 text-sm text-muted">{t("medical_hint")}</p>}
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="mt-5 space-y-3">
          {routes.map((r) => (
            <button key={r.id} onClick={() => up("route", r.id)} className={`card flex w-full items-center justify-between p-4 text-left ${f.route === r.id ? "border-2 border-brand" : ""}`}>
              <div>
                <p className="font-bold">{r.name}</p>
                <p className="text-sm text-muted">{r.region} · {r.distance_km} km</p>
                {r.simulated && <span className="chip mt-2 bg-caution/10 text-caution">{t("route_simulated")}</span>}
              </div>
              {f.route === r.id && <Check className="text-brand" />}
            </button>
          ))}
          <div className="grid grid-cols-2 gap-3 pt-2">
            <label className="block"><span className="label">{t("start_date")}</span><input type="date" className="input mt-1" value={f.start} onChange={(e) => up("start", e.target.value)} /></label>
            <label className="block"><span className="label">{t("end_date")}</span><input type="date" className="input mt-1" value={f.end} min={f.start} onChange={(e) => up("end", e.target.value)} /></label>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="mt-5 space-y-3">
          {[t("consent_1"), t("consent_2"), t("consent_3"), t("consent_4")].map((c, i) => (
            <div key={i} className="flex gap-3"><Check className="mt-0.5 shrink-0 text-safe" size={20} /><p>{c}</p></div>
          ))}
          <label className="card mt-4 flex cursor-pointer items-center gap-3 p-4">
            <input type="checkbox" className="h-6 w-6 accent-brand" checked={f.consent} onChange={(e) => up("consent", e.target.checked)} />
            <span className="font-semibold">{t("i_agree")}</span>
          </label>
        </div>
      )}

      <div className="mt-auto pt-8">
        <button className="btn-primary w-full text-lg" disabled={!valid || busy} onClick={() => (step < 2 ? setStep(step + 1) : submit())}>
          {step < 2 ? t("next") : t("start_trip")}
        </button>
      </div>
    </div>
  );
}
