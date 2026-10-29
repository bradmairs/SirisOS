import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Check, FileText, Plus, Refrigerator, Trash2, Wrench } from "lucide-react";
import {
  dueText, EVERY_CHOICES, everyText, maintenance as api,
  type Appliance, type ApplianceFields, type HomeJob, type Maintenance, type NewJob,
} from "../api/maintenance";
import { useResource } from "../api/resource";
import { FLOORS, roomById } from "../house/layout";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";
import { useShowMore } from "../components/ShowMore";

const roomName = (id: string) => roomById(id)?.name ?? id;
const fmt = (iso: string | null) => iso ? new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
const DOT: Record<HomeJob["state"], string> = { overdue: "dot-critical", due: "dot-warning", soon: "dot-warning", ok: "dot-good", unset: "" };

/** Home maintenance (5.2), shared by the house page and Home. */
export function useMaintenance() {
  const res = useResource<Maintenance>("maintenance", () => api.get(), { staleMs: 60_000, persist: true });
  const [error, setError] = useState<string | null>(null);
  async function run(p: Promise<Maintenance>) {
    try {
      res.mutate(await p);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save.");
    }
  }
  return { data: res.data ?? null, loadError: res.data ? null : res.error, error, run };
}

function RoomSelect({ value, onChange, label }: { value: string; onChange: (room: string) => void; label: string }) {
  return (
    <select className="field" value={value} aria-label={label} onChange={(e) => onChange(e.target.value)}>
      {FLOORS.map((f) => (
        <optgroup key={f.id} label={`${f.name} floor`}>
          {f.rooms.filter((r) => !r.id.startsWith("stairs")).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

function JobRow({ job, run, onEdit, showRoom = true }: { job: HomeJob; run: (p: Promise<Maintenance>) => void; onEdit: () => void; showRoom?: boolean }) {
  const [when, setWhen] = useState("");
  return (
    <li className="item maint__job">
      <span className={`item__dot ${DOT[job.state]}`} aria-hidden="true" />
      <button type="button" className="item__text house__pick" onClick={onEdit}>
        <div className="item__title career-wrap">{job.title}</div>
        <div className="item__subtitle career-wrap">{[showRoom && roomName(job.room), everyText(job.every_days), dueText(job)].filter(Boolean).join(" · ")}</div>
      </button>
      {job.state === "unset" ? (
        <form className="row maint__when" onSubmit={(e) => { e.preventDefault(); if (when) run(api.changeJob(job.id, { last_done: when })); }}>
          <input className="field" type="date" value={when} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setWhen(e.target.value)} aria-label={`When you last did: ${job.title}`} />
          <button type="submit" className="button button--small" disabled={!when}>Save</button>
        </form>
      ) : (
        <div className="row maint__acts">
          {(job.state === "overdue" || job.state === "due") && <button type="button" className="button button--small" onClick={() => run(api.snooze(job.id))}>Next week</button>}
          <button type="button" className="button button--small button--primary" aria-label={`Done: ${job.title}`} onClick={() => run(api.done(job.id))}><Check size={14} aria-hidden="true" /> Done</button>
        </div>
      )}
    </li>
  );
}

/** On Home (5.2): the jobs due today or overdue. Hidden when there are none. */
export function HomeJobsWidget() {
  const { data, run } = useMaintenance();
  const needs = (data?.jobs ?? []).filter((j) => j.state === "overdue" || j.state === "due");
  if (!needs.length) return null;
  return (
    <Glass as="section" className="widget" aria-label="Around the house">
      <header className="widget__head"><Wrench aria-hidden="true" /><span>Around the house</span>
        <Link to="/house?view=maintenance" className="widget__source">All jobs</Link></header>
      <ul className="items">{needs.slice(0, 4).map((j) => <JobRow key={j.id} job={j} run={run} onEdit={() => undefined} />)}</ul>
      {needs.length > 4 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>And {needs.length - 4} more.</p>}
    </Glass>
  );
}

/** The house page's maintenance card: every job, due first. */
export function MaintenanceCard() {
  const { data, loadError, error, run } = useMaintenance();
  const [editing, setEditing] = useState<HomeJob | "new" | null>(null);
  const jobs = data?.jobs ?? [];
  const started = jobs.filter((j) => j.state !== "unset");
  const unset = jobs.filter((j) => j.state === "unset");
  const listed = useShowMore(started, 8);
  const later = useShowMore(unset, 3);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Maintenance" id="maintenance">
      <header className="widget__head"><Wrench aria-hidden="true" /><span>Maintenance</span>
        <button type="button" className="widget__source icon-link" onClick={() => setEditing("new")}><Plus size={14} aria-hidden="true" /> Add a job</button></header>
      {loadError && <p className="muted" style={{ margin: 0 }}>{loadError}</p>}
      {error && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 13 }}>{error}</p>}
      {data && (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          {data.summary.overdue + data.summary.due ? `${data.summary.overdue + data.summary.due} need doing; their rooms glow in the house.` : "Nothing due."}
          {data.summary.soon ? ` ${data.summary.soon} coming up this week.` : ""}
        </p>
      )}
      {started.length > 0 && <ul className="items">{listed.shown.map((j) => <JobRow key={j.id} job={j} run={run} onEdit={() => setEditing(j)} />)}</ul>}
      {listed.toggle}
      {unset.length > 0 && (
        <>
          <h3 className="maint__h">Not started: when did you last do these?</h3>
          <ul className="items">{later.shown.map((j) => <JobRow key={j.id} job={j} run={run} onEdit={() => setEditing(j)} />)}</ul>
          {later.toggle}
        </>
      )}
      {editing && data && (
        <JobSheet job={editing === "new" ? null : editing} appliances={data.appliances} onClose={() => setEditing(null)}
          onSave={(fields) => { run(editing === "new" ? api.addJob(fields) : api.changeJob(editing.id, fields)); setEditing(null); }}
          onDelete={editing === "new" ? undefined : () => { run(api.removeJob(editing.id)); setEditing(null); }} />
      )}
    </Glass>
  );
}

function JobSheet({ job, appliances, onClose, onSave, onDelete }: {
  job: HomeJob | null; appliances: Appliance[]; onClose: () => void; onSave: (j: NewJob) => void; onDelete?: () => void;
}) {
  const [f, setF] = useState<NewJob>({ title: job?.title ?? "", room: job?.room ?? "office", every_days: job?.every_days ?? 90,
    last_done: job?.last_done ?? null, appliance: job?.appliance ?? null, notes: job?.notes ?? "" });
  const custom = !EVERY_CHOICES.some(([d]) => d === f.every_days);
  function submit(e: FormEvent) {
    e.preventDefault();
    if (f.title.trim()) onSave({ ...f, title: f.title.trim() });
  }
  return (
    <Sheet label={job ? "Edit job" : "Add a job"} onClose={onClose}>
      <form className="stack maint__form" onSubmit={submit}>
        <h2 className="app-sheet__name">{job ? "Edit job" : "Add a job"}</h2>
        <input className="field" value={f.title} placeholder="e.g. Clean the AC filters" aria-label="Job" onChange={(e) => setF({ ...f, title: e.target.value })} />
        <RoomSelect value={f.room} label="Room" onChange={(room) => setF({ ...f, room })} />
        <select className="field" aria-label="How often" value={custom ? "custom" : f.every_days} onChange={(e) => e.target.value !== "custom" && setF({ ...f, every_days: Number(e.target.value) })}>
          {EVERY_CHOICES.map(([d, label]) => <option key={d} value={d}>{label}</option>)}
          {custom && <option value="custom">{everyText(f.every_days)}</option>}
        </select>
        <label className="career-app__field"><span className="career-app__label">Last done</span>
          <input className="field" type="date" value={f.last_done ?? ""} onChange={(e) => setF({ ...f, last_done: e.target.value || null })} /></label>
        {appliances.length > 0 && (
          <select className="field" aria-label="Appliance" value={f.appliance ?? ""} onChange={(e) => setF({ ...f, appliance: e.target.value || null })}>
            <option value="">No appliance</option>
            {appliances.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        )}
        <textarea className="field" rows={2} value={f.notes} placeholder="Notes (filter size, where the tap is…)" aria-label="Notes" onChange={(e) => setF({ ...f, notes: e.target.value })} />
        <div className="row" style={{ gap: 8 }}>
          <button type="submit" className="button button--primary" disabled={!f.title.trim()}>Save</button>
          <button type="button" className="button" onClick={onClose}>Cancel</button>
          {onDelete && <button type="button" className="icon-link" style={{ marginLeft: "auto" }} aria-label="Delete the job" onClick={onDelete}><Trash2 size={16} aria-hidden="true" /></button>}
        </div>
      </form>
    </Sheet>
  );
}

/** Appliances: make, model, when bought, warranty and the manual. */
export function AppliancesCard() {
  const { data, run } = useMaintenance();
  const [editing, setEditing] = useState<Appliance | "new" | null>(null);
  const items = data?.appliances ?? [];
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Appliances">
      <header className="widget__head"><Refrigerator aria-hidden="true" /><span>Appliances</span>
        <button type="button" className="widget__source icon-link" onClick={() => setEditing("new")}><Plus size={14} aria-hidden="true" /> Add one</button></header>
      {!items.length && <p className="muted" style={{ margin: 0, fontSize: 14 }}>Add the AC units, the dishwasher, the BBQ… with their manual and warranty, so they're here when something breaks.</p>}
      <ul className="items">
        {items.map((a) => (
          <li key={a.id} className="item">
            <span className={`item__dot ${a.warranty_days != null && a.warranty_days >= 0 && a.warranty_days <= 30 ? "dot-warning" : ""}`} aria-hidden="true" />
            <button type="button" className="item__text house__pick" onClick={() => setEditing(a)}>
              <div className="item__title">{a.name}</div>
              <div className="item__subtitle career-wrap">{[roomName(a.room), [a.make, a.model].filter(Boolean).join(" "), warrantyText(a)].filter(Boolean).join(" · ")}</div>
            </button>
            {(a.manual || a.manual_url) && (
              <button type="button" className="icon-link" aria-label={`Manual for ${a.name}`}
                onClick={() => (a.manual ? api.openManual(a.id).catch(() => undefined) : window.open(a.manual_url, "_blank", "noopener"))}>
                <FileText size={16} aria-hidden="true" />
              </button>
            )}
          </li>
        ))}
      </ul>
      {editing && (
        <ApplianceSheet appliance={editing === "new" ? null : editing} onClose={() => setEditing(null)} run={run}
          onSave={(fields) => { run(editing === "new" ? api.addAppliance(fields) : api.changeAppliance(editing.id, fields)); setEditing(null); }}
          onDelete={editing === "new" ? undefined : () => { run(api.removeAppliance(editing.id)); setEditing(null); }} />
      )}
    </Glass>
  );
}

function warrantyText(a: Appliance): string {
  if (a.warranty_days == null) return a.bought_on ? `Bought ${fmt(a.bought_on)}` : "";
  if (a.warranty_days < 0) return "Out of warranty";
  return a.warranty_days <= 60 ? `Warranty ends in ${a.warranty_days} days` : `Warranty to ${fmt(a.warranty_until)}`;
}

function ApplianceSheet({ appliance, onClose, onSave, onDelete, run }: {
  appliance: Appliance | null; onClose: () => void; onSave: (a: ApplianceFields) => void; onDelete?: () => void; run: (p: Promise<Maintenance>) => void;
}) {
  const [f, setF] = useState<ApplianceFields>({ name: appliance?.name ?? "", room: appliance?.room ?? "kitchen", make: appliance?.make ?? "", model: appliance?.model ?? "",
    bought_on: appliance?.bought_on ?? null, warranty_until: appliance?.warranty_until ?? null, manual_url: appliance?.manual_url ?? "", notes: appliance?.notes ?? "" });
  const file = useRef<HTMLInputElement>(null);
  return (
    <Sheet label={appliance ? appliance.name : "Add an appliance"} onClose={onClose}>
      <form className="stack maint__form" onSubmit={(e) => { e.preventDefault(); if (f.name.trim()) onSave({ ...f, name: f.name.trim() }); }}>
        <h2 className="app-sheet__name">{appliance ? "Edit appliance" : "Add an appliance"}</h2>
        <input className="field" value={f.name} placeholder="e.g. Office split system" aria-label="Name" onChange={(e) => setF({ ...f, name: e.target.value })} />
        <RoomSelect value={f.room} label="Room" onChange={(room) => setF({ ...f, room })} />
        <div className="row" style={{ gap: 6 }}>
          <input className="field" value={f.make} placeholder="Make" aria-label="Make" onChange={(e) => setF({ ...f, make: e.target.value })} />
          <input className="field" value={f.model} placeholder="Model" aria-label="Model" onChange={(e) => setF({ ...f, model: e.target.value })} />
        </div>
        <div className="row" style={{ gap: 6 }}>
          <label className="career-app__field" style={{ flex: 1 }}><span className="career-app__label">Bought</span>
            <input className="field" type="date" value={f.bought_on ?? ""} onChange={(e) => setF({ ...f, bought_on: e.target.value || null })} /></label>
          <label className="career-app__field" style={{ flex: 1 }}><span className="career-app__label">Warranty until</span>
            <input className="field" type="date" value={f.warranty_until ?? ""} onChange={(e) => setF({ ...f, warranty_until: e.target.value || null })} /></label>
        </div>
        <input className="field" type="url" value={f.manual_url} placeholder="Link to the manual (https://…)" aria-label="Manual link" onChange={(e) => setF({ ...f, manual_url: e.target.value })} />
        {appliance && (
          <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            {appliance.manual && <button type="button" className="button button--small" onClick={() => api.openManual(appliance.id).catch(() => undefined)}><FileText size={14} aria-hidden="true" /> {appliance.manual.filename}</button>}
            <button type="button" className="button button--small" onClick={() => file.current?.click()}>{appliance.manual ? "Replace the manual" : "Upload the manual"}</button>
            <input ref={file} type="file" hidden accept=".pdf,image/*" aria-label="Upload the manual"
              onChange={(e) => { const x = e.target.files?.[0]; if (x) run(api.uploadManual(appliance.id, x)); }} />
          </div>
        )}
        <textarea className="field" rows={2} value={f.notes} placeholder="Notes (serial number, installer…)" aria-label="Notes" onChange={(e) => setF({ ...f, notes: e.target.value })} />
        <div className="row" style={{ gap: 8 }}>
          <button type="submit" className="button button--primary" disabled={!f.name.trim()}>Save</button>
          <button type="button" className="button" onClick={onClose}>Cancel</button>
          {onDelete && <button type="button" className="icon-link" style={{ marginLeft: "auto" }} aria-label="Delete the appliance" onClick={onDelete}><Trash2 size={16} aria-hidden="true" /></button>}
        </div>
      </form>
    </Sheet>
  );
}

/** In the house's room panel: that room's jobs and appliances. */
export function RoomUpkeep({ roomId }: { roomId: string }) {
  const { data, run } = useMaintenance();
  const jobs = (data?.jobs ?? []).filter((j) => j.room === roomId && j.state !== "unset");
  const appliances = (data?.appliances ?? []).filter((a) => a.room === roomId);
  if (!jobs.length && !appliances.length) return null;
  return (
    <div className="maint__room">
      {jobs.length > 0 && <ul className="items">{jobs.map((j) => <JobRow key={j.id} job={j} run={run} onEdit={() => undefined} showRoom={false} />)}</ul>}
      {appliances.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{appliances.map((a) => a.name).join(" · ")}</p>}
    </div>
  );
}
