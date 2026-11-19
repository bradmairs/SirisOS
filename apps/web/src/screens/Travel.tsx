import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Luggage, Plane, Plus, Trash2 } from "lucide-react";
import { Glass } from "../components/Glass";
import { useResource } from "../api/resource";
import { travel, type TripView } from "../api/travel";
import { assistant } from "../api/hub";

/**
 * Trips (10.2): the weather there, a packing list, bills while you're away, the out-of-office and away mode, on one
 * card. It shows on Home from a week before.
 */

const DAY = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
const when = (t: TripView) => (t.away ? "away now" : t.days_to_go === 0 ? "today" : t.days_to_go === 1 ? "tomorrow" : `in ${t.days_to_go} days`);

function AwayButton() {
  const res = useResource("assistant:protocols", () => assistant.protocols(), { staleMs: 10 * 60_000 });
  const [note, setNote] = useState<string | null>(null);
  const list = Array.isArray(res.data?.protocols) ? res.data!.protocols : [];
  const away = list.find((p) => /away|out|leav|holiday/i.test(p.name));
  if (!away) return null;
  return (
    <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
      <button type="button" className="button button--small" onClick={async () => {
        setNote(null);
        try {
          const r = await assistant.runProtocol(away.name);
          setNote(r.failed.length ? `Ran ${away.name}, but ${r.failed.length} step${r.failed.length === 1 ? "" : "s"} failed.` : `${away.name} is on.`);
        } catch (e) { setNote(e instanceof Error ? e.message : String(e)); }
      }}>Run “{away.name}”</button>
      {note && <span className="muted" role="status" style={{ fontSize: 13 }}>{note}</span>}
    </div>
  );
}

export function TripCard({ trip, onChange, full = true }: { trip: TripView; onChange: (t: TripView) => void; full?: boolean }) {
  const [item, setItem] = useState("");
  const [error, setError] = useState<string | null>(null);
  const save = async (c: Parameters<typeof travel.change>[1]) => {
    setError(null);
    try { onChange(await travel.change(trip.id, c)); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  const wx = Array.isArray(trip.weather?.days) ? trip.weather.days : [];
  const todo = trip.packing.filter((p) => !p.done);
  return (
    <Glass as="section" className="widget" aria-label={`Trip to ${trip.destination}`}>
      <header className="widget__head"><Plane aria-hidden="true" /><span>{trip.destination}</span>
        <span className="widget__source">{when(trip)} · {trip.nights} night{trip.nights === 1 ? "" : "s"}</span>
      </header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>{DAY(trip.start)} to {DAY(trip.end)}{trip.place && trip.place !== trip.destination ? ` · ${trip.place}` : ""}</p>
      {wx.length > 0 ? (
        <div className="trip-weather" aria-label="Weather there">
          {wx.slice(0, full ? 10 : 4).map((d) => (
            <div key={d.date} className="trip-weather__day">
              <span className="muted">{new Date(`${d.date}T00:00:00`).toLocaleDateString(undefined, { weekday: "short" })}</span>
              <strong>{d.high_c != null ? `${Math.round(d.high_c)}°` : "–"}</strong>
              <span className="muted">{d.low_c != null ? `${Math.round(d.low_c)}°` : ""}</span>
              <span style={{ fontSize: 11 }}>{d.conditions}{d.rain_chance != null && d.rain_chance >= 40 ? ` ${d.rain_chance}%` : ""}</span>
            </div>
          ))}
        </div>
      ) : trip.weather?.note && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{trip.weather.note}</p>}

      <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
        <span><Luggage size={14} aria-hidden="true" /> Packed {trip.packed} of {trip.to_pack}</span>
        {!full && <Link to="/travel" className="brief-link" style={{ fontSize: 13 }}>Trip</Link>}
      </div>
      {full && (
        <>
          <ul className="stack" style={{ gap: 2, padding: 0, listStyle: "none" }} aria-label="Packing list">
            {[...todo, ...trip.packing.filter((p) => p.done)].map((p) => (
              <li key={p.item} className="row" style={{ gap: 8 }}>
                <label className="row" style={{ gap: 8, flex: 1, minWidth: 0 }}>
                  <input type="checkbox" checked={p.done} onChange={() => void save({ packing: trip.packing.map((x) => (x.item === p.item ? { ...x, done: !x.done } : x)) })} />
                  <span style={p.done ? { textDecoration: "line-through", opacity: 0.6 } : undefined}>{p.item}</span>
                </label>
                <button type="button" className="icon-link" aria-label={`Take ${p.item} off the list`} onClick={() => void save({ packing: trip.packing.filter((x) => x.item !== p.item) })}>
                  <Trash2 size={13} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
          <form className="row" style={{ gap: 6 }} onSubmit={(e) => {
            e.preventDefault();
            if (item.trim()) void save({ packing: [...trip.packing, { item: item.trim(), done: false }] }).then(() => setItem(""));
          }}>
            <input className="field" placeholder="Add to pack" aria-label="Add to pack" value={item} onChange={(e) => setItem(e.target.value)} maxLength={80} style={{ flex: 1, minWidth: 0 }} />
            <button type="submit" className="button button--small"><Plus size={14} aria-hidden="true" /> Add</button>
          </form>
        </>
      )}

      {trip.bills.length > 0 && (
        <div>
          <strong style={{ fontSize: 14 }}>Due while you're away</strong>
          <ul className="stack" style={{ gap: 2, padding: 0, listStyle: "none", fontSize: 14 }}>
            {trip.bills.map((b, i) => (
              <li key={`${b.date}-${i}`} className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{DAY(b.date)} · {b.name}</span>
                {b.amount != null && <span className="budget-tx__amount">${b.amount.toFixed(2)}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {!trip.away && (
        <label className="row" style={{ gap: 8 }}>
          <input type="checkbox" checked={trip.ooo_done} onChange={() => void save({ ooo_done: !trip.ooo_done })} />
          <span>Out-of-office set{!trip.ooo_done && <span className="muted" style={{ fontSize: 12 }}> · a reminder at 3pm {DAY(trip.ooo_day)}</span>}</span>
        </label>
      )}
      {full && (trip.away || trip.days_to_go <= 1) && <AwayButton />}
      {error && <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>{error}</p>}
    </Glass>
  );
}

export function TravelScreen() {
  const res = useResource("travel:list", () => travel.list(), {});
  const [dest, setDest] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { document.title = "Trips · SirisOS"; }, []);
  const data = res.data && Array.isArray(res.data.upcoming) ? res.data : undefined;

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">Going away</p>
          <h1 className="page-head__title">Trips</h1>
        </div>
      </header>
      {data?.next && <TripCard trip={data.next} onChange={() => void res.reload(true)} />}
      <Glass as="section" className="widget" aria-label="Add a trip">
        <header className="widget__head"><Plus aria-hidden="true" /><span>Add a trip</span></header>
        <form className="stack" style={{ gap: 6 }} onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          setBusy(true);
          try {
            await travel.add({ destination: dest.trim(), start, end });
            setDest(""); setStart(""); setEnd("");
            await res.reload(true);
          } catch (err) { setError(err instanceof Error ? err.message : String(err)); } finally { setBusy(false); }
        }}>
          <input className="field" placeholder="Where (e.g. Hobart)" aria-label="Where" value={dest} onChange={(e) => setDest(e.target.value)} maxLength={80} required />
          <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
            <label className="stack muted" style={{ gap: 2, fontSize: 13, flex: "1 1 130px" }}>Leaving<input className="field" type="date" value={start} onChange={(e) => setStart(e.target.value)} required /></label>
            <label className="stack muted" style={{ gap: 2, fontSize: 13, flex: "1 1 130px" }}>Back<input className="field" type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} required /></label>
          </div>
          <button type="submit" className="button button--small" style={{ alignSelf: "flex-start" }} disabled={busy}>{busy ? "Looking it up…" : "Add trip"}</button>
        </form>
        {error && <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>{error}</p>}
      </Glass>
      {data && data.upcoming.length > 1 && (
        <Glass as="section" className="widget" aria-label="Coming up">
          <header className="widget__head"><span>Coming up</span></header>
          <ul className="items">
            {data.upcoming.slice(1).map((t) => (
              <li key={t.id} className="item">
                <span className="item__text"><span className="item__title">{t.destination}</span><span className="item__subtitle">{DAY(t.start)} to {DAY(t.end)}</span></span>
                <button type="button" className="icon-link" aria-label={`Delete the trip to ${t.destination}`} onClick={async () => { await travel.remove(t.id); await res.reload(true); }}>
                  <Trash2 size={14} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        </Glass>
      )}
      {data?.next && (
        <button type="button" className="button button--small button--ghost" style={{ alignSelf: "flex-start" }} onClick={async () => { await travel.remove(data.next!.id); await res.reload(true); }}>
          <Trash2 size={14} aria-hidden="true" /> Delete the trip to {data.next.destination}
        </button>
      )}
    </div>
  );
}

/** Home (10.2): the trip, from a week before until you're back. */
export function TripHomeCard() {
  const res = useResource("travel:current", () => travel.current(), { staleMs: 30 * 60_000, persist: true });
  const trip = res.data?.trip;
  if (!trip || !Array.isArray(trip.packing)) return null;
  return <TripCard trip={trip} full={false} onChange={(t) => res.mutate({ trip: t })} />;
}
