import { useState } from "react";
import { House, Smartphone, X } from "lucide-react";
import { api } from "../api/client";
import { presence } from "../api/hub";
import { netwatch } from "../api/netwatch";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

/** Phones that count as someone home (7.2): the away protocol is only offered once all of them have left
 *  the Wi-Fi, so it waits for Dom's iPhone too. Names are UniFi's, matched ignoring case and punctuation. */
export function PresencePhonesCard() {
  const res = useResource("presence", () => presence.get(), { staleMs: 60_000, refreshMs: 120_000 });
  const away = useResource<Away>("presence:away", () => api<Away>("/api/v1/presence/away"), { staleMs: 60_000 });
  const net = useResource("netwatch", () => netwatch.get(), { staleMs: 60_000 });
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const phones = res.data?.phones ?? [];
  const added = phones.filter((p) => p.source === "added").map((p) => p.name);
  const save = async (next: string[]) => {
    setError(null);
    try { await presence.setAdded(next); res.reload?.(true); } catch (e) { setError(e instanceof Error ? e.message : "Couldn't save it."); }
  };
  const have = new Set(phones.map((p) => p.name.toLowerCase().replace(/[^a-z0-9]/g, "")));
  const suggestions = (net.data?.devices ?? []).filter((d) => d.kind === "client" && /phone|pixel|galaxy/i.test(`${d.name} ${d.type ?? ""}`)
    && !have.has(d.name.toLowerCase().replace(/[^a-z0-9]/g, ""))).slice(0, 6);
  if (!res.data && !res.error) return null;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Phones that count as home">
      <header className="widget__head"><House aria-hidden="true" /><span>Who counts as home</span>
        {res.data?.home != null && <span className="widget__source">{res.data.home ? "Someone's home" : "Everyone's out"}</span>}</header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Everyone's out once every one of these phones has been off the Wi-Fi for {away.data ? `${away.data.away_after_minutes} minutes` : "a while"} in a row (a phone asleep off the Wi-Fi for a minute doesn't count).</p>
      <AwayMode res={away} />
      {res.error && <p className="tone-warning" style={{ margin: 0, fontSize: 13 }}>Couldn't reach SirisAI: {res.error}</p>}
      <ul className="items">
        {phones.map((p) => (
          <li key={p.name} className="item">
            <Smartphone size={15} className={p.home ? "tone-good" : "muted"} aria-hidden="true" />
            <span className="item__text"><span className="item__title">{p.name}</span>
              <span className="item__subtitle">{p.home == null ? "Not checked yet" : p.home ? "Home" : "Away"}{p.source === "settings" ? " · from SirisAI's settings" : ""}</span></span>
            {p.source === "added" && <button type="button" className="icon-link" aria-label={`Stop counting ${p.name}`} onClick={() => save(added.filter((n) => n !== p.name))}><X size={14} aria-hidden="true" /></button>}
          </li>
        ))}
      </ul>
      {suggestions.length > 0 && (
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }} aria-label="Phones on the network">
          {suggestions.map((d) => <button key={d.id} type="button" className="chip chip--button" onClick={() => save([...added, d.name])}>+ {d.name}</button>)}
        </div>
      )}
      <form className="row" style={{ gap: 8 }} onSubmit={(e) => { e.preventDefault(); if (name.trim()) { void save([...added, name.trim()]); setName(""); } }}>
        <input className="field" style={{ flex: 1 }} placeholder="A phone's name in UniFi" aria-label="Phone name" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit" className="button" disabled={!name.trim()}>Add</button>
      </form>
      {error && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 13 }}>{error}</p>}
    </Glass>
  );
}


/** 8.5 (SirisAI 5.63): what SirisAI does when everyone's out. "Nothing" when Apple Home's own automation already does it. */
interface Away { mode: "off" | "ask" | "auto"; protocol: string; away_after_minutes: number }
const MODES: { id: Away["mode"]; label: string; hint: string }[] = [
  { id: "off", label: "Nothing", hint: "Apple Home (or nothing) handles it. SirisAI still knows who's home." },
  { id: "ask", label: "Ask me", hint: "SirisAI suggests the away protocol, and runs it if you say so." },
  { id: "auto", label: "Run it", hint: "SirisAI runs the away protocol by itself, and undoes it when someone's back." },
];

function AwayMode({ res }: { res: { data?: Away; error?: string | null; mutate?: (v: Away) => void } }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!res.data) return null;
  const mode = res.data.mode;
  const pick = async (m: Away["mode"]) => {
    if (m === mode) return;
    setBusy(true); setError(null);
    try { res.mutate?.(await api<Away>("/api/v1/presence/away", { method: "PUT", body: JSON.stringify({ mode: m }) })); }
    catch (e) { setError(e instanceof Error ? e.message : "Couldn't change it."); }
    finally { setBusy(false); }
  };
  return (
    <div className="stack" style={{ gap: 6 }}>
      <span style={{ fontSize: 14, fontWeight: 600 }}>When everyone's out, SirisAI does</span>
      <div className="row gym-chips" role="radiogroup" aria-label="When everyone's out">
        {MODES.map((m) => (
          <button key={m.id} type="button" role="radio" aria-checked={mode === m.id} disabled={busy}
            className={`chip chip--button ${mode === m.id ? "chip--active" : ""}`} onClick={() => pick(m.id)}>{m.label}</button>
        ))}
      </div>
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>{MODES.find((m) => m.id === mode)?.hint}</p>
      {error && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 13 }}>{error}</p>}
    </div>
  );
}
