import { Activity, BellRing, Database, Footprints, LocateFixed, Mountain, RotateCcw, Siren, SkipForward, Users, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { LoginCard } from "../components/ops";
import { HoldButton, Spinner, useToast } from "../components/ui";
import { api } from "../lib/api";
import { getRoleToken } from "../lib/session";
import type { RoundState } from "../lib/types";

/** Presenter's phone (SPEC 9.4.2): one tap per demo beat. */
export default function StageControl() {
  const toast = useToast();
  const [token, setToken] = useState<string | null>(() => getRoleToken("presenter"));
  const [busy, setBusy] = useState<string | null>(null);
  const [useMine, setUseMine] = useState(false);
  const [last, setLast] = useState<string>("");
  const [round, setRound] = useState<RoundState | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);
  const timer = useRef<number | null>(null);
  useEffect(() => {
    if (token) api<RoundState>("/stage/round", { token }).then(setRound).catch(() => {});
  }, [token]);
  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);
  /** One tap starts the next judging round after 3 seconds; tapping again in that time cancels it.
   *  The countdown lives in a ref and the request is sent outside any state update, so it can only fire once. */
  const left = useRef(0);
  const nextRound = () => {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
      setCountdown(null);
      toast("Cancelled. Nothing was reset.", "info");
      return;
    }
    left.current = 3;
    setCountdown(3);
    timer.current = window.setInterval(() => {
      left.current -= 1;
      if (left.current > 0) return void setCountdown(left.current);
      if (timer.current) clearInterval(timer.current);
      timer.current = null;
      setCountdown(null);
      api<RoundState & { message: string }>("/stage/scenario", { token, body: { action: "next_round" } })
        .then((r) => {
          setRound(r);
          setLast(r.message);
          toast(r.message, "ok");
        })
        .catch((e) => toast(e.message, "danger"));
    }, 1000);
  };

  const [flagged, setFlagged] = useState(false);
  const [crowdOn, setCrowdOn] = useState(false);
  useEffect(() => {
    api<{ kind: string }[]>("/zones?route_id=hall").then((zs) => setFlagged(zs.some((z) => z.kind === "red_zone"))).catch(() => {});
  }, [token]);
  const csed = async (action: "flag" | "clear" | "crowd" | "crowd_stop") => {
    setBusy(action);
    try {
      const r = await api<{ ok?: boolean; message: string }>("/stage/csed", { token, body: { action } });
      setLast(r.message);
      toast(r.message, r.ok === false ? "warn" : "ok");
      if (action === "flag") setFlagged(true);
      if (action === "clear") setFlagged(false);
      if (action === "crowd") setCrowdOn(true);
      if (action === "crowd_stop") setCrowdOn(false);
    } catch (e: any) {
      if (e.status === 401 || e.status === 403) setToken(null);
      toast(e.message, "danger");
    } finally {
      setBusy(null);
    }
  };

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
      <div className="flex items-center gap-2 font-display text-3xl font-bold"><img src="/icon.svg" className="h-8 w-8" alt="" /> Stage control</div>
      <div className="space-y-2 rounded-2xl bg-night-bg p-4 text-night-text">
        <p className="font-display text-2xl font-bold leading-none text-gold">CSED block demo</p>
        <button className={`${flagged ? "btn-dark" : "btn-danger"} h-auto w-full justify-start gap-4 p-4 text-left`} disabled={!!busy} onClick={() => csed(flagged ? "clear" : "flag")}>
          {busy === "flag" || busy === "clear" ? <Spinner size={28} /> : <Siren size={28} className="shrink-0" />}
          <span><span className="block text-lg">{flagged ? "Clear CSED red zone" : "Flag CSED as a red zone"}</span><span className="block text-sm font-normal opacity-80">{flagged ? "CSED is red on every phone now." : "The whole block turns red on every phone. Anyone who walks in gets the alert."}</span></span>
        </button>
        <button className="btn-dark h-auto w-full justify-start gap-4 p-4 text-left" disabled={!!busy} onClick={() => csed(crowdOn ? "crowd_stop" : "crowd")}>
          {busy === "crowd" || busy === "crowd_stop" ? <Spinner size={28} /> : <Users size={28} className="shrink-0 text-gold" />}
          <span><span className="block text-lg">{crowdOn ? "Stop the simulated crowd" : "Simulate a crowd around CSED"}</span><span className="block text-sm font-normal opacity-80">80 simulated people, around the block only. The heatmap fills in over 20 s.</span></span>
        </button>
      </div>
      <button className={`btn h-auto w-full justify-start gap-4 p-4 text-left ${countdown !== null ? "bg-caution text-white" : "btn-primary"}`} disabled={!!busy} onClick={nextRound}>
        <SkipForward size={28} className="shrink-0" />
        <span>
          <span className="block text-lg">{countdown !== null ? `Starting round ${(round?.round ?? 0) + 1} in ${countdown}… tap to cancel` : `Next round${round ? ` (now: round ${round.round})` : ""}`}</span>
          <span className="block text-sm font-normal opacity-90">Recaps this round on the projector, resets the demo, shows the Join QR again.</span>
        </span>
      </button>
      {round?.last && (
        <div className="card p-3 text-sm">
          <b>Round {round.last.round}:</b> {round.last.judges} judges · {round.last.sos} SOS → {round.last.incidents} incident(s) · {round.last.accepted} accepted · {round.last.tricks_caught}/{round.last.tricks} tricks caught
        </div>
      )}
      <label className="card flex items-center gap-3 p-3">
        <input type="checkbox" className="h-5 w-5 accent-brand" checked={useMine} onChange={(e) => setUseMine(e.target.checked)} />
        <span className="text-sm"><LocateFixed size={14} className="inline" /> Place zones at <b>my</b> location (otherwise: around the judges)</span>
      </label>
      <B a="landslide" icon={<Mountain size={28} />} title="Landslide here" sub="Publishes a danger zone over the judges. Their phones buzz." tone="btn-danger" />
      <B a="crowd_surge" icon={<Users size={28} className="text-caution" />} title="Crowd surge" sub="Adds 40 simulated people over 20 s. The area turns red." />
      <B a="safety_check" icon={<BellRing size={28} className="text-info" />} title='Send "Are you safe?"' sub="To everyone in (or recently in) the landslide zone." />
      <B a="budget_stress" icon={<Zap size={28} className="text-[#6B3E8E]" />} title="Budget stress test" sub="Tiny Prune run budget on the cluster summary: 429 stop, standard text, safety unaffected." />
      <B a="walk_sim" icon={<Footprints size={28} />} title="Walk simulation" sub="A simulated tourist walks a loop (backup if GPS is bad)." />
      <B a="demo_data" icon={<Database size={28} className="text-brand" />} title="Load demo data (Kedarnath)" sub="28 demo travellers, an SOS cluster at the landslide, a lost traveller, a safety check, a crowd and Break-it attempts. View on /r (Kedarnath) or /stage?route=kedarnath." />
      <div className="card p-3 text-sm"><Activity size={14} className="inline" /> {last || "Open /stage on the projector."}</div>
      <HoldButton onDone={() => run("reset")} label="Reset demo" ringColor="#D93025" className="btn-ghost w-full text-danger"><RotateCcw size={18} /> Hold to reset the demo</HoldButton>
    </div>
  );
}
