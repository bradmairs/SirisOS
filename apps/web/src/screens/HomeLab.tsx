import { useEffect, useState } from "react";
import { Box, Cloud, Container, HardDrive, Network, Plus, Router, Server, Wifi, Zap, type LucideIcon } from "lucide-react";
import { homelab, KIND_LABEL, layout, type HomeLab, type LabKind, type LabNode } from "../api/homelab";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";
import { Sheet } from "../components/Sheet";

const ICON: Record<LabKind, LucideIcon> = {
  internet: Cloud, modem: Router, gateway: Router, switch: Network, access_point: Wifi, server: Server, nas: HardDrive, ups: Zap,
  docker: Container, device: Box, other: Box,
};
const W = 168, H = 64;
const ADDABLE: LabKind[] = ["modem", "switch", "access_point", "server", "nas", "ups", "device", "other"];

/** Home Lab (8.5): the hardware as a diagram. What plugs into what is guessed until you set it; tap a box to
 * add its model and notes, or move it. Hardware SirisOS can't see (a modem, a UPS) can be added. */
export function HomeLabScreen() {
  const res = useResource<HomeLab>("homelab", () => homelab.get(), { staleMs: 60_000 });
  const [editing, setEditing] = useState<LabNode | null>(null);
  const [adding, setAdding] = useState(false);
  useEffect(() => { document.title = "Home Lab · SirisOS"; }, []);
  const d = res.data;
  const apply = (next: HomeLab) => { res.mutate?.(next); setEditing(null); setAdding(false); };
  return (
    <>
      <PageHead eyebrow={d ? `${d.nodes.length - 1} pieces of hardware · ${d.clients.online} other devices online` : "Hardware"} title="Home Lab" />
      {!d && res.error && <div className="error-banner" role="alert">{res.error}</div>}
      {!d && !res.error && <div className="skeleton" style={{ height: 260, marginTop: 16 }} aria-busy="true" />}
      {d && (
        <div className="stack" style={{ marginTop: 16 }}>
          <Glass as="section" className="widget lab" style={{ minHeight: 0 }} aria-label="Home Lab diagram">
            <header className="widget__head"><Network aria-hidden="true" /><span>How it connects</span>
              <button type="button" className="widget__source icon-link" onClick={() => setAdding(true)}><Plus size={13} aria-hidden="true" /> Add hardware</button></header>
            <Diagram d={d} onPick={setEditing} />
            <Tree d={d} onPick={setEditing} />
            <p className="muted" style={{ margin: 0, fontSize: 12 }}>
              Dashed lines are guesses: tap a box to say what it plugs into, and add its model and notes.
              {!d.sources.network && " The network watch hasn't seen your UniFi network yet."}
              {!d.sources.servers && " Servers come from the terminal's machines (SIRISOS_TERMINAL_HOSTS)."}
            </p>
          </Glass>
          <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Hardware list">
            <header className="widget__head"><Server aria-hidden="true" /><span>Hardware</span></header>
            <ul className="items">
              {d.nodes.filter((n) => n.kind !== "internet").map((n) => {
                const Icon = ICON[n.kind];
                const parent = d.nodes.find((p) => p.id === n.parent);
                return (
                  <li key={n.id} className="item">
                    <Icon size={16} className={n.online === false ? "tone-critical" : "muted"} aria-hidden="true" />
                    <span className="item__text">
                      <span className="item__title">{n.label}{n.model ? <span className="muted"> · {n.model}</span> : null}</span>
                      <span className="item__subtitle">{KIND_LABEL[n.kind]}{parent ? ` · into ${parent.label}${n.parent_guessed ? " (guessed)" : ""}` : ""}{n.detail ? ` · ${n.detail}` : ""}{n.online === false ? " · offline" : ""}</span>
                    </span>
                    <button type="button" className="button button--small" onClick={() => setEditing(n)} aria-label={`Edit ${n.label}`}>Edit</button>
                  </li>
                );
              })}
            </ul>
          </Glass>
        </div>
      )}
      {d && editing && <EditSheet d={d} node={editing} onClose={() => setEditing(null)} onSaved={apply} />}
      {d && adding && <AddSheet d={d} onClose={() => setAdding(false)} onSaved={apply} />}
    </>
  );
}

function Diagram({ d, onPick }: { d: HomeLab; onPick: (n: LabNode) => void }) {
  const { placed, width, height } = layout(d.nodes);
  const at = new Map(placed.map((p) => [p.id, p]));
  const pad = 8;
  return (
    <div className="lab__scroll">
      <svg className="lab__svg" width={width + pad * 2} height={height + pad * 2} viewBox={`${-pad} ${-pad} ${width + pad * 2} ${height + pad * 2}`}
        role="img" aria-label={`Home Lab: ${placed.map((p) => `${p.label}${p.parent && at.get(p.parent) ? ` into ${at.get(p.parent)!.label}` : ""}`).join("; ")}`}>
        {placed.filter((p) => p.parent && at.has(p.parent)).map((p) => {
          const q = at.get(p.parent!)!;
          const x1 = q.x + W / 2, y1 = q.y + H, x2 = p.x + W / 2, y2 = p.y;
          const mid = (y1 + y2) / 2;
          return <path key={`e-${p.id}`} className={`lab__edge ${p.parent_guessed ? "lab__edge--guess" : ""}`} d={`M${x1},${y1} V${mid} H${x2} V${y2}`} />;
        })}
        {placed.map((p) => {
          const Icon = ICON[p.kind];
          return (
            <g key={p.id} transform={`translate(${p.x},${p.y})`} className="lab__node" role="button" tabIndex={0} aria-label={`${p.label}: edit`}
              onClick={() => p.kind !== "internet" && onPick(p)} onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && p.kind !== "internet") onPick(p); }}>
              <rect width={W} height={H} rx={14} className={`lab__box lab__box--${p.kind}`} />
              <foreignObject x={10} y={10} width={W - 20} height={H - 20}>
                <div className="lab__label">
                  <Icon size={16} aria-hidden="true" />
                  <span className="lab__text"><strong>{p.label}</strong><span>{p.model || p.detail || KIND_LABEL[p.kind]}</span></span>
                </div>
              </foreignObject>
              {p.online !== null && <circle cx={W - 10} cy={10} r={4} className={p.online ? "lab__dot--on" : "lab__dot--off"} />}
            </g>
          );
        })}
      </svg>
      {d.clients.total > 0 && <p className="muted lab__clients">Plus {d.clients.total} other device{d.clients.total === 1 ? "" : "s"} on the network ({d.clients.online} online now).</p>}
    </div>
  );
}

/** Phones (8.5): the same connections as an indented tree, which fits the width the diagram doesn't. */
function Tree({ d, onPick }: { d: HomeLab; onPick: (n: LabNode) => void }) {
  const kids = (id: string | null) => d.nodes.filter((n) => n.parent === id);
  const branch = (n: LabNode, seen: Set<string>): JSX.Element => {
    const Icon = ICON[n.kind];
    const under = kids(n.id).filter((c) => !seen.has(c.id));
    return (
      <li key={n.id}>
        <button type="button" className={`lab__tree-node ${n.parent_guessed ? "lab__tree-node--guess" : ""}`} disabled={n.kind === "internet"} onClick={() => onPick(n)}>
          <Icon size={15} aria-hidden="true" />
          <span className="lab__text"><strong>{n.label}</strong><span>{n.model || n.detail || KIND_LABEL[n.kind]}</span></span>
          {n.online !== null && <span className={`lab__tree-dot ${n.online ? "lab__dot--on" : "lab__dot--off"}`} aria-label={n.online ? "online" : "offline"} />}
        </button>
        {under.length > 0 && <ul>{under.map((c) => branch(c, new Set([...seen, c.id])))}</ul>}
      </li>
    );
  };
  return (
    <div className="lab__tree" aria-label="How it connects, as a list">
      <ul>{kids(null).map((r) => branch(r, new Set([r.id])))}</ul>
      {d.clients.total > 0 && <p className="muted lab__clients">Plus {d.clients.total} other device{d.clients.total === 1 ? "" : "s"} ({d.clients.online} online now).</p>}
    </div>
  );
}

function ParentSelect({ d, value, exclude, onChange }: { d: HomeLab; value: string; exclude?: string; onChange: (v: string) => void }) {
  return (
    <label className="protocol__field"><span>Plugs into</span>
      <select className="field" value={value} onChange={(e) => onChange(e.target.value)} aria-label="Plugs into">
        {d.nodes.filter((n) => n.id !== exclude).map((n) => <option key={n.id} value={n.id}>{n.label} ({KIND_LABEL[n.kind]})</option>)}
      </select>
    </label>
  );
}

function EditSheet({ d, node, onClose, onSaved }: { d: HomeLab; node: LabNode; onClose: () => void; onSaved: (h: HomeLab) => void }) {
  const [label, setLabel] = useState(node.label);
  const [model, setModel] = useState(node.model ?? "");
  const [notes, setNotes] = useState(node.notes ?? "");
  const [parent, setParent] = useState(node.parent ?? "internet");
  const [error, setError] = useState<string | null>(null);
  const mine = node.found === "you";
  const save = async () => {
    try { onSaved(await homelab.change(node.id, { label, model, notes, parent })); } catch (e) { setError(e instanceof Error ? e.message : "Couldn't save it."); }
  };
  return (
    <Sheet label={`Edit ${node.label}`} onClose={onClose}>
      <h2 className="sheet__title">{node.label}</h2>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>{KIND_LABEL[node.kind]}{node.detail ? ` · ${node.detail}` : ""} · {mine ? "added by you" : `from ${node.found === "network" ? "the network watch" : node.found === "terminal" ? "the terminal's machines" : "SirisAI"}`}</p>
      <div className="stack" style={{ gap: 8, marginTop: 12 }}>
        <label className="protocol__field"><span>Name</span><input className="field" value={label} onChange={(e) => setLabel(e.target.value)} aria-label="Name" /></label>
        <label className="protocol__field"><span>Model</span><input className="field" value={model} placeholder="e.g. UniFi Dream Machine Pro" onChange={(e) => setModel(e.target.value)} aria-label="Model" /></label>
        <label className="protocol__field"><span>Notes</span><textarea className="field" rows={3} value={notes} placeholder="Where it is, what's on it, specs" onChange={(e) => setNotes(e.target.value)} aria-label="Notes" /></label>
        <ParentSelect d={d} value={parent} exclude={node.id} onChange={setParent} />
      </div>
      {error && <div className="error-banner" role="alert" style={{ marginTop: 10 }}>{error}</div>}
      <div className="row" style={{ justifyContent: "space-between", marginTop: 16, gap: 8 }}>
        {mine ? <button type="button" className="button button--small" onClick={async () => onSaved(await homelab.remove(node.id))}>Remove</button> : <span />}
        <span className="row" style={{ gap: 6 }}>
          <button type="button" className="button button--small" onClick={onClose}>Cancel</button>
          <button type="button" className="button button--small button--primary" onClick={save}>Save</button>
        </span>
      </div>
    </Sheet>
  );
}

function AddSheet({ d, onClose, onSaved }: { d: HomeLab; onClose: () => void; onSaved: (h: HomeLab) => void }) {
  const [label, setLabel] = useState("");
  const [kind, setKind] = useState<LabKind>("modem");
  const [parent, setParent] = useState("internet");
  return (
    <Sheet label="Add hardware" onClose={onClose}>
      <h2 className="sheet__title">Add hardware</h2>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Something SirisOS can't see on the network: the modem, a UPS, a NAS, a second switch.</p>
      <div className="stack" style={{ gap: 8, marginTop: 12 }}>
        <label className="protocol__field"><span>Name</span><input className="field" value={label} placeholder="e.g. NBN modem" onChange={(e) => setLabel(e.target.value)} aria-label="Name" /></label>
        <div className="row gym-chips" role="radiogroup" aria-label="What it is">
          {ADDABLE.map((k) => <button key={k} type="button" role="radio" aria-checked={kind === k} className={`chip chip--button ${kind === k ? "chip--active" : ""}`} onClick={() => setKind(k)}>{KIND_LABEL[k]}</button>)}
        </div>
        <ParentSelect d={d} value={parent} onChange={setParent} />
      </div>
      <div className="row" style={{ justifyContent: "flex-end", marginTop: 16, gap: 6 }}>
        <button type="button" className="button button--small" onClick={onClose}>Cancel</button>
        <button type="button" className="button button--small button--primary" disabled={!label.trim()} onClick={async () => onSaved(await homelab.add(label.trim(), kind, parent))}>Add</button>
      </div>
    </Sheet>
  );
}
