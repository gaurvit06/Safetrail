import { Check } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "../components/ui";
import { api } from "../lib/api";
import { useT } from "../lib/i18n";
import { setSession } from "../lib/session";
import type { TripCreated } from "../lib/types";
import { LangSwitch } from "./Welcome";

/** Stage quick-join (/j): one screen, consent still required. */
export default function JudgeJoin() {
  const { t, lang } = useT();
  const nav = useNavigate();
  const toast = useToast();
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);

  const join = async () => {
    setBusy(true);
    try {
      const r = await api<TripCreated>("/join", { body: { name: name.trim() || null, language: lang, consent } });
      setSession({ ...r, started: false });
      nav("/t/prepare");
    } catch (e: any) {
      toast(e.message ?? "Couldn't join", "danger");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-full max-w-lg flex-col pb-6">
      <div className="bg-night-bg px-5 pb-6 pt-5 text-night-text">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-display text-2xl font-bold text-white"><img src="/icon.svg" alt="" className="h-9 w-9" /> SafeTrail</div>
          <LangSwitch dark />
        </div>
        <h1 className="mt-6 text-5xl text-white">You're on the trail</h1>
        <p className="mt-2 font-display text-2xl font-bold leading-tight text-gold">{t("motto")}</p>
        <p className="mt-2 text-night-text/80">For the next few minutes, the CSED block is a mountain route. Your phone will warn you, and you can call for help.</p>
      </div>
      <div className="flex flex-1 flex-col px-5">
      <label className="mt-6 block"><span className="label">Your name (optional)</span><input className="input mt-1" placeholder="Judge" value={name} onChange={(e) => setName(e.target.value)} /></label>
      <div className="mt-6 space-y-2 text-sm">
        {[t("consent_1"), t("consent_3"), t("consent_4")].map((c, i) => <div key={i} className="flex gap-2"><Check size={18} className="shrink-0 text-safe" />{c}</div>)}
      </div>
      <label className="card mt-4 flex cursor-pointer items-center gap-3 p-4">
        <input type="checkbox" className="h-6 w-6 accent-brand" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span className="font-semibold">{t("i_agree")}</span>
      </label>
      <div className="mt-auto pt-8">
        <button className="btn-primary w-full text-lg" disabled={!consent || busy} onClick={join}>Join the trail</button>
      </div>
      </div>
    </div>
  );
}
