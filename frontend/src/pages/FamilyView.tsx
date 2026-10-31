import { HeartHandshake, Lock } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import { ago, hm } from "../lib/format";

type Fam = { first_name: string; route_name: string; status: string; last_check_in_ago_s: number | null; acknowledged_at: number | null };
const STATUS: Record<string, { label: string; cls: string }> = {
  not_started: { label: "Not started yet", cls: "bg-black/5 text-muted" },
  on_trip: { label: "On trip", cls: "bg-info/10 text-info" },
  help_requested: { label: "Help requested", cls: "bg-danger/10 text-danger" },
  help_acknowledged: { label: "Help acknowledged", cls: "bg-caution/10 text-caution" },
  safe: { label: "Safe", cls: "bg-safe/10 text-safe" },
  trip_ended: { label: "Trip ended", cls: "bg-black/5 text-muted" },
};

/** What a family member sees: status only, never a location (SPEC 5.15). */
export default function FamilyView() {
  const { token } = useParams();
  const [d, setD] = useState<Fam | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const load = () => api<Fam>(`/family/${token}`).then((x) => { setD(x); setErr(null); }).catch((e) => setErr(e.message));
    load();
    const i = setInterval(load, 30000);
    return () => clearInterval(i);
  }, [token]);
  const st = d ? STATUS[d.status] ?? STATUS.on_trip : null;
  return (
    <div className="mx-auto flex min-h-full max-w-md flex-col justify-center px-5 py-10">
      <div className="mb-6 flex items-center gap-2 font-bold"><img src="/icon.svg" className="h-8 w-8" alt="" /> SafeTrail · Family</div>
      {err && <div className="card p-6 text-center text-muted">{err}</div>}
      {d && st && (
        <div className="card p-6">
          <div className="flex items-center gap-3"><HeartHandshake className="text-brand" /><p className="text-xl font-bold">{d.first_name}</p></div>
          <p className="mt-1 text-muted">{d.route_name}</p>
          <span className={`chip mt-5 px-4 py-2 text-base ${st.cls}`}>{st.label}</span>
          <p className="mt-4 text-lg">Last check-in: <b>{d.last_check_in_ago_s == null ? "not yet" : ago(Date.now() / 1000 - d.last_check_in_ago_s)}</b></p>
          {d.acknowledged_at && <p className="mt-1 text-caution">Rescue team acknowledged at {hm(d.acknowledged_at)}</p>}
        </div>
      )}
      <p className="mt-6 flex items-center justify-center gap-2 text-center text-sm text-muted"><Lock size={14} /> For their privacy, SafeTrail never shares live location.</p>
    </div>
  );
}
