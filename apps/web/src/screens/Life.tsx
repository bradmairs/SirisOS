import { useEffect, useRef, useState } from "react";
import { FileText, Plane, Receipt, Trash2, Upload } from "lucide-react";
import { useResource } from "../api/resource";
import { life, type Bill, type Doc, type Trip } from "../api/life";
import { Glass } from "../components/Glass";

function day(iso: string) {
  return new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

const money = (n: number | null | undefined) => (n == null ? "" : `$${n.toFixed(2)}`);

/** Letters and bills (7.3): add a photo or PDF, and SirisAI reads it, files it in Siris and reminds you of what's due. */
export function DocumentsCard() {
  const [q, setQ] = useState("");
  const { data, reload } = useResource(`life:documents:${q}`, () => life.documents(q), { staleMs: 30_000 });
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ tone: "good" | "critical"; text: string } | null>(null);
  const [open, setOpen] = useState<Doc | null>(null);
  const picker = useRef<HTMLInputElement>(null);

  async function add(file: File) {
    setBusy(true);
    setNote(null);
    try {
      const doc = await life.addDocument(file);
      const due = doc.due[0];
      setNote({
        tone: "good",
        text: `Filed "${doc.title}".` + (due ? ` Due ${day(due.date)}${due.amount ? ` (${money(due.amount)})` : ""}; ${doc.reminders ?? 0} reminders set.` : ""),
      });
      await reload(true);
    } catch (e) {
      setNote({ tone: "critical", text: e instanceof Error ? e.message.replace(/^SirisAI: /, "") : String(e) });
    } finally {
      setBusy(false);
      if (picker.current) picker.current.value = "";
    }
  }

  async function remove(doc: Doc) {
    await life.deleteDocument(doc.id);
    setOpen(null);
    await reload(true);
  }

  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Letters and bills">
      <header className="widget__head"><FileText aria-hidden="true" /><span>Letters and bills</span>
        <button type="button" className="button button--small" style={{ marginLeft: "auto" }} disabled={busy} onClick={() => picker.current?.click()}>
          <Upload size={14} aria-hidden="true" /> {busy ? "Reading…" : "Add"}
        </button>
        <input ref={picker} type="file" hidden accept="application/pdf,image/*,text/plain" capture="environment" aria-label="Choose a letter or bill"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) add(f); }} />
      </header>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>A photo or PDF of a letter, bill or form. It's read on your own server, filed in Siris, and you're reminded before anything's due.</p>
      {note && <p className={`tone-${note.tone}`} role={note.tone === "critical" ? "alert" : "status"} style={{ margin: 0 }}>{note.text}</p>}
      <input className="field" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a letter" aria-label="Find a letter" />
      {data && data.length === 0 ? (
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>{q ? "Nothing matches." : "None yet."}</p>
      ) : (
        <ul className="items">
          {(data ?? []).map((d) => (
            <li key={d.id}>
              <button type="button" className="item item--button" onClick={async () => setOpen(open?.id === d.id ? null : await life.document(d.id))}>
                <span className="item__text">
                  <div className="item__title">{d.title}</div>
                  <div className="item__subtitle">
                    {[d.sender, day(d.added_at), d.due[0] ? `due ${day(d.due[0].date)}${d.due[0].amount ? ` ${money(d.due[0].amount)}` : ""}` : ""].filter(Boolean).join(" · ")}
                  </div>
                </span>
              </button>
              {open?.id === d.id && (
                <div style={{ padding: "4px 12px 12px" }}>
                  <p style={{ margin: "0 0 8px" }}>{open.summary}</p>
                  {open.note_title && <p className="muted" style={{ margin: "0 0 8px", fontSize: 13 }}>In Siris as "{open.note_title}".</p>}
                  <button type="button" className="button button--small" onClick={() => remove(open)}><Trash2 size={14} aria-hidden="true" /> Remove</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Glass>
  );
}

const BILL_KIND: Record<Bill["kind"], string> = { renewal: "Renews", trial_ending: "Trial ending", price_rise: "Price rise", bill_due: "Bill due" };

/** Renewals, trials ending, price rises and bills due, found in email (7.3). */
export function BillsCard() {
  const { data, reload } = useResource("life:bills", () => life.bills(), { staleMs: 60_000 });
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function scan() {
    setBusy(true);
    try {
      const r = await life.scanBills();
      setNote(r.skipped ? `Not checked: ${r.skipped}.` : `Looked at ${r.looked_at} emails, ${r.added} new.`);
      await reload(true);
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function mark(bill: Bill, status: "done" | "ignored") {
    await life.setBill(bill.id, status);
    await reload(true);
  }

  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Bills and subscriptions">
      <header className="widget__head"><Receipt aria-hidden="true" /><span>Bills and subscriptions</span>
        <button type="button" className="button button--small" style={{ marginLeft: "auto" }} disabled={busy} onClick={scan}>{busy ? "Checking…" : "Check email"}</button>
      </header>
      {note && <p className="muted" role="status" style={{ margin: 0, fontSize: 14 }}>{note}</p>}
      {data && data.length === 0 ? (
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>Nothing renewing or due in your email.</p>
      ) : (
        <ul className="items">
          {(data ?? []).map((b) => (
            <li key={b.id} className="item">
              <span className="item__text">
                <div className="item__title">{b.label}</div>
                <div className="item__subtitle">{BILL_KIND[b.kind]} · {b.subject}</div>
              </span>
              <span className="row" style={{ gap: 6 }}>
                <button type="button" className="button button--small" onClick={() => mark(b, "done")}>Done</button>
                <button type="button" className="button button--small" onClick={() => mark(b, "ignored")}>Ignore</button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Glass>
  );
}

function TripRow({ trip, onAway }: { trip: Trip; onAway: (on: boolean) => Promise<void> }) {
  const highs = trip.weather.map((w) => w.high_c).filter((v): v is number => v != null);
  const lows = trip.weather.map((w) => w.low_c).filter((v): v is number => v != null);
  return (
    <li className="item" style={{ display: "block" }}>
      <div className="item__title">{trip.destination} · {day(trip.start)}{trip.nights ? `, ${trip.nights} night${trip.nights === 1 ? "" : "s"}` : ""}</div>
      {highs.length > 0 && <div className="item__subtitle">{Math.round(Math.min(...lows))}–{Math.round(Math.max(...highs))}°C there</div>}
      <p style={{ margin: "6px 0", fontSize: 14 }}><strong>Pack:</strong> {trip.packing.join(", ")}</p>
      <p className="muted" style={{ margin: "0 0 8px", fontSize: 14 }}><strong>House:</strong> {trip.house.join("; ")}</p>
      <label className="row" style={{ gap: 8, fontSize: 14 }}>
        <input type="checkbox" checked={trip.away_mode} onChange={(e) => onAway(e.target.checked)} />
        Away while I'm gone (doors stay locked when you're back)
      </label>
    </li>
  );
}

/** Trips in the calendar, with the weather there and what to pack (7.3). */
export function TravelCard() {
  const { data, reload } = useResource("life:travel", () => life.travel(), { staleMs: 10 * 60_000 });
  async function away(on: boolean) {
    await life.away(on);
    await reload(true);
  }
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Trips">
      <header className="widget__head"><Plane aria-hidden="true" /><span>Trips</span></header>
      {data && data.length === 0 ? (
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>No trips in the calendar for the next three weeks.</p>
      ) : (
        <ul className="items">{(data ?? []).map((t) => <TripRow key={t.key} trip={t} onAway={away} />)}</ul>
      )}
    </Glass>
  );
}

export function LifeScreen() {
  useEffect(() => {
    document.title = "Life admin · SirisOS";
  }, []);
  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">From SirisAI</p>
          <h1 className="page-head__title">Life admin</h1>
        </div>
      </header>
      <div className="stack" style={{ marginTop: 16 }}>
        <DocumentsCard />
        <BillsCard />
        <TravelCard />
      </div>
    </>
  );
}
