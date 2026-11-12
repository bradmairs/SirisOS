import { useEffect, useState, type FormEvent } from "react";
import { Cake, Gift, Package, Trash2 } from "lucide-react";
import { useResource } from "../api/resource";
import { people, things, type Person, type Thing } from "../api/life";
import { Glass } from "../components/Glass";
import { categoryOf, LatestThenGrouped } from "../components/Grouped";
import { Sheet } from "../components/Sheet";
import { ReceiptView } from "./ReceiptView";

const day = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

function warranty(t: Thing): { text: string; tone?: "good" | "warning" | "critical" } {
  if (!t.warranty_until) return { text: "No warranty recorded" };
  const left = t.warranty_days_left ?? 0;
  if (left < 0) return { text: `Warranty ended ${day(t.warranty_until)}`, tone: "critical" };
  if (left <= 30) return { text: `⚠ Warranty ends in ${left} day${left === 1 ? "" : "s"}`, tone: "warning" };
  return { text: `✓ Under warranty until ${day(t.warranty_until)}`, tone: "good" };
}

/** The return window (8.9, SirisAI 5.94): shown while it's open. */
function returnBy(t: Thing): { text: string; tone?: "warning" } | null {
  if (!t.return_until || (t.return_days_left ?? -1) < 0) return null;
  const left = t.return_days_left ?? 0;
  return { text: left === 0 ? "Last day to return it: today" : `Can go back until ${day(t.return_until)} (${left} day${left === 1 ? "" : "s"})`, tone: left <= 3 ? "warning" : undefined };
}

/** Newest first: by when it was bought, then by when it was added. */
const newestThing = (a: Thing, b: Thing) => (b.bought ?? "").localeCompare(a.bought ?? "") || b.id - a.id;

/** What you own, its warranty and its manual (7.7, SirisAI 5.0). Receipts added under Life Admin fill this in too. */
export function ThingsCard() {
  const [q, setQ] = useState("");
  const { data, reload } = useResource(`things:${q}`, () => things.list(q), { staleMs: 30_000 });
  const [adding, setAdding] = useState(false);
  const [receipt, setReceipt] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", brand: "", bought: "", warranty_months: "", manual: "", room: "" });
  const [returning, setReturning] = useState<number | null>(null);
  const recent = new Date(Date.now() - 60 * 86_400_000).toISOString().slice(0, 10);  // only bought lately: older ones can't go back  // the thing whose return date is being set (8.9)
  const [error, setError] = useState<string | null>(null);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await things.add({ name: form.name, brand: form.brand || undefined, room: form.room || undefined, bought: form.bought || undefined,
        warranty_months: form.warranty_months ? Number(form.warranty_months) : undefined, manual: form.manual || undefined });
      setForm({ name: "", brand: "", bought: "", warranty_months: "", manual: "", room: "" });
      setAdding(false);
      await reload(true);
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^SirisAI: /, "") : String(err));
    }
  }

  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Things you own">
      <header className="widget__head"><Package aria-hidden="true" /><span>Things you own</span>
        <button type="button" className="button button--small" style={{ marginLeft: "auto" }} onClick={() => setAdding(!adding)}>{adding ? "Cancel" : "Add"}</button>
      </header>
      {adding && (
        <form className="stack" style={{ gap: 6 }} onSubmit={add} aria-label="Add a thing">
          <input className="field" required placeholder="What (e.g. Dishwasher)" aria-label="What" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
            <input className="field" placeholder="Brand" aria-label="Brand" value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} />
            <input className="field" placeholder="Room" aria-label="Room" value={form.room} onChange={(e) => setForm({ ...form, room: e.target.value })} />
            <input className="field" type="date" aria-label="Bought" value={form.bought} onChange={(e) => setForm({ ...form, bought: e.target.value })} />
            <input className="field" type="number" min={0} placeholder="Warranty (months)" aria-label="Warranty in months" value={form.warranty_months} onChange={(e) => setForm({ ...form, warranty_months: e.target.value })} />
          </div>
          <input className="field" placeholder="Manual: a link, or where the paper one is" aria-label="Manual" value={form.manual} onChange={(e) => setForm({ ...form, manual: e.target.value })} />
          {error && <p className="tone-critical" role="alert" style={{ margin: 0 }}>{error}</p>}
          <button type="submit" className="button button--small button--primary" disabled={!form.name.trim()}>Save</button>
        </form>
      )}
      <input className="field" type="search" placeholder="Find (e.g. dishwasher)" aria-label="Find a thing" value={q} onChange={(e) => setQ(e.target.value)} />
      {data && data.length === 0 ? (
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>{q ? "Nothing matches." : "Nothing yet. Receipts from your email or added under Life Admin show up here."}</p>
      ) : (
        <LatestThenGrouped items={data ?? []} label="things" newest={newestThing} category={(t) => categoryOf(t.name, t.brand, t.model, t.shop)}
          latest={q ? Number.MAX_SAFE_INTEGER : 5}
          render={(t) => {
            const w = warranty(t);
            return (
              <li key={t.id} className="item">
                <span className="item__text">
                  <div className="item__title">{t.name}{t.brand ? ` · ${t.brand}` : ""}{t.model ? ` ${t.model}` : ""}</div>
                  <div className="item__subtitle">
                    {[t.room, t.bought ? `bought ${day(t.bought)}` : "", t.price != null ? `$${t.price.toFixed(2)}` : ""].filter(Boolean).join(" · ")}
                  </div>
                  <div className={`item__subtitle${w.tone ? ` tone-${w.tone}` : ""}`}>{w.text}</div>
                  {(() => { const r = returnBy(t); return r ? <div className={`item__subtitle${r.tone ? ` tone-${r.tone}` : ""}`}>{r.text}</div> : null; })()}
                  {returning === t.id && (
                    <label className="row item__subtitle" style={{ gap: 6 }}>Return by
                      <input className="field" type="date" aria-label={`Return ${t.name} by`} defaultValue={t.return_until ?? ""}
                        onChange={async (e) => { await things.update(t.id, { return_until: e.target.value || null }); setReturning(null); await reload(true); }} /></label>
                  )}
                  {t.manual && (/^https?:/.test(t.manual)
                    ? <a className="item__subtitle" href={t.manual} target="_blank" rel="noreferrer">Manual</a>
                    : <div className="item__subtitle">Manual: {t.manual}</div>)}
                </span>
                {t.document_id != null && (
                  <button type="button" className="chip chip--button" aria-expanded={receipt === t.document_id} onClick={() => setReceipt(receipt === t.document_id ? null : t.document_id)}>Receipt</button>
                )}
                {returning !== t.id && t.bought && t.bought >= recent && (t.return_until == null || (t.return_days_left ?? -1) >= 0) && (
                  <button type="button" className="chip chip--button" aria-label={`Set when ${t.name} can be returned by`} onClick={() => setReturning(t.id)}>Return by</button>
                )}
                <button type="button" className="icon-link" aria-label={`Remove ${t.name}`} onClick={async () => { await things.remove(t.id); await reload(true); }}>
                  <Trash2 size={16} aria-hidden="true" />
                </button>
              </li>
            );
          }} />
      )}
      {receipt != null && <Sheet label="Receipt" onClose={() => setReceipt(null)}><ReceiptView id={receipt} /></Sheet>}
    </Glass>
  );
}

function when(p: Person): string {
  const bits = [];
  if (p.days_to_birthday != null) bits.push(`birthday ${p.days_to_birthday === 0 ? "today" : `in ${p.days_to_birthday} day${p.days_to_birthday === 1 ? "" : "s"}`}${p.turning ? ` (turning ${p.turning})` : ""}`);
  if (p.days_to_anniversary != null) bits.push(`anniversary in ${p.days_to_anniversary} days`);
  return bits.join(" · ");
}

/** Birthdays, anniversaries, gift ideas and catching up (7.7, SirisAI 5.0). */
export function PeopleCard() {
  const { data, reload } = useResource("people", () => people.list(), { staleMs: 60_000 });
  const [form, setForm] = useState({ name: "", birthday: "", relation: "" });
  const [open, setOpen] = useState<{ id: number; ideas: string[]; seen: string } | null>(null);

  async function add(e: FormEvent) {
    e.preventDefault();
    await people.add({ name: form.name, birthday: form.birthday || null, relation: form.relation });
    setForm({ name: "", birthday: "", relation: "" });
    await reload(true);
  }

  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="People">
      <header className="widget__head"><Cake aria-hidden="true" /><span>People</span></header>
      <ul className="items">
        {(data ?? []).map((p) => (
          <li key={p.id}>
            <div className="item">
              <span className="item__text">
                <div className="item__title">{p.name}{p.relation ? ` · ${p.relation}` : ""}</div>
                <div className="item__subtitle">{when(p) || "No dates yet"}</div>
              </span>
              <button type="button" className="icon-link" aria-label={`Gift ideas and catch-ups for ${p.name}`}
                onClick={async () => { if (open?.id === p.id) { setOpen(null); return; } const g = await people.gifts(p.id); setOpen({ id: p.id, ideas: g.ideas, seen: g.last_seen.text }); }}>
                <Gift size={16} aria-hidden="true" />
              </button>
              <button type="button" className="icon-link" aria-label={`Remove ${p.name}`} onClick={async () => { await people.remove(p.id); await reload(true); }}>
                <Trash2 size={16} aria-hidden="true" />
              </button>
            </div>
            {open?.id === p.id && (
              <div style={{ padding: "0 12px 10px", fontSize: 14 }}>
                <p style={{ margin: "0 0 4px" }}><strong>Last caught up:</strong> {open.seen}</p>
                <p style={{ margin: 0 }}><strong>Gift ideas:</strong> {open.ideas.length ? open.ideas.join("; ") : "Nothing in your notes yet. Tell SirisAI what they like."}</p>
                <button type="button" className="button button--small" style={{ marginTop: 6 }}
                  onClick={async () => { await people.update(p.id, { last_contact: new Date().toISOString().slice(0, 10) }); setOpen(null); await reload(true); }}>Caught up today</button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <form className="row" style={{ gap: 6, flexWrap: "wrap" }} onSubmit={add} aria-label="Add a person">
        <input className="field" required placeholder="Name" aria-label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input className="field" type="date" aria-label="Birthday" value={form.birthday} onChange={(e) => setForm({ ...form, birthday: e.target.value })} />
        <input className="field" placeholder="Relation" aria-label="Relation" value={form.relation} onChange={(e) => setForm({ ...form, relation: e.target.value })} />
        <button type="submit" className="button button--small" disabled={!form.name.trim()}>Add</button>
      </form>
    </Glass>
  );
}

export function ThingsScreen() {
  useEffect(() => {
    document.title = "Things & People · SirisOS";
  }, []);
  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">From SirisAI</p>
          <h1 className="page-head__title">Things &amp; People</h1>
        </div>
      </header>
      <div className="stack" style={{ marginTop: 16 }}>
        <ThingsCard />
        <PeopleCard />
      </div>
    </>
  );
}
