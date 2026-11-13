import { useState } from "react";
import { IdCard, Trash2 } from "lucide-react";
import { renewals, type Renewal, type RenewalKind } from "../api/renewals";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

const KINDS: [RenewalKind, string][] = [["passport", "Passport"], ["licence", "Driver's licence"], ["rego", "Car rego"], ["insurance", "Insurance"],
  ["medicare", "Medicare card"], ["warranty", "Warranty"], ["membership", "Membership"], ["other", "Other"]];
const day = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const when = (r: Renewal) => (r.days_left < 0 ? `expired ${-r.days_left} day${r.days_left === -1 ? "" : "s"} ago` : r.days_left === 0 ? "expires today"
  : r.days_left <= 90 ? `in ${r.days_left} day${r.days_left === 1 ? "" : "s"}` : day(r.expires));

/** Documents and renewals (9.3): passport, licence, rego, insurance and the like, soonest first. Reminders come 60, 30
 * and 7 days before and on the day; renewed, so tap the date and set the new one. */
export function RenewalsCard() {
  const res = useResource<{ renewals: Renewal[] }>("renewals", () => renewals.list(), { staleMs: 60_000, persist: true });
  const items = res.data?.renewals ?? [];
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", kind: "passport" as RenewalKind, expires: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const run = async (fn: () => Promise<{ renewals: Renewal[] }>, done?: string) => {
    setMsg(null);
    try { res.mutate?.(await fn()); if (done) setMsg(done); } catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't save that."); }
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Documents and renewals">
      <header className="widget__head"><IdCard aria-hidden="true" /><span>Documents and renewals</span></header>
      {res.data && !items.length && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Passport, licence, car rego, insurance, Medicare: add their expiry dates and SirisOS reminds you 60, 30 and 7 days before.</p>}
      {items.length > 0 && (
        <ul className="items">
          {items.map((r) => (
            <li key={r.id} className="item">
              <span className="item__text">
                <span className="item__title">{r.name}</span>
                <span style={{ whiteSpace: "normal" }} className={`item__subtitle ${r.state === "expired" ? "tone-critical" : r.state === "soon" ? "tone-warning" : ""}`}>
                  {KINDS.find(([k]) => k === r.kind)?.[1]} · {when(r)}{r.note ? ` · ${r.note}` : ""}</span>
              </span>
              <input className="field renewal-date" type="date" aria-label={`${r.name} expires`} value={r.expires}
                onChange={(e) => { if (e.target.value) run(() => renewals.change(r.id, { expires: e.target.value }), `${r.name}: now ${day(e.target.value)}.`); }} />
              <button type="button" className="icon-link" aria-label={`Remove ${r.name}`} onClick={() => { if (window.confirm(`Remove ${r.name}?`)) run(() => renewals.remove(r.id)); }}><Trash2 size={14} aria-hidden="true" /></button>
            </li>
          ))}
        </ul>
      )}
      {adding ? (
        <form className="stack" style={{ gap: 8 }} onSubmit={(e) => {
          e.preventDefault();
          if (!form.name.trim() || !form.expires) { setMsg("A name and an expiry date."); return; }
          run(() => renewals.add({ ...form, name: form.name.trim() })).then(() => { setAdding(false); setForm({ name: "", kind: "passport", expires: "" }); });
        }}>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <select className="field" aria-label="What it is" value={form.kind} onChange={(e) => {
              const kind = e.target.value as RenewalKind;
              const label = KINDS.find(([k]) => k === kind)![1];
              setForm({ ...form, kind, name: !form.name || KINDS.some(([, l]) => l === form.name) ? label : form.name });
            }}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <input className="field" style={{ flex: 1, minWidth: 140 }} placeholder="Name, e.g. Car rego (Corolla)" aria-label="Name" value={form.name} maxLength={80} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input className="field" type="date" aria-label="Expires" value={form.expires} onChange={(e) => setForm({ ...form, expires: e.target.value })} />
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button type="submit" className="button button--primary">Add</button>
            <button type="button" className="button" onClick={() => setAdding(false)}>Cancel</button>
          </div>
        </form>
      ) : <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => { setAdding(true); setForm({ name: "Passport", kind: "passport", expires: "" }); }}>Add one</button>}
      {msg && <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
    </Glass>
  );
}
