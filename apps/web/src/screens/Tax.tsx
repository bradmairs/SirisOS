import { useEffect, useRef, useState } from "react";
import { Calculator, Car, House, Inbox, Paperclip, Plus, ReceiptText, Trash2 } from "lucide-react";
import { useResource } from "../api/resource";
import { tax, type TaxClaim, type TaxClaimInput, type TaxToSort, type TaxYear } from "../api/tax";
import { life } from "../api/life";
import { Glass } from "../components/Glass";
import { SaveButton } from "../components/SaveButton";
import { undoable } from "../components/Undo";

/** Tax-claimable receipts (11.18): work-related deductions for an Australian tax return, a financial year at a time.
 * Receipts kept from email wait to be sorted (claim it, or not a tax one); others are added by hand with a photo or PDF.
 * The ATO's rules are applied as you go: the $300 written-evidence threshold, items over $300 depreciated, the work
 * share, reimbursed costs, the 70c-an-hour working from home rate and 88c a km. */

const money = (n: number) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const day = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const today = () => new Date().toLocaleDateString("en-CA");

export function TaxScreen() {
  useEffect(() => { document.title = "Tax · SirisOS"; }, []);
  const [fy, setFy] = useState<number | undefined>(undefined);
  const res = useResource(`tax:${fy ?? "now"}`, () => tax.year(fy), { staleMs: 30_000 });
  const y = res.data;
  const reload = () => void res.reload(true);
  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">Budget</p>
          <h1 className="page-head__title">Tax claims</h1>
        </div>
        {y && (
          <select className="field" style={{ width: "auto" }} aria-label="Financial year" value={y.fy} onChange={(e) => setFy(Number(e.target.value))}>
            {y.years.map((f) => <option key={f} value={f}>{`${f - 1}-${String(f).slice(-2)}`}</option>)}
          </select>
        )}
      </header>
      {res.error && !y && <p className="muted" role="alert">Couldn't load your tax claims: {res.error}</p>}
      {y && (
        <div className="stack" style={{ marginTop: 16 }}>
          <Summary y={y} />
          <ToSort y={y} onChange={reload} />
          <AddClaim y={y} onAdded={reload} />
          <Claims y={y} onChange={reload} />
          <HomeAndCar y={y} onChange={reload} />
          <p className="muted" style={{ fontSize: 12, margin: 0 }}>
            A record-keeper, not tax advice. Rates are the ATO's for 2025-26. Keep receipts for five years from when you lodge, and check
            anything you're unsure of with the ATO or a registered tax agent.
          </p>
        </div>
      )}
    </>
  );
}

function Summary({ y }: { y: TaxYear }) {
  const deps = y.claims.filter((c) => c.treatment === "depreciate");
  return (
    <Glass as="section" className="widget" aria-label="This year's claims">
      <header className="widget__head"><Calculator aria-hidden="true" /><span>{y.label}: 1 July to 30 June</span>
        <SaveButton label="Export CSV" get={() => tax.export(y.fy)} />
      </header>
      <div className="row" style={{ gap: 24, flexWrap: "wrap", alignItems: "baseline" }}>
        <div><div className="muted" style={{ fontSize: 13 }}>To claim this year</div><div style={{ fontSize: 28, fontWeight: 600 }} aria-label="Total to claim">{money(y.total)}</div></div>
        <div><div className="muted" style={{ fontSize: 13 }}>Work-related</div><div style={{ fontSize: 18, fontWeight: 600 }}>{money(y.work_total)}</div></div>
        {deps.length > 0 && <div><div className="muted" style={{ fontSize: 13 }}>To depreciate</div><div style={{ fontSize: 18, fontWeight: 600 }}>{deps.length} item{deps.length === 1 ? "" : "s"}</div></div>}
      </div>
      {y.by_category.length > 0 && (
        <ul className="budget-split__lines" aria-label="By category">
          {y.by_category.map((b) => <li key={b.category}><span>{b.label} ({b.count})</span><span>{money(b.claimable)}</span></li>)}
          {y.wfh.claimable > 0 && <li><span>Working from home ({y.wfh.hours} h)</span><span>{money(y.wfh.claimable)}</span></li>}
          {y.car.claimable > 0 && <li><span>Car ({Math.min(y.car.km, y.car.cap)} km)</span><span>{money(y.car.claimable)}</span></li>}
        </ul>
      )}
      {y.checks.map((c, i) => (
        <p key={i} role={c.level === "warn" ? "alert" : undefined} style={{ margin: 0, fontSize: 14, padding: "8px 12px", borderRadius: 12,
          background: `color-mix(in srgb, ${c.level === "warn" ? "var(--warning, #f5a524)" : c.level === "ok" ? "var(--good, #30a46c)" : "var(--accent)"} 14%, transparent)` }}>{c.text}</p>
      ))}
    </Glass>
  );
}

function ToSort({ y, onChange }: { y: TaxYear; onChange: () => void }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!y.to_sort.length && !y.email_problem) return null;
  return (
    <Glass as="section" className="widget" aria-label="Receipts to sort">
      <header className="widget__head"><Inbox aria-hidden="true" /><span>Receipts from email to sort ({y.to_sort.length})</span></header>
      {y.email_problem && <p className="muted" style={{ margin: 0, fontSize: 14 }}>Couldn't reach your email receipts just now ({y.email_problem}).</p>}
      {y.to_sort.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 14 }}>This year's receipts kept from email. Claim the ones for work; the rest are put aside.</p>}
      <ul className="items">
        {y.to_sort.map((r) => (
          <li key={r.doc_id}>
            <div className="item">
              <span className="item__text">
                <div className="item__title">{r.vendor || r.description}{r.amount != null ? ` · ${money(r.amount)}` : ""}</div>
                <div className="item__subtitle">{day(r.date)}{r.vendor && r.description ? ` · ${r.description}` : ""}</div>
              </span>
              <span className="row" style={{ gap: 6 }}>
                <button type="button" className="button button--small button--primary" aria-label={`Claim ${r.vendor || r.description}`} onClick={() => setOpen(open === r.doc_id ? null : r.doc_id)}>Claim</button>
                <button type="button" className="button button--small" aria-label={`${r.vendor || r.description} isn't a tax receipt`}
                  onClick={() => undoable({ text: `Put ${r.vendor || "the receipt"} aside`, run: async () => { await tax.notTax(r.doc_id); onChange(); } })}>Not tax</button>
              </span>
            </div>
            {open === r.doc_id && <ClaimForm y={y} from={r} onSaved={() => { setOpen(null); onChange(); }} onCancel={() => setOpen(null)} />}
          </li>
        ))}
      </ul>
    </Glass>
  );
}

function AddClaim({ y, onAdded }: { y: TaxYear; onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <Glass as="section" className="widget" aria-label="Add a claim">
      <header className="widget__head"><Plus aria-hidden="true" /><span>Add a receipt by hand</span>
        {!open && <button type="button" className="button button--small" onClick={() => setOpen(true)}>Add</button>}
      </header>
      {!open && <p className="muted" style={{ margin: 0, fontSize: 14 }}>A paper receipt, a card payment with no email, or something under $10 for your diary.</p>}
      {open && <ClaimForm y={y} onSaved={() => { setOpen(false); onAdded(); }} onCancel={() => setOpen(false)} />}
    </Glass>
  );
}

function ClaimForm({ y, from, claim, onSaved, onCancel }: { y: TaxYear; from?: TaxToSort; claim?: TaxClaim; onSaved: () => void; onCancel: () => void }) {
  const [f, setF] = useState<TaxClaimInput>(() => claim ? { ...claim } : {
    date: from?.date ?? today(), vendor: from?.vendor ?? "", description: from?.description ?? "", amount: from?.amount ?? undefined,
    category: from?.category ?? "equipment", work_pct: 100, reimbursed: false, has_receipt: !!from, doc_id: from?.doc_id ?? null,
  });
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const set = (patch: TaxClaimInput) => setF((x) => ({ ...x, ...patch }));
  const hint = y.categories.find((c) => c.id === f.category)?.hint;
  const id = claim?.id ?? from?.doc_id ?? "new";

  async function save() {
    setBusy(true); setError(null);
    try {
      let body = f;
      if (file) {
        const doc = await life.addDocument(file);   // kept with your other documents, and linked to the claim
        body = { ...f, doc_id: doc.id, has_receipt: true };
      }
      if (claim) await tax.change(claim.id, body); else await tax.add(body);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save it.");
    } finally { setBusy(false); }
  }

  return (
    <div className="stack" style={{ gap: 8, padding: "8px 0" }} role="form" aria-label={claim ? "Change the claim" : "The claim"}>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <input className="field" style={{ flex: "1 1 140px" }} type="date" aria-label="Date" value={f.date ?? ""} onChange={(e) => set({ date: e.target.value })} />
        <input className="field" style={{ flex: "1 1 120px" }} inputMode="decimal" aria-label="Amount" placeholder="Amount $" value={f.amount ?? ""}
          onChange={(e) => set({ amount: e.target.value === "" ? undefined : Number(e.target.value.replace(/[$,]/g, "")) })} />
      </div>
      <input className="field" aria-label="From" placeholder="Who it's from (the shop)" value={f.vendor ?? ""} onChange={(e) => set({ vendor: e.target.value })} />
      <input className="field" aria-label="What it was" placeholder="What it was" value={f.description ?? ""} onChange={(e) => set({ description: e.target.value })} />
      <select className="field" aria-label="Category" value={f.category} onChange={(e) => set({ category: e.target.value })}>
        {y.categories.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
      </select>
      {hint && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{hint}</p>}
      <label className="row" style={{ gap: 8, fontSize: 14 }}>
        <span>For work</span>
        <input type="range" min={0} max={100} step={5} aria-label="Work share" value={f.work_pct ?? 100} onChange={(e) => set({ work_pct: Number(e.target.value) })} style={{ flex: 1 }} />
        <span style={{ width: 44, textAlign: "right" }}>{f.work_pct ?? 100}%</span>
      </label>
      <div className="row" style={{ gap: 16, flexWrap: "wrap", fontSize: 14 }}>
        <label className="row" style={{ gap: 6 }}><input type="checkbox" checked={!!f.has_receipt} onChange={(e) => set({ has_receipt: e.target.checked })} />I have the receipt</label>
        <label className="row" style={{ gap: 6 }}><input type="checkbox" checked={!!f.reimbursed} onChange={(e) => set({ reimbursed: e.target.checked })} />Work paid me back</label>
        {f.category === "equipment" && <label className="row" style={{ gap: 6 }}><input type="checkbox" checked={!!f.set_item} onChange={(e) => set({ set_item: e.target.checked })} />Part of a set</label>}
      </div>
      {!f.doc_id && (
        <div className="row" style={{ gap: 8 }}>
          <input ref={picker} type="file" accept="image/*,application/pdf" hidden aria-label={`Receipt file ${id}`} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button type="button" className="button button--small" onClick={() => picker.current?.click()}><Paperclip size={14} aria-hidden="true" /> {file ? file.name : "Attach a photo or PDF"}</button>
        </div>
      )}
      <input className="field" aria-label="Note" placeholder="Note (how you worked out the work share)" value={f.note ?? ""} onChange={(e) => set({ note: e.target.value })} />
      {error && <p role="alert" style={{ margin: 0, fontSize: 14 }}>{error}</p>}
      <div className="row" style={{ gap: 8 }}>
        <button type="button" className="button button--small button--primary" disabled={busy || !f.amount || !(f.vendor || f.description)} onClick={() => void save()}>{busy ? "Saving…" : claim ? "Save" : "Add the claim"}</button>
        <button type="button" className="button button--small" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

function Claims({ y, onChange }: { y: TaxYear; onChange: () => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [gone, setGone] = useState<Set<string>>(new Set());
  const list = y.claims.filter((c) => !gone.has(c.id));
  const missing = new Set(y.missing_receipts);
  return (
    <Glass as="section" className="widget" aria-label="Claims">
      <header className="widget__head"><ReceiptText aria-hidden="true" /><span>Claims ({list.length})</span>
        {list.some((c) => c.doc_id) && (
          <SaveButton label="Receipts (zip)" get={() => life.downloadReceipts({ ids: list.map((c) => c.doc_id).filter((d): d is number => !!d) })} />
        )}
      </header>
      {!list.length && <p className="muted" style={{ margin: 0, fontSize: 14 }}>Nothing claimed for {y.label} yet.</p>}
      <ul className="items">
        {list.map((c) => (
          <li key={c.id}>
            <button type="button" className="item item--button" aria-expanded={open === c.id} onClick={() => setOpen(open === c.id ? null : c.id)}>
              <span className="item__text">
                <div className="item__title">{c.vendor || c.description} · {money(c.claimable)}{c.work_pct < 100 && !c.reimbursed ? ` (${c.work_pct}% of ${money(c.amount)})` : ""}</div>
                <div className="item__subtitle">
                  {day(c.date)} · {y.categories.find((k) => k.id === c.category)?.label}
                  {c.treatment === "depreciate" ? " · depreciate" : ""}{missing.has(c.id) ? " · no receipt" : ""}{c.source === "email" ? " · from email" : ""}
                </div>
                {c.treatment_note && <div className="item__subtitle">{c.treatment_note}</div>}
              </span>
            </button>
            {open === c.id && (
              <div style={{ padding: "0 12px 12px" }}>
                <ClaimForm y={y} claim={c} onSaved={() => { setOpen(null); onChange(); }} onCancel={() => setOpen(null)} />
                <button type="button" className="button button--small" aria-label={`Remove the claim for ${c.vendor || c.description}`}
                  onClick={() => { setOpen(null); undoable({ text: `Removed ${c.vendor || "the claim"}`, run: async () => { await tax.remove(c.id); onChange(); },
                    hide: () => setGone((g) => new Set(g).add(c.id)), restore: () => setGone((g) => { const n = new Set(g); n.delete(c.id); return n; }) }); }}>
                  <Trash2 size={14} aria-hidden="true" /> Remove
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Glass>
  );
}

function HomeAndCar({ y, onChange }: { y: TaxYear; onChange: () => void }) {
  const [hours, setHours] = useState(y.wfh.hours ? String(y.wfh.hours) : "");
  const [km, setKm] = useState(y.car.km ? String(y.car.km) : "");
  useEffect(() => { setHours(y.wfh.hours ? String(y.wfh.hours) : ""); setKm(y.car.km ? String(y.car.km) : ""); }, [y.fy, y.wfh.hours, y.car.km]);
  async function save(body: { wfh_hours?: number; car_km?: number }) { await tax.setYear(y.fy, body); onChange(); }
  return (
    <Glass as="section" className="widget" aria-label="Working from home and car">
      <header className="widget__head"><House aria-hidden="true" /><span>Working from home and the car</span></header>
      <label className="stack" style={{ gap: 4, fontSize: 14 }}>
        <span>Hours worked from home this year (fixed rate, 70c an hour: covers power, internet, phone and stationery)</span>
        <input className="field" inputMode="decimal" aria-label="Hours worked from home" value={hours} placeholder="0"
          onChange={(e) => setHours(e.target.value)} onBlur={() => void save({ wfh_hours: Number(hours || 0) })} />
      </label>
      <label className="stack" style={{ gap: 4, fontSize: 14 }}>
        <span><Car size={14} aria-hidden="true" /> Work kilometres in your own car (88c a km, up to 5,000 km; not home to work)</span>
        <input className="field" inputMode="decimal" aria-label="Work kilometres" value={km} placeholder="0"
          onChange={(e) => setKm(e.target.value)} onBlur={() => void save({ car_km: Number(km || 0) })} />
      </label>
    </Glass>
  );
}
