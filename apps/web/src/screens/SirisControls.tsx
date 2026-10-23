import { useEffect, useState } from "react";
import { BatteryCharging, Camera, Car, Eye, Lightbulb, Lock, LockOpen, Package, Power, ShieldCheck, Sparkles, Undo2, Warehouse, Zap } from "lucide-react";
import { assistant } from "../api/hub";
import { useResource } from "../api/resource";
import type { HomeControl, HomeControls, ProtocolPreview, ProtocolRunResult, SirisCar, SirisEnergy, SirisParcel, SirisProtocol, SirisWidgets } from "../api/types";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";

const WIDGETS_REFRESH_MS = 60_000;

/** SirisAI's hub widgets (ADR 110): car, parcels, power, protocols, cameras. */
export function useSirisWidgets() {
  const { data, error, reload } = useResource<SirisWidgets>("sirisai:widgets", () => assistant.widgets(), { refreshMs: WIDGETS_REFRESH_MS, persist: true });
  return { widgets: data ?? null, loading: !data && !error, failed: !data && !!error, reload: () => reload(true).catch(() => undefined) };
}

function Card({ title, Icon, wide, children, id }: { title: string; Icon: typeof Car; wide?: boolean; children: React.ReactNode; id?: string }) {
  return (
    <Glass as="section" id={id} className={`widget ${wide ? "widget--wide" : ""}`} aria-label={title}>
      <header className="widget__head">
        <Icon aria-hidden="true" />
        <span>{title}</span>
      </header>
      {children}
    </Glass>
  );
}

const PROTOCOL_LABELS: Record<string, string> = { lockdown: "Lock down", away: "Away", guest: "Guests over", guest_off: "Guests gone" };

export function protocolLabel(name: string): string {
  return PROTOCOL_LABELS[name] ?? name.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

/** Protocol buttons. Tapping one shows exactly what would run right now; it
 * runs only after "Run" (protocols change locks, covers and modes), and the
 * last run can be undone. */
export function ProtocolsWidget({ protocols, lastRun, onChanged }: { protocols: SirisProtocol[]; lastRun: SirisWidgets["last_protocol"]; onChanged: () => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [undoing, setUndoing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function undo() {
    setUndoing(true);
    try {
      const result = await assistant.undoProtocol();
      setMessage(`Undid ${protocolLabel(result.name)}.`);
      onChanged();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setUndoing(false);
    }
  }

  return (
    <Card title="Protocols" Icon={ShieldCheck} wide>
      <div className="protocol-buttons">
        {protocols.map((p) => (
          <button key={p.name} type="button" className="button protocol-button" onClick={() => setOpen(p.name)} title={p.description}>
            {protocolLabel(p.name)}
          </button>
        ))}
      </div>
      {lastRun?.can_undo && (
        <p className="muted protocol-last">
          Last: {protocolLabel(lastRun.protocol ?? "")}
          <button type="button" className="button button--small button--quiet" onClick={undo} disabled={undoing}>
            <Undo2 size={14} aria-hidden="true" /> Undo
          </button>
        </p>
      )}
      {message && <p className="muted" role="status">{message}</p>}
      {open && <ProtocolSheet name={open} onClose={() => setOpen(null)} onRan={(r) => { setMessage(summary(r)); onChanged(); }} />}
    </Card>
  );
}

function summary(r: ProtocolRunResult): string {
  const parts = [`${protocolLabel(r.name)}: ${r.ran.length} step${r.ran.length === 1 ? "" : "s"} done`];
  if (r.skipped.length) parts.push(`${r.skipped.length} skipped`);
  if (r.failed.length) parts.push(`${r.failed.length} failed`);
  return parts.join(", ") + ".";
}

export function ProtocolSheet({ name, onClose, onRan }: { name: string; onClose: () => void; onRan: (r: ProtocolRunResult) => void }) {
  const [preview, setPreview] = useState<ProtocolPreview | null>(null);
  const [result, setResult] = useState<ProtocolRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    assistant.protocol(name).then(setPreview, (e) => setError(e instanceof Error ? e.message : String(e)));
  }, [name]);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const r = await assistant.runProtocol(name);
      setResult(r);
      onRan(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <Sheet label={protocolLabel(name)} onClose={onClose}>
      <h2 className="sheet__title">{protocolLabel(name)}</h2>
      {preview?.description && <p className="muted">{preview.description}</p>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      {result ? (
        <>
          <p role="status">{summary(result)}</p>
          {result.failed.length > 0 && <ul className="items">{result.failed.map((f) => <li key={f} className="item tone-critical">{f}</li>)}</ul>}
          <button type="button" className="button" onClick={onClose}>Done</button>
        </>
      ) : preview ? (
        <>
          <ul className="items protocol-steps" aria-label="What will happen">
            {preview.steps.map((s, i) => (
              <li key={i} className={`item ${s.would_run ? "" : "item--skipped"}`}>
                <span className="item__dot" aria-hidden="true" />
                <span className="item__text">
                  <div className="item__title">{s.label}</div>
                  {!s.would_run && s.reason && <div className="item__subtitle">Skipped now: {s.reason}</div>}
                </span>
              </li>
            ))}
          </ul>
          <div className="row">
            <button type="button" className="button button--primary" onClick={run} disabled={running}>
              {running ? "Running…" : `Run ${protocolLabel(name).toLowerCase()}`}
            </button>
            <button type="button" className="button" onClick={onClose}>Cancel</button>
          </div>
        </>
      ) : (
        !error && <div className="skeleton" style={{ height: 80 }} />
      )}
    </Sheet>
  );
}

/** Cameras: tap one for its latest frame, and ask SirisAI's vision model what's there. */
export function CamerasWidget({ cameras }: { cameras: string[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Card title="Cameras" Icon={Camera} id="cameras">
      <div className="protocol-buttons">
        {cameras.map((c) => (
          <button key={c} type="button" className="button button--small" onClick={() => setOpen(c)}>{c.replace(/_/g, " ")}</button>
        ))}
      </div>
      {open && <CameraSheet camera={open} onClose={() => setOpen(null)} />}
    </Card>
  );
}

export function CameraSheet({ camera, onClose }: { camera: string; onClose: () => void }) {
  const [src, setSrc] = useState<string | null>(null);
  const [description, setDescription] = useState<string | null>(null);
  const [looking, setLooking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let url: string | null = null;
    assistant.frame(camera).then((u) => { url = u; setSrc(u); }, () => setError("No picture from this camera right now."));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [camera]);

  async function look() {
    setLooking(true);
    setError(null);
    try {
      setDescription((await assistant.look(camera)).description);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLooking(false);
    }
  }

  const name = camera.replace(/_/g, " ");
  return (
    <Sheet label={name} onClose={onClose}>
      <h2 className="sheet__title">{name}</h2>
      {src && <img className="camera-frame" src={src} alt={`Latest frame from ${name}`} />}
      {error && <div className="error-banner" role="alert">{error}</div>}
      {description && <p role="status">{description}</p>}
      <button type="button" className="button button--primary" onClick={look} disabled={looking}>
        <Eye size={16} aria-hidden="true" /> {looking ? "Looking…" : "What's there?"}
      </button>
    </Sheet>
  );
}

export function CarWidget({ car }: { car: SirisCar }) {
  return (
    <Card title={car.name.replace(/^the /, "").replace(/^\w/, (c) => c.toUpperCase())} Icon={Car}>
      {car.battery_percent != null && (
        <div className="row" style={{ alignItems: "baseline", gap: 12 }}>
          <span className={`hud-big ${car.low_battery ? "tone-critical" : ""}`}>{Math.round(car.battery_percent)}%</span>
          {car.range != null && <span className="hud-cond">{Math.round(car.range)} {car.range_unit ?? "km"}</span>}
        </div>
      )}
      <p className="muted" style={{ margin: 0 }}>
        {car.charging ? <><BatteryCharging size={14} aria-hidden="true" /> Charging · </> : car.plugged_in ? "Plugged in · " : ""}
        {car.locked === false ? "Unlocked" : car.locked ? "Locked" : ""}
        {car.location ? ` · ${car.location}` : ""}
      </p>
      {car.low_battery && <p className="tone-critical" style={{ margin: 0 }}>Low and not plugged in.</p>}
    </Card>
  );
}

export function EnergyWidget({ energy }: { energy: SirisEnergy }) {
  const next = energy.next_cheap_window ? new Date(energy.next_cheap_window) : null;
  return (
    <Card title="Power" Icon={Zap}>
      <div className={`hud-cond ${energy.cheap_now ? "tone-good" : ""}`}>{energy.cheap_now ? "Cheap right now" : "Not cheap right now"}</div>
      <p className="muted" style={{ margin: 0 }}>
        {energy.cheap_now
          ? energy.reasons[0]
          : next && !Number.isNaN(next.getTime())
            ? `Next cheap window ${next.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false })}`
            : ""}
      </p>
      {energy.waiting_jobs > 0 && <p className="muted" style={{ margin: 0 }}>{energy.waiting_jobs} job{energy.waiting_jobs === 1 ? "" : "s"} waiting for it</p>}
    </Card>
  );
}

export function SirisParcelsWidget({ parcels }: { parcels: SirisParcel[] }) {
  return (
    <Card title="Parcels" Icon={Package}>
      <ul className="items">
        {parcels.slice(0, 4).map((p) => (
          <li key={p.id} className="item">
            <span className="item__dot" aria-hidden="true" />
            <span className="item__text">
              <div className="item__title">{p.label}</div>
              <div className="item__subtitle">{[p.status_text, p.eta ? `ETA ${p.eta.slice(0, 10)}` : null].filter(Boolean).join(" · ")}</div>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

const ACTION_FOR: Record<HomeControl["kind"], (state: string) => string> = {
  light: () => "toggle",
  switch: () => "toggle",
  garage: (s) => (s === "open" || s === "opening" ? "close" : "open"),
  lock: (s) => (s === "locked" ? "unlock" : "lock"),
};

function stateWords(c: HomeControl): string {
  if (c.kind === "light" || c.kind === "switch") return c.state === "on" ? (c.brightness_pct != null ? `On · ${c.brightness_pct}%` : "On") : c.state === "off" ? "Off" : c.state;
  return c.state.charAt(0).toUpperCase() + c.state.slice(1);
}

/** Lights, the garage, locks and scenes, one tap each (4.2). The garage and
 * unlocking ask first; SirisAI refuses them otherwise. */
export function HomeControlsWidget() {
  const { data, reload } = useResource<HomeControls>("sirisai:controls", () => assistant.controls(), { refreshMs: 30_000, persist: true });
  const [asking, setAsking] = useState<HomeControl | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<{ tone: "good" | "critical"; text: string } | null>(null);
  const [states, setStates] = useState<Record<string, string>>({});
  if (!data || (!data.configured && data.scenes.length === 0) || (data.controls.length === 0 && data.scenes.length === 0)) return null;

  async function act(c: HomeControl, confirmed = false) {
    const state = states[c.entity_id] ?? c.state;
    const action = ACTION_FOR[c.kind](state);
    if ((c.kind === "garage" || action === "unlock") && !confirmed) {
      setAsking(c);
      return;
    }
    setAsking(null);
    setBusy(c.entity_id);
    setNote(null);
    try {
      const r = await assistant.control(c.entity_id, action, confirmed);
      if (r.state) setStates((s) => ({ ...s, [c.entity_id]: r.state! }));
      reload(true).catch(() => undefined);
    } catch (e) {
      setNote({ tone: "critical", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(null);
    }
  }
  async function scene(id: string, name: string) {
    setBusy(id);
    setNote(null);
    try {
      await assistant.scene(id);
      setNote({ tone: "good", text: `${name}: done.` });
      reload(true).catch(() => undefined);
    } catch (e) {
      setNote({ tone: "critical", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(null);
    }
  }

  const confirmText = (c: HomeControl) => {
    const action = ACTION_FOR[c.kind](states[c.entity_id] ?? c.state);
    return `${action.charAt(0).toUpperCase() + action.slice(1)} ${c.name}?`;
  };
  return (
    <Card title="Home controls" Icon={Lightbulb} wide id="home-controls">
      {data.controls.length > 0 && (
        <div className="controls-grid">
          {data.controls.map((c) => {
            const state = states[c.entity_id] ?? c.state;
            const on = state === "on" || state === "open" || state === "unlocked";
            const Icon = c.kind === "garage" ? Warehouse : c.kind === "lock" ? (state === "locked" ? Lock : LockOpen) : c.kind === "switch" ? Power : Lightbulb;
            return (
              <button key={c.entity_id} type="button" className={`control-tile ${on ? "control-tile--on" : ""} ${c.kind === "garage" || c.kind === "lock" ? `control-tile--${c.kind}` : ""}`}
                aria-pressed={c.kind === "light" || c.kind === "switch" ? on : undefined} disabled={busy === c.entity_id}
                aria-label={`${c.name}: ${stateWords({ ...c, state })}`} onClick={() => act(c)}>
                <Icon size={18} aria-hidden="true" />
                <span className="control-tile__name">{c.name}</span>
                <span className="control-tile__state">{busy === c.entity_id ? "…" : stateWords({ ...c, state })}</span>
              </button>
            );
          })}
        </div>
      )}
      {asking && (
        <div className="row control-confirm" role="alertdialog" aria-label={confirmText(asking)}>
          <span style={{ fontWeight: 600 }}>{confirmText(asking)}</span>
          <button type="button" className="button button--small button--primary" onClick={() => act(asking, true)}>Yes</button>
          <button type="button" className="button button--small" onClick={() => setAsking(null)}>Cancel</button>
        </div>
      )}
      {data.scenes.length > 0 && (
        <div className="protocol-buttons" aria-label="Scenes">
          {data.scenes.map((s) => (
            <button key={s.id} type="button" className="button button--small" disabled={busy === s.id} onClick={() => scene(s.id, s.name)}>
              <Sparkles size={14} aria-hidden="true" /> {s.name}
            </button>
          ))}
        </div>
      )}
      {data.guest_mode && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Guest mode: the garage and locks are hidden.</p>}
      {note && <p className={`tone-${note.tone}`} role="status" style={{ margin: 0, fontSize: 14 }}>{note.text}</p>}
    </Card>
  );
}
