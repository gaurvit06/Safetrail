import { AlertTriangle, BookOpen, CheckCircle2, Footprints, Languages, LogOut, MapPin, Megaphone, MessageSquareText, Navigation, QrCode, Users, Wifi, WifiOff, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import MapView from "../components/MapView";
import {
  FamilySheet, GuideCard, PackSheet, PassSheet, PhraseShow, SafetyCheckPrompt, SignalSheet, SosFlow, SosStatus, Strobe, useHeading, WeatherSheet, ZoneAlert, zoneText,
} from "../components/tourist";
import { BottomSheet, HoldButton, Overlay, SheetHeader, Spinner, useToast } from "../components/ui";
import { api, connectEvents, isNetworkError } from "../lib/api";
import { ago, riskText } from "../lib/format";
import { WeatherIcon, ZoneIcon } from "../components/icons";
import { distanceToPolygon, fmtDistance, haversine, nearest, nearestSegmentName, safeWayOut } from "../lib/geo";
import { Geofence } from "../lib/geofence";
import { useT } from "../lib/i18n";
import { flush, kv, onQueueChange, pingQueue, queueSos, sosStore, type QueuedSos } from "../lib/offline";
import { getBundle, getSession, setBundle, setSession } from "../lib/session";
import { ackChime, cautionChime, dangerAlert, unlockAudio, vibrate } from "../lib/signals";
import type { CrowdHeat, Evt, HelpPoint, Pack, PassPayload, StartBundle, Weather, Zone } from "../lib/types";
import { LangSwitch } from "./Welcome";

type Fix = { lat: number; lon: number; accuracy: number; source?: "gps" | "checkpoint" | "sim" };
const SHEET_PEEK = 150;
// The simulated walk starts on the path south of the block and ends inside it, about 190 m in 17 seconds.
const WALK_START_M = { north: -190, east: 30 };
const WALK_STEPS = 19;
const WALK_STEP_MS = 900;

export default function TripHome() {
  const { t, lang } = useT();
  const nav = useNavigate();
  const toast = useToast();
  const [params] = useSearchParams();
  const session = useMemo(getSession, []);
  const [bundle, setB] = useState<StartBundle | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [pack, setPack] = useState<Pack | null>(null);
  const [me, setMe] = useState<Fix | null>(null);
  const [gps, setGps] = useState<"waiting" | "ok" | "denied" | "rough">("waiting");
  const [online, setOnline] = useState(navigator.onLine);
  const [sending, setSending] = useState(false);
  const [queued, setQueued] = useState(0);
  const [sosList, setSosList] = useState<QueuedSos[]>([]);
  const [sharing, setSharing] = useState(true);
  const [inside, setInside] = useState<string[]>([]);
  const [alertZone, setAlertZone] = useState<Zone | null>(null);
  const [approach, setApproach] = useState<Zone | null>(null);
  const [crowd, setCrowd] = useState<{ message: string; alt: string; wait: number } | null>(null);
  const [check, setCheck] = useState<{ check_id: number; message: string } | null>(null);
  const [overlay, setOverlay] = useState<null | "sos" | "pack" | "signal" | "pass" | "family" | "end" | "weather">(null);
  const [weather, setWeather] = useState<Weather | null>(null);
  const [heat, setHeat] = useState<CrowdHeat | null>(null);
  const [walking, setWalking] = useState(false);
  const walkTimer = useRef<number | null>(null);
  const lastCrowdAlert = useRef(0);
  const routeIdRef = useRef("");
  const [packTab, setPackTab] = useState(0);
  const [sosPreset, setSosPreset] = useState<string | undefined>();
  const [statusId, setStatusId] = useState<string | null>(null);
  const [wayOut, setWayOut] = useState<number[][] | null>(null);
  const [guide, setGuide] = useState<HelpPoint | null>(null);
  const [zoneCard, setZoneCard] = useState<Zone | null>(null);
  const [phrase, setPhrase] = useState<{ local: string; user: string } | null>(null);
  const [strobe, setStrobe] = useState(false);
  const [demo, setDemo] = useState(false);
  const [groupMsg, setGroupMsg] = useState<string | null>(null);
  const [ended, setEnded] = useState<number | null>(null);
  const geofence = useRef(new Geofence());
  const zonesRef = useRef<Zone[]>([]);
  const passRef = useRef<PassPayload | null>(null); // Phase 2: permit-aware geofencing
  const [passRevoked, setPassRevoked] = useState(false);
  zonesRef.current = zones;
  const meRef = useRef<Fix | null>(null);
  const demoRef = useRef(false);
  demoRef.current = demo;
  const sharingRef = useRef(true);
  sharingRef.current = sharing;
  const lastPing = useRef(0);
  const heading = useHeading(!!guide);

  const tripId = session?.trip.id ?? "";
  const token = session?.tourist_token ?? "";

  /* ---------------- storage + sync */
  const refreshQueue = useCallback(async () => {
    const all = await sosStore.all();
    setSosList(all.filter((s) => s.trip_id === tripId).sort((a, b) => b.created_at_device - a.created_at_device));
    setQueued(all.filter((s) => s.status === "queued").length + (await pingQueue.count()));
  }, [tripId]);

  const saveWeather = async (w: Weather) => {
    setWeather((cur) => (cur?.fetched_at && w.fetched_at && cur.fetched_at >= w.fetched_at ? cur : w));
    const b = await getBundle();
    if (b && (!b.weather?.fetched_at || (w.fetched_at ?? 0) > b.weather.fetched_at)) await setBundle({ ...b, weather: w });
  };

  const persistZones = async (zs: Zone[]) => {
    const b = await getBundle();
    if (b) {
      b.route.zones = zs;
      await setBundle(b);
    }
  };

  const sync = useCallback(async () => {
    if (!session) return;
    try {
      const r = await api(`/trips/${tripId}/sync`, { token });
      setZones(r.zones);
      persistZones(r.zones);
      if (r.weather?.available) saveWeather(r.weather);
      if (r.heat) setHeat(r.heat);
      if (r.checks_pending?.length) setCheck(r.checks_pending[0]);
      for (const s of r.sos) {
        const q = await sosStore.get(s.client_id);
        if (q && q.status !== "cancelled")
          await sosStore.put({ ...q, status: "received", received_at: s.received_at, incident_id: s.incident_id, incident_status: s.incident_status, accepted_at: s.accepted_at, team: s.team });
      }
      setOnline(true);
      refreshQueue();
    } catch (e) {
      if (isNetworkError(e)) setOnline(false);
    }
  }, [session, tripId, token, refreshQueue]);

  const sendAnswers = async () => {
    const pending = (await kv.get<{ check_id: number; answer: string }[]>("answers")) ?? [];
    const left = [];
    for (const a of pending) {
      try {
        await api(`/safety-checks/${a.check_id}/answer`, { token, body: { trip_id: tripId, answer: a.answer } });
      } catch (e) {
        if (isNetworkError(e)) left.push(a);
      }
    }
    await kv.set("answers", left);
  };

  const flushNow = useCallback(async () => {
    if (!session) return;
    const n = (await sosStore.all()).filter((s) => s.status === "queued").length + (await pingQueue.count());
    if (n) setSending(true);
    const r = await flush(tripId, token);
    setSending(false);
    setOnline(r.online);
    if (r.online) sendAnswers();
    refreshQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, tripId, token, refreshQueue]);

  useEffect(() => {
    if (!session) return void nav("/");
    getBundle().then((b) => {
      if (!b || b.trip.id !== tripId) return void nav("/t/prepare");
      setB(b);
      passRef.current = (b.pass as unknown as PassPayload) ?? null;
      setZones(b.route.zones);
      setPack(b.pack);
      setSharing(b.trip.sharing !== false);
      routeIdRef.current = b.route.id;
      if (b.weather?.available) setWeather(b.weather);
      else api<Weather>(`/weather?route_id=${b.route.id}`).then((w) => {
          if (w.available) saveWeather(w);
        }).catch(() => {});
    });
    refreshQueue();
    const off = onQueueChange(refreshQueue);
    flushNow();
    const i = setInterval(flushNow, 10000);
    const onl = () => {
      flushNow();
      sync();
    };
    const offl = () => setOnline(false);
    window.addEventListener("online", onl);
    window.addEventListener("offline", offl);
    return () => {
      off();
      clearInterval(i);
      window.removeEventListener("online", onl);
      window.removeEventListener("offline", offl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // upgrade the template pack to the AI pack when it's ready
  useEffect(() => {
    if (!bundle || !pack || pack.source === "ai" || !online) return;
    const i = setInterval(async () => {
      try {
        const p = await api<Pack>(`/packs?route_id=${bundle.route.id}&lang=${bundle.trip.language}&bucket=${bundle.trip.profile_bucket}`);
        if (p.source === "ai") {
          setPack(p);
          const b = await getBundle();
          if (b) await setBundle({ ...b, pack: p });
          clearInterval(i);
        }
      } catch {
        /* offline: keep the template */
      }
    }, 8000);
    return () => clearInterval(i);
  }, [bundle, pack, online]);

  /* ---------------- live events */
  useEffect(() => {
    if (!session) return;
    const onEvent = (e: Evt) => {
      const d = e.data;
      if (e.type === "zone.published") {
        setZones((zs) => {
          const next = [...zs.filter((z) => z.id !== d.zone.id), d.zone];
          persistZones(next);
          return next;
        });
      } else if (e.type === "zone.advisory_ready") {
        const merge = (z: Zone): Zone => (z.id === d.zone_id ? { ...z, advisories: { ...z.advisories, ...d.advisories } } : z);
        setZones((zs) => zs.map(merge));
        setAlertZone((a) => (a ? merge(a) : a));
      } else if (e.type === "zone.removed") {
        setZones((zs) => {
          const next = zs.filter((z) => z.id !== d.zone_id);
          persistZones(next);
          return next;
        });
        setAlertZone((a) => (a?.id === d.zone_id ? null : a));
        setApproach((a) => (a?.id === d.zone_id ? null : a));
      } else if (e.type === "crowd.heat_public") {
        if (d.route_id === routeIdRef.current) setHeat(d);
      } else if (e.type === "crowd.warn") {
        setCrowd({ message: d.message?.[lang] ?? Object.values(d.message ?? {})[0] ?? "", alt: d.alt_name, wait: d.wait_min });
        cautionChime();
      } else if (e.type === "check.prompt") {
        setCheck({ check_id: d.check_id, message: d.message });
        cautionChime();
      } else if (e.type === "incident.status") {
        sosStore.all().then(async (all) => {
          for (const s of all)
            if (s.incident_id === d.incident_id) await sosStore.put({ ...s, incident_status: d.status, accepted_at: d.status === "accepted" ? d.at : s.accepted_at, team: d.team });
          refreshQueue();
        });
        if (d.status === "accepted") {
          ackChime();
          toast(`${t("st_ack")} · ${d.team ?? ""}`, "ok");
        }
        if (d.message) setGroupMsg(d.message);
      } else if (e.type === "pass.revoked") {
        setPassRevoked(true);
        toast(t("pass_revoked"), "danger");
      } else if (e.type === "weather.updated") {
        if (d.route_id === routeIdRef.current && d.weather?.available) saveWeather(d.weather);
      } else if (e.type === "stage.reset") {
        toast("The demo was reset. Thanks for trying SafeTrail!");
        setSession(null);
        nav("/");
      }
    };
    return connectEvents(token, onEvent, (open) => open && (setOnline(true), sync()));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  /* ---------------- location + geofence */
  const postEvent = (type: string, z: Zone) =>
    api(`/trips/${tripId}/events`, { token, body: [{ type, zone_id: z.id, kind: z.kind, ts_device: Date.now() / 1000 }] }).catch(() => {});

  const onFix = useCallback((f: Fix) => {
    meRef.current = f;
    setMe(f);
    setGps(f.accuracy > 60 ? "rough" : "ok");
    const evs = geofence.current.update({ ...f, ts: Date.now() }, zonesRef.current);
    let important = false;
    for (const ev of evs) {
      if (ev.type === "enter") {
        important = true;
        postEvent("zone_enter", ev.zone);
        setApproach((a) => (a?.id === ev.zone.id ? null : a));
        const p = passRef.current;
        if (ev.zone.kind === "restricted" && p?.kyc_level === "verified" && (p.permitted_zone_ids ?? []).includes(ev.zone.id)) {
          toast(t("permitted_here", { zone: ev.zone.segment_name || ev.zone.id }), "ok"); // your permit covers it: no alarm
        } else if (ev.fullScreen && !(ev.zone.kind === "crowd" && Date.now() - lastCrowdAlert.current < 5 * 60 * 1000)) {
          // A crowd can shift into several zones, so it alerts once; and it never covers a danger alert.
          if (ev.zone.kind === "crowd") lastCrowdAlert.current = Date.now();
          setAlertZone((a) => (ev.zone.kind === "crowd" && a && a.kind !== "crowd" ? a : ev.zone));
          dangerAlert();
        } else cautionChime();
      } else if (ev.type === "approach") {
        setApproach(ev.zone);
        postEvent("approach", ev.zone);
        cautionChime();
      } else if (ev.type === "approach_clear") setApproach((a) => (a?.id === ev.zone.id ? null : a));
      else if (ev.type === "exit") {
        setAlertZone((a) => (a?.id === ev.zone.id ? null : a));
        setWayOut(null);
      }
    }
    setInside(geofence.current.insideZones());
    if (sharingRef.current && (important || Date.now() - lastPing.current > 15000 || f.source === "checkpoint")) {
      lastPing.current = Date.now();
      pingQueue.add({ lat: f.lat, lon: f.lon, accuracy_m: f.accuracy, ts_device: Date.now() / 1000, source: f.source ?? "gps" }).then(() => {
        if (important) flushNow();
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // re-run the geofence when zones change (a zone drawn on top of you must alert immediately)
  useEffect(() => {
    if (meRef.current) {
      onFix(meRef.current);
      setTimeout(() => meRef.current && onFix(meRef.current), 50);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zones.map((z) => z.id).join(",")]);

  useEffect(() => {
    if (!navigator.geolocation) return void setGps("denied");
    const id = navigator.geolocation.watchPosition(
      (p) => !demoRef.current && onFix({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy, source: "gps" }),
      (err) => setGps(err.code === 1 ? "denied" : "waiting"),
      { enableHighAccuracy: true, maximumAge: 2000, timeout: 20000 },
    );
    const hb = setInterval(() => {
      const f = meRef.current;
      if (f && sharingRef.current) pingQueue.add({ lat: f.lat, lon: f.lon, accuracy_m: f.accuracy, ts_device: Date.now() / 1000, source: f.source ?? "gps" });
    }, 120000);
    return () => {
      navigator.geolocation.clearWatch(id);
      clearInterval(hb);
    };
  }, [onFix]);

  // checkpoint QR scan: /c/:id -> /t?cp=ID
  useEffect(() => {
    const cp = params.get("cp");
    if (!cp || !bundle) return;
    const found = bundle.route.checkpoints.find((c) => c.id === cp);
    const apply = (c: { name: string; lat: number; lon: number }) => {
      onFix({ lat: c.lat, lon: c.lon, accuracy: 5, source: "checkpoint" });
      toast(t("checkpoint_ok", { name: c.name }), "ok");
      flushNow();
    };
    if (found) apply(found);
    else api(`/checkpoints/${cp}`).then(apply).catch(() => toast("Unknown checkpoint", "warn"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bundle]);

  /* ---------------- actions */
  const sendSos = async (kind: string, people: string, note: string) => {
    unlockAudio();
    const f = meRef.current ?? { lat: bundle!.route.center[1], lon: bundle!.route.center[0], accuracy: 5000 };
    const q: QueuedSos = { client_id: crypto.randomUUID().replace(/-/g, ""), trip_id: tripId, kind, people_bucket: people, note: note || null, lat: f.lat, lon: f.lon, accuracy_m: f.accuracy, created_at_device: Date.now() / 1000, channel: "data", status: "queued" };
    await queueSos(q);
    vibrate([300, 100, 300]);
    setOverlay(null);
    setSosPreset(undefined);
    setStatusId(q.client_id);
    flushNow();
  };

  const cancelSos = async (s: QueuedSos) => {
    if (s.status === "received") await api(`/sos/${s.client_id}/cancel`, { token, body: {} }).catch(() => toast("Couldn't cancel while offline", "warn"));
    await sosStore.put({ ...s, status: "cancelled" });
    setStatusId(null);
    refreshQueue();
  };

  const answerCheck = async (a: "safe" | "need_help") => {
    const c = check!;
    setCheck(null);
    if (a === "need_help") {
      setSosPreset("stuck");
      setOverlay("sos");
    } else toast(t("thanks_safe"), "ok");
    const pending = (await kv.get<any[]>("answers")) ?? [];
    await kv.set("answers", [...pending, { check_id: c.check_id, answer: a }]);
    sendAnswers();
  };


  /* ---------------- Phase 2: the pass carries a permit (simulated registry) */
  const upgradePass = async (qr: string, p: PassPayload) => {
    const b = (await getBundle()) ?? bundle;
    if (!b) return;
    const next = { ...b, pass_qr: qr, pass: p as unknown as Record<string, unknown> };
    await setBundle(next);
    setB(next);
    passRef.current = p;
    toast(t("permit_added"), "ok");
  };
  const notPermitted = (z: Zone): string | undefined => {
    const p = passRef.current;
    return z.kind === "restricted" && p?.kyc_level === "verified" && !(p.permitted_zone_ids ?? []).includes(z.id) ? p.permit_type ?? "" : undefined;
  };
  const showWayOut = (z: Zone) => {
    const f = meRef.current;
    setAlertZone(null);
    setZoneCard(null);
    if (!f) return toast(t("no_gps"), "warn");
    const w = safeWayOut(f.lat, f.lon, z.polygon);
    setWayOut(w.path);
    toast(`${fmtDistance(w.distance)} ${w.dir}`, "ok");
  };

  const toggleSharing = async () => {
    const on = !sharing;
    setSharing(on);
    try {
      await api(`/trips/${tripId}/sharing`, { token, body: { on } });
    } catch {
      /* offline: the next sync fixes it */
    }
    const b = await getBundle();
    if (b) await setBundle({ ...b, trip: { ...b.trip, sharing: on } });
  };

  const checkIn = async () => {
    const f = meRef.current;
    if (!f) return toast(t("no_gps"), "warn");
    await pingQueue.add({ lat: f.lat, lon: f.lon, accuracy_m: f.accuracy, ts_device: Date.now() / 1000, source: f.source ?? "gps" });
    await flushNow();
    toast(online ? t("checked_in") : t("st_pending"), online ? "ok" : "warn");
  };

  const endTrip = async () => {
    try {
      const r = await api(`/trips/${tripId}/end`, { token, body: {} });
      setEnded(r.pings_deleted_after);
    } catch (e: any) {
      toast(e.message ?? "Couldn't end the trip while offline", "warn");
    }
  };

  /** A labelled stand-in for a real walk, for when GPS near the building won't play along. It feeds the same
   *  geofence as real GPS, so the alert is the real one; only the position is simulated. */
  const walkIn = () => {
    const r = bundle!.route;
    const [lon0, lat0] = r.center;
    const startLat = lat0 + WALK_START_M.north / 111320;
    const startLon = lon0 + WALK_START_M.east / (111320 * Math.cos((lat0 * Math.PI) / 180));
    if (!zones.some((z) => z.kind === "red_zone")) toast(t("walk_no_zone"), "warn");
    if (walkTimer.current) clearInterval(walkTimer.current);
    geofence.current = new Geofence(); // so a second take alerts again
    setAlertZone(null);
    setWayOut(null);
    setInside([]);
    setDemo(true);
    demoRef.current = true;
    setWalking(true);
    let i = 0;
    walkTimer.current = window.setInterval(() => {
      const k = i / WALK_STEPS;
      onFix({ lat: startLat + (lat0 - startLat) * k, lon: startLon + (lon0 - startLon) * k, accuracy: 6, source: "sim" });
      if (++i > WALK_STEPS) {
        if (walkTimer.current) clearInterval(walkTimer.current);
        walkTimer.current = null;
        setWalking(false);
      }
    }, WALK_STEP_MS);
  };
  useEffect(() => () => { if (walkTimer.current) clearInterval(walkTimer.current); }, []);

  /** Leave simulated positions behind and start again from real GPS, so a fake position never lingers. */
  const backToGps = () => {
    if (walkTimer.current) clearInterval(walkTimer.current);
    walkTimer.current = null;
    setWalking(false);
    setDemo(false);
    demoRef.current = false;
    geofence.current = new Geofence();
    setAlertZone(null);
    setApproach(null);
    setWayOut(null);
    setInside([]);
    meRef.current = null;
    setMe(null);
    setGps("waiting");
    navigator.geolocation?.getCurrentPosition(
      (p) => onFix({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy, source: "gps" }),
      (err) => err.code === 1 && setGps("denied"),
      { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 },
    );
  };

  /* ---------------- derived */
  const route = bundle?.route;
  const segment = me && route ? nearestSegmentName(me.lat, me.lon, route.segments) : "";
  const nh = me && route ? nearest(me.lat, me.lon, route.help_points) : null;
  const wsec = weather?.sections.find((s) => s.name === segment) ?? weather?.sections[0] ?? null;
  const wDanger = wsec?.risks.find((r) => r.level === "danger");
  const insideZone = zones.find((z) => inside.includes(z.id));
  const statusSos = sosList.find((s) => s.client_id === statusId) ?? null;
  const activeSos = sosList.find((s) => s.status !== "cancelled" && s.incident_status !== "resolved" && Date.now() / 1000 - s.created_at_device < 6 * 3600);
  const acked = activeSos && (activeSos.incident_status === "accepted" || activeSos.incident_status === "en_route");
  const path = guide && me ? [[me.lon, me.lat], [guide.lon, guide.lat]] : wayOut;
  const familyUrl = `${bundle?.config.public_url?.replace(/\/$/, "") || window.location.origin}/f/${session?.family_token ?? bundle?.family_token}`;

  if (!session || !bundle || !route || !pack) return <div className="grid h-full place-items-center"><Spinner size={28} /></div>;

  const pill = sending ? { cls: "bg-info text-white", icon: <Spinner size={14} />, text: t("sending") } : online ? { cls: "bg-safe text-white", icon: <Wifi size={14} />, text: t("online") } : { cls: "bg-offline text-white", icon: <WifiOff size={14} />, text: t("offline") };

  return (
    <div className="relative h-full overflow-hidden">
      <MapView
        bbox={route.bbox}
        route={route.line}
        zones={zones}
        highlightZoneId={zoneCard?.id ?? alertZone?.id ?? null}
        me={me ? { ...me, heading: guide ? heading : null, demo: demo || me.source === "sim" } : null}
        helpPoints={route.help_points}
        checkpoints={route.checkpoints}
        path={path}
        followMe
        trackMe
        crowd={heat}
        legendClass="bottom-[166px] left-3"
        onClick={demo ? (lat, lon) => onFix({ lat, lon, accuracy: 5, source: "sim" }) : undefined}
        onZoneClick={(z) => setZoneCard(z)}
        onHelpClick={(hp) => setGuide(hp)}
      />

      {/* top bar */}
      <div className="absolute inset-x-0 top-0 z-20 flex items-center gap-2 p-3 pr-12">
        <div className="card flex min-w-0 flex-1 items-center gap-2 px-3 py-2 shadow-float">
          <MapPin size={18} className="shrink-0 text-brand" />
          <div className="min-w-0">
            <p className="truncate font-display text-lg font-bold leading-tight">{route.name}</p>
            <p className="truncate text-xs text-muted">{session.trip.label}{demo || me?.source === "sim" ? ` · ${t("sim_label")}` : me?.source === "gps" ? ` · ${t("gps_label", { m: Math.round(me.accuracy) })}` : segment ? ` · ${segment}` : ""}</p>
          </div>
        </div>
        <span className={`chip px-3 py-2 shadow-float ${pill.cls}`}>{pill.icon}{pill.text}</span>
      </div>

      {/* banners */}
      <div className="absolute inset-x-3 top-[72px] z-20 mx-auto flex max-w-lg flex-col gap-2">
        {acked && <div className="animate-slideup rounded-xl bg-safe px-4 py-3 font-semibold text-white shadow-float"><CheckCircle2 className="mr-2 inline" size={18} />{t("help_ack_banner", { team: activeSos?.team ?? "" })}</div>}
        {activeSos && !acked && <button onClick={() => setStatusId(activeSos.client_id)} className="rounded-xl bg-danger px-4 py-3 text-left font-semibold text-white shadow-float">SOS · {activeSos.status === "received" ? t("st_received") : t("st_pending")} →</button>}
        {wDanger && wsec && <button onClick={() => setOverlay("weather")} className="rounded-xl bg-danger px-4 py-3 text-left font-semibold text-white shadow-float"><WeatherIcon code={wsec.now.code} size={18} className="-mt-0.5 mr-1.5 inline" />{riskText(bundle.templates.weather, wDanger.key, wDanger.value)}</button>}
        {insideZone && !alertZone && <button onClick={() => showWayOut(insideZone)} className="rounded-xl bg-danger px-4 py-3 text-left font-semibold text-white shadow-float"><ZoneIcon kind={insideZone.kind} size={18} className="-mt-0.5 mr-1.5 inline" />{zoneText(insideZone, lang, bundle).title} · {t("show_way_back")} →</button>}
        {approach && !insideZone && me && <button onClick={() => setZoneCard(approach)} className="animate-slideup rounded-xl bg-caution px-4 py-3 text-left font-semibold text-white shadow-float"><ZoneIcon kind={approach.kind} size={18} className="-mt-0.5 mr-1.5 inline" />{zoneText(approach, lang, bundle).title}: {fmtDistance(distanceToPolygon(me.lat, me.lon, approach.polygon))} {t("ahead")}</button>}
        {gps === "rough" && me && <div className="rounded-xl bg-white/95 px-4 py-2 text-sm font-semibold text-caution shadow-float"><AlertTriangle className="mr-1 inline" size={16} />{t("rough", { m: Math.round(me.accuracy) })}</div>}
        {gps === "denied" && <div className="rounded-xl bg-white/95 px-4 py-2 text-sm font-semibold text-danger shadow-float">{t("no_gps")}</div>}
        {!sharing && <div className="rounded-xl bg-white/95 px-4 py-2 text-sm font-semibold text-muted shadow-float">{t("sharing_off")}</div>}
        {queued > 0 && !online && <div className="rounded-xl bg-white/95 px-4 py-2 text-sm font-semibold text-muted shadow-float">{t("queued_sos", { n: sosList.filter((s) => s.status === "queued").length })}</div>}
        {gps === "waiting" && !demo && <div className="rounded-xl bg-white/95 px-4 py-2 text-sm font-semibold text-muted shadow-float">{t("gps_waiting")}</div>}
        {demo && <button onClick={backToGps} className="rounded-xl bg-[#6B3E8E] px-4 py-2 text-left text-sm font-semibold text-white shadow-float">{walking ? t("walking") : t("sim_on")}</button>}
      </div>

      {guide && <GuideCard hp={guide} me={me} heading={heading} onClose={() => setGuide(null)} />}

      {zoneCard && (
        <div className="absolute inset-x-3 top-20 z-30 mx-auto max-w-lg animate-slideup">
          <div className="card p-4 shadow-float">
            <div className="flex items-start justify-between gap-2">
              <p className="text-lg font-bold"><ZoneIcon kind={zoneCard.kind} size={20} className="-mt-0.5 mr-1.5 inline" />{zoneText(zoneCard, lang, bundle).title}</p>
              <button onClick={() => setZoneCard(null)} className="grid h-9 w-9 place-items-center rounded-full bg-black/5"><X size={16} /></button>
            </div>
            <p className="mt-1">{zoneText(zoneCard, lang, bundle).body}</p>
            {me && <p className="mt-2 text-sm font-semibold text-muted">{inside.includes(zoneCard.id) ? "You are inside this zone" : `${fmtDistance(distanceToPolygon(me.lat, me.lon, zoneCard.polygon))} away`}</p>}
            <button className="btn-primary mt-3 w-full" onClick={() => showWayOut(zoneCard)}><Navigation size={18} /> {t("show_way_back")}</button>
          </div>
        </div>
      )}

      {crowd && (
        <div className="absolute inset-x-3 z-30 mx-auto max-w-lg animate-slideup" style={{ bottom: SHEET_PEEK + 12 }}>
          <div className="rounded-2xl bg-caution p-4 text-white shadow-float">
            <div className="flex items-start justify-between"><p className="flex items-center gap-2 text-lg font-bold"><Users size={20} />{t("crowd_title")}</p><button onClick={() => setCrowd(null)}><X /></button></div>
            <p className="mt-1">{crowd.message}</p>
            <div className="mt-3 flex gap-2">
              <button className="btn flex-1 bg-white text-ink" onClick={() => { setCrowd(null); setTimeout(() => { cautionChime(); toast(t("crowd_title") + "?", "warn"); }, crowd.wait * 60000); toast(t("remind_me", { m: crowd.wait }), "ok"); }}>{t("remind_me", { m: crowd.wait })}</button>
              {crowd.alt && <button className="btn flex-1 border-2 border-white/70" onClick={() => { setCrowd(null); toast(crowd.alt, "ok"); }}>{t("show_alt")}</button>}
            </div>
          </div>
        </div>
      )}

      {/* SOS */}
      <div className="absolute right-4 z-30" style={{ bottom: SHEET_PEEK + 16 }}>
        <HoldButton onDone={() => { unlockAudio(); setOverlay("sos"); }} label={t("sos_hold")} className="grid h-24 w-24 place-items-center rounded-full bg-danger text-white shadow-float">
          <div className="text-center leading-tight"><p className="text-2xl font-extrabold">SOS</p><p className="text-[11px] font-semibold opacity-90">hold</p></div>
        </HoldButton>
      </div>

      <BottomSheet peek={SHEET_PEEK} collapse={walking ? 1 : 0}>
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="eyebrow">{t("nearest_help")}</p>
            <p className="truncate font-display text-2xl font-bold leading-tight">{nh ? `${nh.item.name}` : "—"}</p>
            <p className="text-sm text-muted">{nh ? fmtDistance(nh.d) : gps === "waiting" ? "Finding you…" : ""}</p>
          </div>
          {nh && <button className="btn-ghost shrink-0" onClick={() => setGuide(nh.item)}><Navigation size={18} /> {t("guide_me")}</button>}
        </div>
        {wsec && (
          <button onClick={() => setOverlay("weather")} className="card mt-3 flex w-full items-center gap-3 p-3 text-left">
            <WeatherIcon code={wsec.now.code} size={32} strokeWidth={1.75} className="shrink-0 text-ink" />
            <div className="min-w-0 flex-1">
              <p className="font-bold">{Math.round(wsec.now.temp_c)}° · {wsec.now.desc}</p>
              <p className={`truncate text-sm ${wsec.level === "danger" ? "text-danger" : wsec.level === "warn" ? "text-caution" : "text-muted"}`}>
                {wsec.risks[0] ? riskText(bundle.templates.weather, wsec.risks[0].key, wsec.risks[0].value) : bundle.templates.weather?.none}
              </p>
              <p className="text-xs text-muted">{weather?.stale || !online ? t("last_update") : t("updated")} {ago(weather?.fetched_at)} · Open-Meteo</p>
            </div>
          </button>
        )}
        {route.id === "hall" && <button className="btn mt-3 w-full bg-[#6B3E8E] text-white" disabled={walking} onClick={walkIn}><Footprints size={18} /> {walking ? t("walking") : t("walk_in")}</button>}
        <div className="mt-4 grid grid-cols-3 gap-2">
          {[
            { icon: <BookOpen />, label: t("safety_pack"), on: () => { setPackTab(0); setOverlay("pack"); } },
            { icon: <MessageSquareText />, label: t("phrases"), on: () => { setPackTab(1); setOverlay("pack"); } },
            { icon: <Megaphone />, label: t("signal"), on: () => { unlockAudio(); setOverlay("signal"); } },
            { icon: <QrCode />, label: t("pass"), on: () => setOverlay("pass") },
            { icon: <Users />, label: t("family"), on: () => setOverlay("family") },
            { icon: <CheckCircle2 />, label: t("check_in"), on: checkIn },
          ].map((a) => (
            <button key={a.label} onClick={a.on} className="flex flex-col items-center gap-1 rounded-2xl border border-line bg-white px-2 py-3 text-xs font-semibold active:scale-95">
              <span className="text-brand">{a.icon}</span>{a.label}
            </button>
          ))}
        </div>
        {sosList.filter((s) => s.status !== "cancelled").length > 0 && (
          <div className="mt-4">
            <p className="label">{t("sos_title")}</p>
            {sosList.filter((s) => s.status !== "cancelled").slice(0, 3).map((s) => (
              <button key={s.client_id} onClick={() => setStatusId(s.client_id)} className="card mt-2 flex w-full items-center justify-between p-3 text-left">
                <span className="font-semibold">{bundle.templates.kind[s.kind] ?? s.kind} · {new Date(s.created_at_device * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                <span className={`chip ${s.status === "received" ? "bg-safe/10 text-safe" : "bg-caution/10 text-caution"}`}>{s.incident_status === "accepted" || s.incident_status === "en_route" ? t("st_ack") : s.status === "received" ? t("st_received") : t("st_pending")}</span>
              </button>
            ))}
          </div>
        )}
        <div className="mt-5 space-y-2">
          <div className="flex items-center justify-between"><span className="flex items-center gap-2 font-semibold"><Languages size={18} /> Language</span><LangSwitch /></div>
          <button className="btn-ghost w-full" onClick={toggleSharing}>{sharing ? t("stop_sharing") : t("resume_sharing")}</button>
          <button className={`btn w-full ${demo ? "bg-[#6B3E8E] text-white" : "btn-ghost"}`} onClick={() => (demo ? backToGps() : setDemo(true))}>{demo ? t("use_real_gps") : t("demo_location")}</button>
          <button className="btn-ghost w-full text-danger" onClick={() => setOverlay("end")}><LogOut size={18} /> {t("end_trip")}</button>
          {route.simulated && <p className="pt-1 text-center text-xs text-muted">{t("route_simulated")}</p>}
        </div>
      </BottomSheet>

      {/* overlays */}
      {overlay === "sos" && <SosFlow bundle={bundle} preset={sosPreset} onSend={sendSos} onClose={() => { setOverlay(null); setSosPreset(undefined); }} />}
      {statusSos && <SosStatus sos={statusSos} label={session.trip.label} smsNumber={bundle.config.sms_number} offerAfterS={bundle.config.sms_offer_after_s} groupMessage={groupMsg} onCancel={() => cancelSos(statusSos)} onClose={() => setStatusId(null)} />}
      {overlay === "pack" && <PackSheet pack={pack.content} source={pack.source} helpPoints={route.help_points} segments={route.segments} currentSegment={segment} me={me} initialTab={packTab} onGuide={(hp) => { setOverlay(null); setGuide(hp); }} onShowLocal={setPhrase} onClose={() => setOverlay(null)} />}
      {overlay === "signal" && <SignalSheet me={me} segment={segment} nearestHelp={nh ? `${nh.item.name} (${fmtDistance(nh.d)})` : ""} emergency={route.facts.emergency_number} onStrobe={() => { setOverlay(null); setStrobe(true); }} onClose={() => setOverlay(null)} />}
      {overlay === "pass" && <PassSheet qr={bundle.pass_qr} label={session.trip.label} pass={(bundle.pass as unknown as PassPayload) ?? null} tripId={tripId} token={token} revoked={passRevoked} onUpgraded={upgradePass} onClose={() => setOverlay(null)} />}
      {overlay === "weather" && <WeatherSheet weather={weather} templates={bundle.templates.weather} current={segment} online={online} onClose={() => setOverlay(null)} />}
      {overlay === "family" && <FamilySheet url={familyUrl} token={session.family_token ?? bundle.family_token} tripId={tripId} touristToken={token} onClose={() => setOverlay(null)} />}
      {overlay === "end" && (
        <Overlay onClose={() => setOverlay(null)}>
          <SheetHeader title={ended ? t("end_trip") : t("back_safe")} onClose={() => setOverlay(null)} />
          <div className="space-y-3 px-5 py-5">
            {ended ? (
              <>
                <p>{t("trip_ended", { d: new Date(ended * 1000).toLocaleDateString() })}</p>
                <button className="btn-primary w-full" onClick={() => { setSession(null); nav("/"); }}>OK</button>
              </>
            ) : (
              <HoldButton onDone={endTrip} label={t("end_trip")} ringColor="#D93025" className="btn-ghost w-full text-danger">{t("end_trip")} (hold)</HoldButton>
            )}
          </div>
        </Overlay>
      )}
      {phrase && <PhraseShow local={phrase.local} user={phrase.user} onClose={() => setPhrase(null)} />}
      {strobe && <Strobe onClose={() => setStrobe(false)} />}
      {alertZone && <ZoneAlert zone={alertZone} bundle={bundle} notPermitted={notPermitted(alertZone)} onWayBack={() => showWayOut(alertZone)} onClose={() => setAlertZone(null)} />}
      {check && <SafetyCheckPrompt message={check.message} onAnswer={answerCheck} />}
    </div>
  );
}
