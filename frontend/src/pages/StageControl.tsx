import { Activity, BellRing, Database, Footprints, LocateFixed, Mountain, RotateCcw, Users, Zap } from "lucide-react";
import { useState } from "react";
import { LoginCard } from "../components/ops";
import { HoldButton, Spinner, useToast } from "../components/ui";
import { api } from "../lib/api";
import { getRoleToken } from "../lib/session";

/** Presenter's phone (SPEC 9.4.2): one tap per demo beat. */
export default function StageControl() {
  const toast = useToast();
  const [token, setToken] = useState<string | null>(() => getRoleToken("presenter"));
  const [busy, setBusy] = useState<string | null>(null);
  const [useMine, setUseMine] = useState(false);
  const [last, setLast] = useState<string>("");

  const run = async (action: string) => {
    setBusy(action);
    let pos: { lat?: number; lon?: number } = {};
    if (useMine && (action === "landslide" || action === "crowd_surge" || action === "walk_sim")) {
      pos = await new Promise((res) => navigator.geolocation.getCurrentPosition((p) => res({ lat: p.coords.latitude, lon: p.coords.longitude }), () => res({}), { enableHighAccuracy: true, timeout: 8000 }));
    }
    try {
      const r = await api<any>("/stage/scenario", { token, body: { action, ...pos } });
      const msg = r.message ?? (r.zone ? `Zone ${r.zone.id} published` : r.check_id ? `Safety check sent to ${r.targets} phones` : r.ok === false ? r.message : "Done");
      setLast(msg);
      toast(msg, r.ok === false ? "warn" : "ok");
    } catch (e: any) {
      if (e.status === 401 || e.status === 403) setToken(null);
      toast(e.message, "danger");
    } finally {
      setBusy(null);
    }
  };

  if (!token) return <div className="min-h-full px-4"><LoginCard roles={["presenter"]} onDone={(t) => setToken(t)} /></div>;

  const B = ({ a, icon, title, sub, tone = "btn-ghost" }: { a: string; icon: React.ReactNode; title: string; sub: string; tone?: string }) => (
    <button className={`${tone} h-auto w-full justify-start gap-4 p-4 text-left`} disabled={!!busy} onClick={() => run(a)}>
      <span className="shrink-0">{busy === a ? <Spinner size={28} /> : icon}</span>
      <span><span className="block text-lg">{title}</span><span className="block text-sm font-normal opacity-80">{sub}</span></span>
    </button>
  );

  return (
    <div className="mx-auto max-w-lg space-y-3 px-4 py-5">
      <div className="flex items-center gap-2 text-lg font-bold"><img src="/icon.svg" className="h-8 w-8" alt="" /> Stage control</div>
      <label className="card flex items-center gap-3 p-3">
        <input type="checkbox" className="h-5 w-5 accent-brand" checked={useMine} onChange={(e) => setUseMine(e.target.checked)} />
        <span className="text-sm"><LocateFixed size={14} className="inline" /> Place zones at <b>my</b> location (otherwise: around the judges)</span>
      </label>
      <B a="landslide" icon={<Mountain size={28} className="text-danger" />} title="Landslide here" sub="Publishes a danger zone over the judges. Their phones buzz." tone="btn-danger" />
      <B a="crowd_surge" icon={<Users size={28} className="text-caution" />} title="Crowd surge" sub="Adds 40 simulated people over 20 s. The area turns red." />
      <B a="safety_check" icon={<BellRing size={28} className="text-info" />} title='Send "Are you safe?"' sub="To everyone in (or recently in) the landslide zone." />
      <B a="budget_stress" icon={<Zap size={28} className="text-[#7C3AED]" />} title="Budget stress test" sub="Tiny Prune run budget on the cluster summary: 429 stop, standard text, safety unaffected." />
      <B a="walk_sim" icon={<Footprints size={28} />} title="Walk simulation" sub="A simulated tourist walks a loop (backup if GPS is bad)." />
      <B a="demo_data" icon={<Database size={28} className="text-brand" />} title="Load demo data (Kedarnath)" sub="28 demo travellers, an SOS cluster at the landslide, a lost traveller, a safety check, a crowd and Break-it attempts. View on /r (Kedarnath) or /stage?route=kedarnath." />
      <div className="card p-3 text-sm"><Activity size={14} className="inline" /> {last || "Open /stage on the projector."}</div>
      <HoldButton onDone={() => run("reset")} label="Reset demo" ringColor="#D93025" className="btn-ghost w-full text-danger"><RotateCcw size={18} /> Hold to reset the demo</HoldButton>
    </div>
  );
}
