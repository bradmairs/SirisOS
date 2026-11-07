import { useState } from "react";
import { CircleAlert, CircleCheck, Copy, HeartPulse, KeyRound } from "lucide-react";
import { training, type HealthImportStatus } from "../api/training";
import { useResource } from "../api/resource";
import { health, type Health } from "../api/health";
import { Glass } from "../components/Glass";

function copy(text: string) {
  navigator.clipboard?.writeText(text).catch(() => undefined);
}

/** Apple Health, on its own (5.5; moved to Health → Data sync in 7.23): the address and key Health Auto Export sends to, what arrived lately, a setup check and a test. */
export function HealthSyncCard({ health }: { health: boolean }) {
  const res = useResource<HealthImportStatus>("health:import", () => training.importStatus(), { staleMs: 60_000 });
  const [key, setKey] = useState<string | null>(null);
  const s = res.data;
  const url = `${window.location.origin}${s?.path ?? "/api/v1/health/import"}`;
  async function make() {
    if (s?.has_key && !window.confirm("A new key stops the old one: the phone will need the new one. Make a new key?")) return;
    const made = await training.newKey();
    setKey(made.key);
    res.reload(true);
  }
  const last = s?.last_ok;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Apple Health" id="health">
      <header className="widget__head"><HeartPulse aria-hidden="true" /><span>Apple Health, on its own</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>
        {last ? `Last arrived ${new Date(last.at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}${last.days?.length ? ` (${last.days.length} day${last.days.length === 1 ? "" : "s"}, to ${last.days.at(-1)})` : ""}.`
          : health ? "SirisAI has health data, but none has come through here yet." : "No health data yet."}
        {s?.last?.error ? ` The last try failed: ${s.last.error}` : ""}
      </p>
      <TestSync />
      {(s?.attempts?.length ?? 0) > 0 && (
        <details className="training__attempts" open={s!.attempts![0].status >= 400}>
          <summary>What the phone sent lately</summary>
          <ul className="items">
            {s!.attempts!.slice(0, 6).map((a) => (
              <li key={a.at + a.status} className="item">
                <span className={`item__dot ${a.status < 300 ? "dot-good" : "dot-critical"}`} aria-hidden="true" />
                <span className="item__text">
                  <span className="item__title career-wrap">{a.outcome}</span>
                  <span className="item__subtitle">{new Date(a.at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })} · {a.status}{a.bytes ? ` · ${a.bytes > 1e6 ? `${(a.bytes / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(a.bytes / 1000))} KB`}` : ""}</span>
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
      <SetupCheck />
      {s && !s.attempts?.length && s.has_key && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Nothing has reached this address yet. If the app says the export failed, check SirisOS is reachable from your phone at this address (try it in Safari), and that the server is on 5.62 or later.</p>}
      <ol className="training__steps">
        <li>Install <strong>Health Auto Export</strong> on your iPhone and allow it to read Health.</li>
        <li>In it: Automations → New → <strong>REST API</strong>. URL: <code>{url}</code> <button type="button" className="icon-link" aria-label="Copy the address" onClick={() => copy(url)}><Copy size={13} aria-hidden="true" /></button></li>
        <li>Add a header <code>Authorization</code> with <code>Bearer</code> and your key (below). Format: JSON. Time Grouping: Minutes (so readiness can use the HRV taken while you slept, energy follows your day, and heart rate lines up with your gym sets; Hours works too). Date Range: Default (all of yesterday plus today so far; "Previous 7 Days" leaves today out, and "Since Last Sync" sends only part of the day). Sync: hourly. A second automation for Workouts with the same settings, but Time Grouping: Seconds, and heart-rate data on (SirisGym lines each set up with it). Pick steps, active energy, exercise time, heart rate, resting heart rate, HRV, respiratory rate, sleep analysis, mindful minutes, weight, and workouts.</li>
        <li>Turn on <strong>Sync automatically</strong>. Health is locked while the phone is locked, so it sends the next time you unlock it.</li>
      </ol>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Rather use Shortcuts? A daily personal automation of "Find Health Samples" then "Get Contents of URL" (POST, JSON <code>{'{"date": "YYYY-MM-DD", "metrics": {"steps": …, "sleep_hours": …}}'}</code>) to the same address, with the same header, works too.</p>
      {key ? (
        <div className="training__key">
          <code>{key}</code>
          <button type="button" className="button button--small" onClick={() => copy(`Bearer ${key}`)}><Copy size={14} aria-hidden="true" /> Copy "Bearer …"</button>
          <p className="muted" style={{ margin: 0, fontSize: 12 }}>Shown once. SirisOS keeps only a fingerprint of it.</p>
        </div>
      ) : (
        <button type="button" className="button button--small" style={{ alignSelf: "flex-start", justifySelf: "start" }} onClick={make}>
          <KeyRound size={14} aria-hidden="true" /> {s?.has_key ? `Make a new key (now …${s.key_hint})` : "Make a key"}
        </button>
      )}
    </Glass>
  );
}

/** Is Health Auto Export set up the way SirisAI needs (6.4, SirisAI 4.03)? From what the last exports looked like. */
function SetupCheck() {
  const res = useResource<Health>("health", () => health.get(), { staleMs: 60_000, persist: true });
  const setup = res.data?.setup;
  if (!setup?.connected) return null;
  return (
    <div className="training__check" aria-label="Setup check">
      {setup.problems.length === 0 ? (
        <p className="tone-good" style={{ margin: 0, fontSize: 14 }}><CircleCheck size={14} aria-hidden="true" /> Set up right: grouped by hour, whole days, and workouts arriving.</p>
      ) : (
        <ul className="items">
          {setup.problems.map((p) => (
            <li key={p} className="item"><CircleAlert size={16} className="tone-warning" aria-hidden="true" /><span className="item__text"><span className="item__title career-wrap">{p}</span></span></li>
          ))}
        </ul>
      )}
    </div>
  );
}


/** Test the sync (6.93): a sample export for this hour through SirisOS and SirisAI, nothing kept, so a failure is either here or on the phone. */
function TestSync() {
  const [r, setR] = useState<{ ok: boolean; detail: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { setR(await training.testSync()); } catch (e) { setR({ ok: false, detail: e instanceof Error ? e.message : String(e) }); } finally { setBusy(false); }
  };
  return (
    <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
      <button type="button" className="button" disabled={busy} onClick={run}>{busy ? "Testing…" : "Test the sync"}</button>
      {r && <span role="status" className={r.ok ? "tone-good" : "tone-warning"} style={{ fontSize: 13 }}>{r.ok ? "✓ " : "✗ "}{r.detail}</span>}
    </div>
  );
}
