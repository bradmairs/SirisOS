import { useState } from "react";
import { Mic, Dumbbell, Plus, Settings2, Trash2 } from "lucide-react";
import { gym, newId, type Gym, type GymProfile, type GymSettings } from "../api/gym";
import { Glass } from "../components/Glass";
import { BackupsCard } from "./GymCards";

/** SirisGym's Settings tab (split out of Gym.tsx in 8.9). */

export const list = (v: string) => v.split(/[ ,]+/).map(Number).filter((n) => Number.isFinite(n) && n > 0);

/** SirisGym's settings (6.7): rest, the weight step, warm-ups, and each gym with its bar, plates, dumbbells and machines. */
export function SettingsView({ g, onChange }: { g: Gym; onChange: () => void }) {
  const [s, setS] = useState<GymSettings>(g.settings);
  const [saved, setSaved] = useState(false);
  const setGym = (id: string, patch: Partial<GymProfile>) => setS({ ...s, gyms: s.gyms.map((x) => (x.id === id ? { ...x, ...patch } : x)) });
  const save = async () => { setSaved(false); setS(await gym.settings(s)); setSaved(true); onChange(); };
  return (
    <>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Training settings">
        <header className="widget__head"><Settings2 aria-hidden="true" /><span>Training</span></header>
        <label className="gym-setting">Rest between sets (s)<input className="field" type="number" min={0} max={900} value={s.rest_s} onChange={(e) => setS({ ...s, rest_s: Number(e.target.value) || 0 })} /></label>
        <label className="gym-setting">Rest between exercises (s)<input className="field" type="number" min={0} max={900} value={s.rest_between_s ?? 120} onChange={(e) => setS({ ...s, rest_between_s: Number(e.target.value) || 0 })} /></label>
        <label className="gym-setting">Weight step (kg)<input className="field" type="number" step={0.25} min={0.25} max={20} value={s.increment} onChange={(e) => setS({ ...s, increment: Number(e.target.value) || 2.5 })} /></label>
        <label className="gym-setting">iPhone Shortcut to run when a workout starts
          <input className="field" placeholder="e.g. SirisGym Start (empty: none)" value={s.shortcut_start ?? ""} onChange={(e) => setS({ ...s, shortcut_start: e.target.value })} /></label>
        <label className="gym-setting">…and when it finishes or is discarded (to stop the Watch workout)
          <input className="field" placeholder="e.g. SirisGym Finish (empty: none)" value={s.shortcut_finish ?? ""} onChange={(e) => setS({ ...s, shortcut_finish: e.target.value })} /></label>
        {!!s.shortcut_start?.trim() && !s.shortcut_finish?.trim() && (
          <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 12 }}>With a start Shortcut but no finish one, the Watch workout keeps running after you finish or discard here. Name a Shortcut that ends it.</p>
        )}
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>Make the Shortcut in the Shortcuts app with this exact name, e.g. one that starts a Traditional Strength Training workout on your Watch, so heart rate and kJ are recorded and matched to the session. The finish one gets "finished" or "discarded" as its input, and should end the Watch workout. It runs on iPhone. In Safari it comes straight back; from the Home Screen app, tap ◀ SirisOS at the top left (a link back would open Safari instead, without your workout).</p>
        <label className="gym-setting">…and for each rest, given its seconds (e.g. to start a Clock timer, which shows on the lock screen and Dynamic Island)
          <input className="field" placeholder="e.g. SirisGym Rest (empty: none)" value={s.shortcut_rest ?? ""} onChange={(e) => setS({ ...s, shortcut_rest: e.target.value })} /></label>
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>A web app can't put up a Live Activity itself; only iPhone apps can. A Clock timer can: make a Shortcut that takes the input as seconds and runs Start Timer. Each rest then opens Shortcuts for a moment; from the Home Screen app, tap ◀ SirisOS at the top left to come back.</p>
        <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={s.learn_rest ?? true} onChange={(e) => setS({ ...s, learn_rest: e.target.checked })} /> Set the rest timer from how long my heart rate takes to settle (needs the Watch)</label>
        <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={s.keep_awake ?? true} onChange={(e) => setS({ ...s, keep_awake: e.target.checked })} /> Keep the screen on during a workout</label>
        <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={s.warmups} onChange={(e) => setS({ ...s, warmups: e.target.checked })} /> Add warm-up sets before the first lift for each muscle</label>
        {s.warmups && (
          <label className="gym-setting">Warm-ups (% of the working weight × reps)
            <input className="field" aria-label="Warm-up steps" defaultValue={s.warmup_steps.map((w) => `${Math.round(w.percent * 100)}x${w.reps}`).join(", ")}
              onBlur={(e) => setS({ ...s, warmup_steps: e.target.value.split(/[ ,]+/).map((t) => t.split(/x|×/)).filter((p) => p.length === 2 && Number(p[0]) > 0 && Number(p[1]) > 0)
                .map(([p, r]) => ({ percent: Math.min(1, Number(p) / 100), reps: Number(r) })) })} />
          </label>
        )}
      </Glass>
      {s.gyms.map((x) => (
        <Glass key={x.id} as="section" className="widget" style={{ minHeight: 0 }} aria-label={`Gym: ${x.name}`}>
          <header className="widget__head"><Dumbbell aria-hidden="true" /><span>{x.name}{x.id === s.current_gym ? " · current" : ""}</span>
            {s.gyms.length > 1 && <button type="button" className="widget__source icon-link" aria-label={`Remove ${x.name}`}
              onClick={() => setS({ ...s, gyms: s.gyms.filter((y) => y.id !== x.id), current_gym: s.current_gym === x.id ? s.gyms.find((y) => y.id !== x.id)!.id : s.current_gym })}><Trash2 size={14} aria-hidden="true" /></button>}</header>
          <label className="gym-setting">Name<input className="field" value={x.name} onChange={(e) => setGym(x.id, { name: e.target.value })} /></label>
          <label className="gym-setting">Bar (kg)<input className="field" type="number" step={0.5} value={x.bar} onChange={(e) => setGym(x.id, { bar: Number(e.target.value) || 0 })} /></label>
          <label className="gym-setting">Plates (kg, one of each pair)<input className="field" defaultValue={x.plates.join(", ")} onBlur={(e) => setGym(x.id, { plates: list(e.target.value) })} /></label>
          <label className="gym-setting">Dumbbells on the rack (kg; empty for any)<input className="field" defaultValue={x.dumbbells.join(", ")} placeholder="2.5, 5, 7.5, 10 …" onBlur={(e) => setGym(x.id, { dumbbells: list(e.target.value) })} /></label>
          <label className="gym-setting">Machine stack step (kg)<input className="field" type="number" step={0.5} value={x.stack_step ?? ""} placeholder="any" onChange={(e) => setGym(x.id, { stack_step: Number(e.target.value) || null })} /></label>
          {x.id !== s.current_gym && <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => setS({ ...s, current_gym: x.id })}>Train here now</button>}
        </Glass>
      ))}
      <SiriCard has={!!g.settings.voice_key} onChange={onChange} />
      <TidyCard onChange={onChange} />
      <BackupsCard onChange={onChange} />
      <div className="row" style={{ gap: 8 }}>
        <button type="button" className="button" onClick={() => setS({ ...s, gyms: [...s.gyms, { id: newId(), name: `Gym ${s.gyms.length + 1}`, bar: 20, plates: [25, 20, 15, 10, 5, 2.5, 1.25], dumbbells: [], stack_step: null }] })}>
          <Plus size={14} aria-hidden="true" /> Add a gym</button>
        <button type="button" className="button button--primary" onClick={save}>Save settings</button>
        {saved && <span role="status" className="muted">Saved.</span>}
      </div>
    </>
  );
}

/** Log a set by voice (8.8): a key for an iPhone Shortcut that sends what you said to Siri. Shown once. */
export function SiriCard({ has, onChange }: { has: boolean; onChange: () => void }) {
  const [key, setKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const url = `${window.location.origin}/api/v1/gym-voice/log`;
  const make = async () => {
    if (has && !window.confirm("Make a new key? The Shortcut using the old one stops working until you paste the new one in.")) return;
    setBusy(true); try { setKey((await gym.voiceKey()).key); onChange(); } finally { setBusy(false); }
  };
  const drop = async () => { if (!window.confirm("Turn off logging with Siri?")) return; setBusy(true); try { await gym.dropVoiceKey(); setKey(null); onChange(); } finally { setBusy(false); } };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Log sets with Siri">
      <header className="widget__head"><Mic aria-hidden="true" /><span>Log sets with Siri</span>{has && <span className="widget__source tone-good">On</span>}</header>
      <p style={{ margin: 0, fontSize: 14 }}>Say "Hey Siri, log a set", then "100 by 5" (or "100 kilos for 5 at RPE 8"). The set goes into the exercise you're on, next time SirisGym is open.</p>
      {key ? (
        <>
          <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>Copy this key now: it won't be shown again.</p>
          <code className="gym-key" aria-label="Siri key">{key}</code>
          <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => void navigator.clipboard?.writeText(key)}>Copy the key</button>
        </>
      ) : null}
      <details>
        <summary style={{ fontSize: 14 }}>Make the Shortcut</summary>
        <ol style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 13 }}>
          <li>In Shortcuts, make a new one called <strong>Log a set</strong>.</li>
          <li>Add <strong>Dictate Text</strong>.</li>
          <li>Add <strong>Get Contents of URL</strong>: URL <code>{url}</code>, Method POST, Header <code>X-SirisGym-Key</code> = your key, Request Body JSON with a text field <code>text</code> set to Dictated Text.</li>
          <li>Add <strong>Get Dictionary Value</strong> for <code>say</code>, then <strong>Speak Text</strong>.</li>
        </ol>
      </details>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" className={`button ${has ? "" : "button--primary"}`} disabled={busy} onClick={make}>{has ? "Make a new key" : "Make a key"}</button>
        {has && <button type="button" className="chip chip--button" disabled={busy} onClick={drop}>Turn off</button>}
      </div>
    </Glass>
  );
}

/** Exercises with nothing logged (6.95): see which, then take them out. Workouts are kept, and a copy is saved first. */
export function TidyCard({ onChange }: { onChange: () => void }) {
  const [found, setFound] = useState<{ names: string[]; entries_removed: number } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const look = async () => { setMsg(null); setFound(await gym.cleanup(true)); };
  const go = async () => {
    const r = await gym.cleanup(false);
    setFound(null);
    setMsg(`Took out ${r.exercises_removed} exercise${r.exercises_removed === 1 ? "" : "s"} and ${r.entries_removed} empty entr${r.entries_removed === 1 ? "y" : "ies"}; all ${r.sessions_kept} workouts kept.`);
    onChange();
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Tidy up">
      <header className="widget__head"><Trash2 aria-hidden="true" /><span>Exercises with nothing logged</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Your own exercises with no sets anywhere and not in a routine, and empty entries in workouts. Workouts themselves are never removed.</p>
      {found ? (
        found.names.length || found.entries_removed ? (
          <>
            <p style={{ margin: 0, fontSize: 14 }}>{found.names.length ? found.names.join(", ") : "No exercises"}{found.entries_removed ? ` and ${found.entries_removed} empty entries` : ""}.</p>
            <button type="button" className="button button--primary" style={{ alignSelf: "flex-start" }} onClick={go}>Take them out</button>
          </>
        ) : <p className="muted" style={{ margin: 0 }}>Nothing to tidy.</p>
      ) : <button type="button" className="button" style={{ alignSelf: "flex-start" }} onClick={look}>Look for them</button>}
      {msg && <p role="status" style={{ margin: 0 }}>{msg}</p>}
    </Glass>
  );
}
