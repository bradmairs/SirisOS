import { useEffect, useState } from "react";
import { CloudOff, RefreshCw, Check, Plane } from "lucide-react";
import { useOnline } from "../api/online";
import { describe, drop, failed, flush, onQueued, onSynced, onWaiting, pending, retry, waiting, type Failed, type Pending } from "../api/outbox";
import { flightSoon, inPrepFrame, lastReady, prepare, type Ready } from "../api/prepare";
import { shownSince } from "../api/resource";
import { Sheet } from "./Sheet";

/** 11.4: the sync bar. Offline it says so, with how old what's on screen is and what's waiting; back online it says
 * what synced; it opens the Offline sheet (what's waiting, what didn't go, and Get ready for offline). */

const time = (ms: number) => new Date(ms).toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });

export function openOffline() {
  window.dispatchEvent(new CustomEvent("sirisos:offline"));
}

export function SyncBar() {
  const online = useOnline();
  const [count, setCount] = useState(() => waiting());
  const [failedCount, setFailedCount] = useState(() => failed().length);
  const [flash, setFlash] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [prep, setPrep] = useState<{ done: number; total: number } | null>(null);

  useEffect(() => {
    const offWaiting = onWaiting((n) => { setCount(n); setFailedCount(failed().length); });
    const offSynced = onSynced((n) => { setFlash(`Synced ${n} change${n === 1 ? "" : "s"}`); setFailedCount(failed().length); });
    const offQueued = onQueued(() => setFlash("Saved on this phone · syncs when you're back"));
    const onOpen = () => setOpen(true);
    window.addEventListener("sirisos:offline", onOpen);
    return () => { offWaiting(); offSynced(); offQueued(); window.removeEventListener("sirisos:offline", onOpen); };
  }, []);
  useEffect(() => {
    if (!flash) return;
    const t = window.setTimeout(() => setFlash(null), 3500);
    return () => window.clearTimeout(t);
  }, [flash]);
  // The evening before a flight: get ready by itself.
  useEffect(() => {
    if (!online || inPrepFrame()) return;
    let stop = false;
    const t = window.setTimeout(() => {
      flightSoon().then((soon) => {
        if (soon && !stop) {
          setPrep({ done: 0, total: 1 });
          prepare((done, total) => setPrep({ done, total })).finally(() => { setPrep(null); setFlash("Ready for your flight: SirisOS works offline"); });
        }
      }).catch(() => undefined);
    }, 8000);
    return () => { stop = true; window.clearTimeout(t); };
  }, [online]);

  if (inPrepFrame()) return null;
  const since = shownSince();
  let text: string | null = null;
  let tone = "";
  if (prep) text = `Getting ready for offline… ${Math.round((prep.done / Math.max(1, prep.total)) * 100)}%`;
  else if (!online) {
    text = `Offline${since ? ` · showing what it had at ${time(since)}` : ""}${count ? ` · ${count} waiting` : ""}`;
    tone = " syncbar--offline";
  } else if (flash) text = flash;
  else if (count) text = `Syncing ${count} change${count === 1 ? "" : "s"}…`;
  else if (failedCount) { text = `${failedCount} change${failedCount === 1 ? "" : "s"} didn't sync · Review`; tone = " syncbar--warn"; }

  return (
    <>
      {text && (
        <button type="button" className={`syncbar${tone}`} onClick={() => setOpen(true)} aria-live="polite">
          {!online ? <CloudOff size={14} aria-hidden="true" /> : prep || count ? <RefreshCw size={14} aria-hidden="true" className="spin" /> : <Check size={14} aria-hidden="true" />}
          <span>{text}</span>
        </button>
      )}
      {open && <OfflineSheet online={online} onClose={() => setOpen(false)} preparing={!!prep} onPrepare={() => {
        setPrep({ done: 0, total: 1 });
        prepare((done, total) => setPrep({ done, total })).then((r) => setFlash(`Ready offline: ${r.screens} screens, ${r.notes} notes`)).finally(() => setPrep(null));
      }} />}
    </>
  );
}

function OfflineSheet({ online, onClose, onPrepare, preparing }: { online: boolean; onClose: () => void; onPrepare: () => void; preparing: boolean }) {
  const [items, setItems] = useState<Pending[]>(() => pending());
  const [bad, setBad] = useState<Failed[]>(() => failed());
  const [ready, setReady] = useState<Ready | null>(() => lastReady());
  useEffect(() => onWaiting(() => { setItems(pending()); setBad(failed()); setReady(lastReady()); }), []);
  return (
    <Sheet label="Offline" onClose={onClose}>
      <h2 className="sheet__title">Offline</h2>
      <section className="stack" style={{ gap: 8 }}>
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>
          {ready ? `Ready since ${time(ready.at)}: ${ready.screens} screens and ${ready.notes} Siris notes kept on this phone.` : "Not got ready yet. Do it before a flight, on Wi-Fi, with SirisOS open."}
          {" "}It also gets ready by itself the evening before a flight in Trips or your calendar.
        </p>
        <button type="button" className="button button--small button--primary" style={{ alignSelf: "flex-start" }} disabled={!online || preparing} onClick={onPrepare}>
          <Plane size={14} aria-hidden="true" /> {preparing ? "Getting ready…" : "Get ready for offline"}
        </button>
      </section>
      <section aria-label="Waiting to sync" style={{ marginTop: 16 }}>
        <h3 className="section-title">Waiting to sync ({items.length})</h3>
        {items.length === 0 ? <p className="muted" style={{ margin: 0, fontSize: 14 }}>Nothing waiting.</p> : (
          <ul className="items">
            {items.map((p) => (
              <li key={p.at} className="item"><span className="item__text"><span className="item__title">{describe(p)}</span>
                <span className="item__subtitle">{time(Date.parse(p.at))}</span></span>
                <button type="button" className="button button--small" onClick={() => drop(p.at)} aria-label={`Let go: ${describe(p)}`}>Let go</button></li>
            ))}
          </ul>
        )}
        {items.length > 0 && online && <button type="button" className="button button--small" onClick={() => void flush()}>Sync now</button>}
      </section>
      {bad.length > 0 && (
        <section aria-label="Didn't sync" style={{ marginTop: 16 }}>
          <h3 className="section-title">Didn't sync ({bad.length})</h3>
          <ul className="items">
            {bad.map((p) => (
              <li key={p.at} className="item"><span className="item__text"><span className="item__title">{describe(p)}</span>
                <span className="item__subtitle">{p.why}</span></span>
                <button type="button" className="button button--small" onClick={() => retry(p.at)}>Retry</button>
                <button type="button" className="button button--small" onClick={() => drop(p.at)} aria-label={`Let go: ${describe(p)}`}>Let go</button></li>
            ))}
          </ul>
        </section>
      )}
      <p className="muted" style={{ marginTop: 16, fontSize: 12 }}>
        Offline you can read every screen as it was last loaded and your kept Siris notes, and make everyday changes (tasks, habits, the journal,
        meals, budget sorting, the wrap-up, timesheet, SirisGym, notes): they sync in order when you're back. Home controls, cameras, the Terminal
        and SirisAI's answers need a connection; a question asked offline is sent when you're back and the answer comes as a notification.
      </p>
    </Sheet>
  );
}
