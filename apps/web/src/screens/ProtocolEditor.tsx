import { useState } from "react";
import { ArrowDown, ArrowUp, Pencil, Plus, RotateCcw, ShieldCheck, Trash2 } from "lucide-react";
import { assistant } from "../api/hub";
import { refreshResource, useResource } from "../api/resource";
import type { ProtocolCatalogue, ProtocolDef, ProtocolStepDef } from "../api/types";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";
import { protocolLabel } from "./SirisControls";

const HA = "home_assistant_call_service";

const DOMAIN_LABEL: Record<string, string> = {
  light: "Lights", switch: "Switches", fan: "Fans", media_player: "TV & media", climate: "Heating & cooling",
  cover: "Blinds & garage doors", lock: "Locks", scene: "Scenes", script: "Scripts",
};
const ACTION_LABEL: Record<string, string> = {
  turn_on: "Turn on", turn_off: "Turn off", toggle: "Toggle", media_play: "Play", media_pause: "Pause",
  set_temperature: "Set temperature", open_cover: "Open", close_cover: "Close", lock: "Lock", unlock: "Unlock",
};
const WHEN: { value: string; label: string }[] = [
  { value: "", label: "Always" }, { value: "nobody_home", label: "Only when nobody's home" },
  { value: "someone_home", label: "Only when someone's home" }, { value: "night", label: "Only at night" }, { value: "day", label: "Only in the day" },
];
const GARAGE = { select: { domain: "cover", device_class: ["garage", "gate"] } };

type Kind = "ha" | "notify" | "guest" | "other";
const kindOf = (s: ProtocolStepDef): Kind => (s.tool === HA ? "ha" : s.tool === "notify" ? "notify" : s.tool === "set_guest_mode" ? "guest" : "other");
const args = (s: ProtocolStepDef) => s.arguments as Record<string, unknown>;

/** What a step does, in words: its label, or one made from what it is. */
export function describeStep(s: ProtocolStepDef, cat?: ProtocolCatalogue | null): string {
  if (s.label) return s.label;
  const a = args(s);
  if (s.tool === HA) {
    const target = a.entity_id === "all" ? `all ${(DOMAIN_LABEL[String(a.domain)] ?? String(a.domain)).toLowerCase()}`
      : isGarage(a.entity_id) ? "garage doors and gates"
      : (Array.isArray(a.entity_id) ? a.entity_id : [a.entity_id]).map((id) => cat?.entities.find((e) => e.entity_id === id)?.name ?? String(id)).join(", ");
    return `${ACTION_LABEL[String(a.service)] ?? String(a.service)} ${target}`;
  }
  if (s.tool === "notify") return `Notify: ${String(a.message ?? "")}`;
  if (s.tool === "set_guest_mode") return a.on ? `Guest mode on${a.hours ? ` for ${a.hours} h` : ""}` : "Guest mode off";
  return s.tool.replace(/_/g, " ");
}

function isGarage(entity: unknown): boolean {
  return !!entity && typeof entity === "object" && "select" in (entity as object);
}

const whenLabel = (w: ProtocolStepDef["when"]) => (typeof w === "string" ? WHEN.find((x) => x.value === w)?.label : w ? `Only when ${w.entity} is ${w.state ?? `not ${w.not_state}`}` : null);

/** Smart home: every protocol, to change, and a way to make new ones (4.91). What's saved is
 *  what Home's Protocols card and Siris in chat use. */
export function ProtocolsManager() {
  const res = useResource<ProtocolCatalogue>("sirisai:protocols", () => assistant.protocols(), { staleMs: 30_000 });
  const [editing, setEditing] = useState<ProtocolDef | "new" | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const cat = res.data ?? null;

  function changed(message: string) {
    setNote(message);
    setEditing(null);
    res.reload(true).catch(() => undefined);
    refreshResource("sirisai:widgets");   // Home's Protocols card
  }

  return (
    <Glass as="section" className="widget widget--wide" aria-label="Protocols">
      <header className="widget__head"><ShieldCheck aria-hidden="true" /><span>Protocols</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Several things done in one go, like Lockdown or Away. Running one always asks first, and can be undone.</p>
      {!cat && res.error && <p className="tone-critical" style={{ margin: 0 }}>Protocols need SirisAI 2.91 or later with Home Assistant set up.</p>}
      {!cat && !res.error && <div className="skeleton" style={{ height: 60 }} />}
      {cat && (
        <ul className="items">
          {cat.protocols.map((p) => (
            <li key={p.name} className="item">
              <span className="item__text">
                <div className="item__title">{protocolLabel(p.name)} {p.builtin ? <span className="chip">Built-in</span> : p.customised ? <span className="chip">Your version</span> : null}</div>
                <div className="item__subtitle">{p.description || p.steps.map((s) => describeStep(s, cat)).join(" · ")}</div>
              </span>
              <button type="button" className="icon-link" onClick={() => setEditing(p)} aria-label={`Edit ${protocolLabel(p.name)}`} title="Edit">
                <Pencil size={15} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {cat && (
        <div className="row">
          <button type="button" className="button button--small" onClick={() => setEditing("new")}><Plus size={14} aria-hidden="true" /> New protocol</button>
        </div>
      )}
      {note && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{note}</p>}
      {cat && editing && (
        <ProtocolSheet catalogue={cat} protocol={editing === "new" ? null : editing} onClose={() => setEditing(null)} onChanged={changed} />
      )}
    </Glass>
  );
}

function blankStep(cat: ProtocolCatalogue): ProtocolStepDef {
  const domain = cat.actions.light ? "light" : Object.keys(cat.actions)[0];
  return { tool: HA, arguments: { domain, service: cat.actions[domain]?.[0] ?? "turn_on", entity_id: "all" } };
}

function ProtocolSheet({ catalogue: cat, protocol, onClose, onChanged }: {
  catalogue: ProtocolCatalogue; protocol: ProtocolDef | null; onClose: () => void; onChanged: (message: string) => void;
}) {
  const [name, setName] = useState(protocol?.name ?? "");
  const [description, setDescription] = useState(protocol?.description ?? "");
  const [steps, setSteps] = useState<ProtocolStepDef[]>(protocol?.steps ?? [blankStep(cat)]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const slug = name.trim().toLowerCase().replace(/[\s-]+/g, "_");
  const title = protocol ? protocolLabel(protocol.name) : "New protocol";

  const put = (i: number, step: ProtocolStepDef) => setSteps(steps.map((s, j) => (j === i ? step : s)));
  const move = (i: number, by: -1 | 1) => {
    const j = i + by;
    if (j < 0 || j >= steps.length) return;
    const next = [...steps];
    [next[i], next[j]] = [next[j], next[i]];
    setSteps(next);
  };

  async function save() {
    if (!/^[a-z][a-z0-9_]{1,40}$/.test(slug)) {
      setError("Give it a name: letters, numbers and spaces, starting with a letter.");
      return;
    }
    if (!protocol && cat.protocols.some((p) => p.name === slug)) {
      setError(`There's already a protocol called ${protocolLabel(slug)}: edit that one instead.`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      // A step with no name gets one from what it does, so previews and Home's card read well.
      // Steps from chat (other tools, their own undo) go back exactly as they came.
      const named = steps.map((st) => (st.label || kindOf(st) === "other" || st.undo ? st : { ...st, label: describeStep(st, cat) }));
      await assistant.saveProtocol(slug, { description: description.trim(), steps: named });
      onChanged(`Saved ${protocolLabel(slug)}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^SirisAI: /, "") : "Couldn't save it.");
      setBusy(false);
    }
  }
  async function remove() {
    if (!protocol) return;
    setBusy(true);
    try {
      const r = await assistant.deleteProtocol(protocol.name);
      onChanged(r.restored_builtin ? `${protocolLabel(protocol.name)} is back to the built-in version.` : `Deleted ${protocolLabel(protocol.name)}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't delete it.");
      setBusy(false);
    }
  }

  return (
    <Sheet label={protocol ? `Edit ${title}` : "New protocol"} onClose={onClose}>
      <header className="sheet__head">
        <h2 className="sheet__title">{protocol ? `Edit ${title}` : "New protocol"}</h2>
        {protocol?.builtin && <p className="muted" style={{ margin: 0 }}>Saving makes this your version; you can go back to the built-in one any time.</p>}
      </header>
      <div className="stack" style={{ gap: 8 }}>
        {!protocol && (
          <label className="protocol__field"><span>Name</span>
            <input className="field" value={name} onChange={(e) => setName(e.target.value)} placeholder="Movie night" aria-label="Protocol name" maxLength={41} />
          </label>
        )}
        <label className="protocol__field"><span>What it's for</span>
          <input className="field" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Dim the lounge, close the blinds" aria-label="What it's for" maxLength={300} />
        </label>
      </div>
      <h3 className="section-title" style={{ marginTop: 14 }}>Steps, in order</h3>
      <ol className="protocol__steps">
        {steps.map((s, i) => (
          <li key={i} className="protocol__step">
            <div className="row protocol__step-head">
              <strong>{i + 1}.</strong>
              <span className="protocol__step-title">{describeStep(s, cat)}</span>
              <button type="button" className="icon-link" disabled={i === 0} onClick={() => move(i, -1)} aria-label={`Move step ${i + 1} up`}><ArrowUp size={15} aria-hidden="true" /></button>
              <button type="button" className="icon-link" disabled={i === steps.length - 1} onClick={() => move(i, 1)} aria-label={`Move step ${i + 1} down`}><ArrowDown size={15} aria-hidden="true" /></button>
              <button type="button" className="icon-link" disabled={steps.length === 1} onClick={() => setSteps(steps.filter((_, j) => j !== i))} aria-label={`Remove step ${i + 1}`}><Trash2 size={15} aria-hidden="true" /></button>
            </div>
            <StepEditor step={s} index={i} cat={cat} onChange={(step) => put(i, step)} />
          </li>
        ))}
      </ol>
      <button type="button" className="button button--small" onClick={() => setSteps([...steps, blankStep(cat)])} disabled={steps.length >= 30}>
        <Plus size={14} aria-hidden="true" /> Add a step
      </button>
      {error && <div className="error-banner" role="alert" style={{ marginTop: 10 }}>{error}</div>}
      <div className="row" style={{ justifyContent: "space-between", marginTop: 18, flexWrap: "wrap", gap: 8 }}>
        {protocol && !protocol.builtin ? (
          confirmDelete ? (
            <span className="row" style={{ gap: 6 }}>
              <button type="button" className="button button--small button--danger" onClick={remove} disabled={busy}>
                {protocol.customised ? "Yes, go back" : "Yes, delete"}
              </button>
              <button type="button" className="button button--small" onClick={() => setConfirmDelete(false)}>Keep</button>
            </span>
          ) : (
            <button type="button" className="button button--small" onClick={() => setConfirmDelete(true)}>
              {protocol.customised ? <><RotateCcw size={14} aria-hidden="true" /> Back to built-in</> : <><Trash2 size={14} aria-hidden="true" /> Delete</>}
            </button>
          )
        ) : <span />}
        <span className="row" style={{ gap: 6 }}>
          <button type="button" className="button button--small" onClick={onClose}>Cancel</button>
          <button type="button" className="button button--small button--primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        </span>
      </div>
    </Sheet>
  );
}

function StepEditor({ step, index, cat, onChange }: { step: ProtocolStepDef; index: number; cat: ProtocolCatalogue; onChange: (s: ProtocolStepDef) => void }) {
  const kind = kindOf(step);
  const a = args(step);
  const n = index + 1;
  const set = (patch: Record<string, unknown>) => onChange({ ...step, arguments: { ...a, ...patch } });

  if (kind === "other") {
    return <p className="muted" style={{ margin: 0, fontSize: 13 }}>Made in chat ({step.tool.replace(/_/g, " ")}): kept as it is. Ask Siris to change it.</p>;
  }
  const switchKind = (k: Kind) => {
    if (k === "ha") onChange({ ...blankStep(cat), when: step.when, label: step.label });
    if (k === "notify") onChange({ tool: "notify", arguments: { message: "", title: "" }, when: step.when, label: step.label });
    if (k === "guest") onChange({ tool: "set_guest_mode", arguments: { on: true, hours: 24 }, when: step.when, label: step.label });
  };
  const domain = String(a.domain ?? "");
  const services = cat.actions[domain] ?? [];
  const entities = cat.entities.filter((e) => e.domain === domain);
  const target = a.entity_id === "all" ? "all" : isGarage(a.entity_id) ? "garage" : String(Array.isArray(a.entity_id) ? a.entity_id[0] : a.entity_id ?? "");
  const data = (a.service_data ?? {}) as Record<string, number>;

  return (
    <div className="protocol__grid">
      <label><span>Does</span>
        <select className="field" value={kind} onChange={(e) => switchKind(e.target.value as Kind)} aria-label={`Step ${n}: kind`}>
          {cat.home_assistant && <option value="ha">A home device</option>}
          <option value="notify">Send a notification</option>
          <option value="guest">Guest mode</option>
        </select>
      </label>
      {kind === "ha" && (
        <>
          <label><span>Device type</span>
            <select className="field" value={domain} aria-label={`Step ${n}: device type`}
              onChange={(e) => { const d = e.target.value; set({ domain: d, service: cat.actions[d]?.[0], entity_id: "all", service_data: undefined }); }}>
              {Object.keys(cat.actions).map((d) => <option key={d} value={d}>{DOMAIN_LABEL[d] ?? d}</option>)}
            </select>
          </label>
          <label><span>Action</span>
            <select className="field" value={String(a.service ?? "")} onChange={(e) => set({ service: e.target.value, service_data: undefined })} aria-label={`Step ${n}: action`}>
              {services.map((s) => <option key={s} value={s}>{ACTION_LABEL[s] ?? s}</option>)}
            </select>
          </label>
          <label><span>Which</span>
            <select className="field" value={target} aria-label={`Step ${n}: which`}
              onChange={(e) => set({ entity_id: e.target.value === "all" ? "all" : e.target.value === "garage" ? GARAGE : e.target.value })}>
              <option value="all">All {(DOMAIN_LABEL[domain] ?? domain).toLowerCase()}</option>
              {domain === "cover" && <option value="garage">Garage doors and gates</option>}
              {entities.map((e) => <option key={e.entity_id} value={e.entity_id}>{e.name}</option>)}
              {target && !["all", "garage"].includes(target) && !entities.some((e) => e.entity_id === target) && <option value={target}>{target}</option>}
            </select>
          </label>
          {domain === "light" && a.service === "turn_on" && (
            <label><span>Brightness %</span>
              <input type="number" className="field" min={1} max={100} value={data.brightness_pct ?? ""} placeholder="As it was" aria-label={`Step ${n}: brightness`}
                onChange={(e) => set({ service_data: e.target.value ? { brightness_pct: Math.max(1, Math.min(100, Number(e.target.value))) } : undefined })} />
            </label>
          )}
          {domain === "climate" && a.service === "set_temperature" && (
            <label><span>Temperature °C</span>
              <input type="number" className="field" min={10} max={32} value={data.temperature ?? 21} aria-label={`Step ${n}: temperature`}
                onChange={(e) => set({ service_data: { temperature: Math.max(10, Math.min(32, Number(e.target.value) || 21)) } })} />
            </label>
          )}
        </>
      )}
      {kind === "notify" && (
        <>
          <label><span>Title</span><input className="field" value={String(a.title ?? "")} onChange={(e) => set({ title: e.target.value })} aria-label={`Step ${n}: title`} maxLength={100} /></label>
          <label className="protocol__wide"><span>Message</span><input className="field" value={String(a.message ?? "")} onChange={(e) => set({ message: e.target.value })} aria-label={`Step ${n}: message`} maxLength={500} /></label>
          <label><span>Priority</span>
            <select className="field" value={String(a.priority ?? "default")} onChange={(e) => set({ priority: e.target.value === "default" ? undefined : e.target.value })} aria-label={`Step ${n}: priority`}>
              {["low", "default", "high", "urgent"].map((p) => <option key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</option>)}
            </select>
          </label>
        </>
      )}
      {kind === "guest" && (
        <>
          <label><span>Turn it</span>
            <select className="field" value={a.on ? "on" : "off"} onChange={(e) => onChange({ ...step, arguments: e.target.value === "on" ? { on: true, hours: 24 } : { on: false } })} aria-label={`Step ${n}: guest mode`}>
              <option value="on">On</option><option value="off">Off</option>
            </select>
          </label>
          {a.on === true && (
            <label><span>For hours</span>
              <input type="number" className="field" min={1} max={168} value={Number(a.hours ?? 24)} onChange={(e) => set({ hours: Math.max(1, Math.min(168, Number(e.target.value) || 24)) })} aria-label={`Step ${n}: hours`} />
            </label>
          )}
        </>
      )}
      <label><span>When</span>
        {step.when && typeof step.when === "object" ? (
          <span className="muted" style={{ fontSize: 13 }}>{whenLabel(step.when)} (set in chat)</span>
        ) : (
          <select className="field" value={step.when ?? ""} onChange={(e) => onChange({ ...step, when: e.target.value || null })} aria-label={`Step ${n}: when`}>
            {WHEN.map((w) => <option key={w.value} value={w.value}>{w.label}</option>)}
          </select>
        )}
      </label>
      <label className="protocol__wide"><span>Name it (optional)</span>
        <input className="field" value={step.label ?? ""} onChange={(e) => onChange({ ...step, label: e.target.value || null })} placeholder={describeStep({ ...step, label: null }, cat)} aria-label={`Step ${n}: name`} maxLength={80} />
      </label>
    </div>
  );
}
