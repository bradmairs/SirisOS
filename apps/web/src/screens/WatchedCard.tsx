import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { api } from "../api/client";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

/** What SirisAI watches (8.4, SirisAI 5.51): GET/PUT /api/v1/assistant/tracking. */
export interface Tracking {
  containers: { name: string; state: string; status: string; tracked: boolean }[] | null;
  untracked: { kind: string; name: string; since: string; why: string }[];
}

export const tracking = {
  get: () => api<Tracking>("/api/v1/assistant/tracking"),
  set: (name: string, tracked: boolean, why = "") =>
    api<Tracking>("/api/v1/assistant/tracking", { method: "PUT", body: JSON.stringify({ kind: "container", name, tracked, why }) }),
};

/** Switch off a container you removed on purpose: SirisAI stops checking it, restarting it, offering updates for it
 * and telling you it's down. Stopped ones come first, those you've switched off last. */
export function WatchedCard() {
  const res = useResource<Tracking>("sirisai:tracking", () => tracking.get(), { staleMs: 60_000 });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const t = res.data;
  if (!t && res.error) return null;  // SirisAI older than 5.51, or not reachable: nothing to switch
  const list = t?.containers ?? [];
  const gone = (t?.untracked ?? []).filter((u) => !list.some((c) => c.name === u.name));  // untracked and no longer in Docker at all
  const shown = all ? list : list.filter((c) => !c.tracked || c.state !== "running");
  async function flip(name: string, tracked: boolean) {
    setBusy(name); setError(null);
    try { res.mutate?.(await tracking.set(name, tracked, tracked ? "" : "switched off in SirisOS")); }
    catch (e) { setError(e instanceof Error ? e.message : "Couldn't change it."); }
    finally { setBusy(null); }
  }
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="What SirisAI watches">
      <header className="widget__head"><Eye aria-hidden="true" /><span>What SirisAI watches</span>
        {list.length > 0 && <button type="button" className="widget__source icon-link" onClick={() => setAll(!all)}>{all ? "Only stopped and off" : `All ${list.length}`}</button>}
      </header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Removed a container on purpose? Switch it off, and SirisAI stops telling you it's down (and won't restart or update it).</p>
      {!t && <div className="skeleton" style={{ height: 60 }} />}
      {t && t.containers === null && <p className="muted" style={{ margin: 0 }}>Docker isn't set up in SirisAI, so there are no containers to list.</p>}
      {t && shown.length === 0 && gone.length === 0 && t.containers !== null && <p className="muted" style={{ margin: 0 }}>Every container is running and watched.</p>}
      <ul className="items">
        {shown.map((c) => (
          <li key={c.name} className="item">
            <span className={`item__dot ${c.state === "running" ? "dot-good" : c.tracked ? "dot-critical" : ""}`} aria-hidden="true" />
            <span className="item__text">
              <span className="item__title">{c.name}</span>
              <span className="item__subtitle">{c.tracked ? c.status || c.state : `Not watched · ${c.status || c.state}`}</span>
            </span>
            <button type="button" role="switch" aria-checked={c.tracked} disabled={busy === c.name} className={`toggle ${c.tracked ? "toggle--on" : ""}`}
              aria-label={`Watch ${c.name}`} title={c.tracked ? "Watched" : "Not watched"} onClick={() => flip(c.name, !c.tracked)}>
              <span className="toggle__knob" aria-hidden="true" />
            </button>
          </li>
        ))}
        {gone.map((u) => (
          <li key={`gone-${u.name}`} className="item">
            <EyeOff size={16} className="muted" aria-hidden="true" />
            <span className="item__text">
              <span className="item__title">{u.name}</span>
              <span className="item__subtitle">Not watched{u.why ? ` · ${u.why}` : ""} · no longer in Docker</span>
            </span>
            <button type="button" className="button button--small" disabled={busy === u.name} onClick={() => flip(u.name, true)}>Watch again</button>
          </li>
        ))}
      </ul>
      {error && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 13 }}>{error}</p>}
    </Glass>
  );
}
