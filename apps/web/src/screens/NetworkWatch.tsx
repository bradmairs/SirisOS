import { useState } from "react";
import { ShieldAlert, Star } from "lucide-react";
import { netwatch, type NetWatch, type WatchedDevice } from "../api/netwatch";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";
import { useShowMore } from "../components/ShowMore";

const ago = (iso: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "");

/** Network alerts (5.3): what's new on the network, what matters, what's blocked. */
export function NetworkWatchCard() {
  const res = useResource<NetWatch>("netwatch", () => netwatch.get(), { refreshMs: 60_000, staleMs: 30_000 });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  async function run(device: string, p: Promise<NetWatch>) {
    setBusy(device);
    try {
      res.mutate(await p);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't do that.");
    } finally {
      setBusy(null);
    }
  }
  const all = res.data?.devices ?? [];
  const fresh = all.filter((d) => !d.trusted && !d.blocked);
  const watched = all.filter((d) => d.trusted && d.important && !d.blocked);
  const blocked = all.filter((d) => d.blocked);
  const rest = all.filter((d) => d.trusted && !d.important && !d.blocked);
  const more = useShowMore(rest, 0);

  const star = (d: WatchedDevice) => (
    <button type="button" className={`icon-link ${d.important ? "tone-warning" : "muted"}`} aria-pressed={d.important} disabled={busy === d.id}
      aria-label={d.important ? `Stop watching ${d.name}` : `Tell me when ${d.name} goes offline`} onClick={() => run(d.id, netwatch.important(d.id, !d.important))}>
      <Star size={16} aria-hidden="true" fill={d.important ? "currentColor" : "none"} />
    </button>
  );

  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Network watch" id="network">
      <header className="widget__head"><ShieldAlert aria-hidden="true" /><span>Network watch</span></header>
      {!res.data && res.error && <p className="muted" style={{ margin: 0, fontSize: 14 }}>{res.error}</p>}
      {res.data && !res.data.watching && <p className="muted" style={{ margin: 0, fontSize: 14 }}>SirisOS starts watching once SirisAI 3.11 or later with UniFi answers, and phone notifications are on. Its first look learns what's already here.</p>}
      {error && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 13 }}>{error}</p>}

      {fresh.length > 0 && (
        <>
          <h3 className="maint__h">New on the network: are these yours?</h3>
          <ul className="items">
            {fresh.map((d) => (
              <li key={d.id} className="item maint__job">
                <span className="item__dot dot-warning" aria-hidden="true" />
                <span className="item__text"><div className="item__title">{d.name}</div><div className="item__subtitle">{d.id} · first seen {ago(d.first_seen)}</div></span>
                <div className="row maint__acts">
                  <button type="button" className="button button--small" disabled={busy === d.id} onClick={() => run(d.id, netwatch.block(d.id, true))}>Block it</button>
                  <button type="button" className="button button--small button--primary" disabled={busy === d.id} onClick={() => run(d.id, netwatch.trust(d.id))}>It's mine</button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {watched.length > 0 && (
        <>
          <h3 className="maint__h">Watched: you'll hear if one drops off for 10 minutes</h3>
          <ul className="items">
            {watched.map((d) => (
              <li key={d.id} className="item">
                <span className={`item__dot ${d.online ? "dot-good" : "dot-critical"}`} aria-hidden="true" />
                <span className="item__text"><div className="item__title">{d.name}</div>
                  <div className="item__subtitle">{d.online ? "Online" : `Offline for ${d.offline_minutes ?? 0} min`}</div></span>
                {star(d)}
              </li>
            ))}
          </ul>
        </>
      )}

      {blocked.length > 0 && (
        <>
          <h3 className="maint__h">Blocked</h3>
          <ul className="items">
            {blocked.map((d) => (
              <li key={d.id} className="item">
                <span className="item__dot" aria-hidden="true" />
                <span className="item__text"><div className="item__title">{d.name}</div><div className="item__subtitle">{d.id}</div></span>
                <button type="button" className="button button--small" disabled={busy === d.id} onClick={() => run(d.id, netwatch.block(d.id, false))}>Unblock</button>
              </li>
            ))}
          </ul>
        </>
      )}

      {rest.length > 0 && (
        <>
          <h3 className="maint__h">Everything else ({rest.length}): star one to watch it</h3>
          <ul className="items">
            {more.shown.map((d) => (
              <li key={d.id} className="item">
                <span className={`item__dot ${d.online ? "dot-good" : ""}`} aria-hidden="true" />
                <span className="item__text"><div className="item__title">{d.name}</div><div className="item__subtitle">{d.online ? "Online" : "Not on now"}</div></span>
                {star(d)}
              </li>
            ))}
          </ul>
          {more.toggle}
        </>
      )}
    </Glass>
  );
}
