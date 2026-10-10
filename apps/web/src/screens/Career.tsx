import { useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowUpRight,
  Award,
  Brain as BrainIcon,
  Check,
  Circle,
  CircleDashed,
  CircleDot,
  CircleSlash,
  Compass,
  FileUp,
  Flag,
  ListChecks,
  Plus,
  Route as RouteIcon,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import {
  career as careerApi,
  EA_PORTAL,
  type Career,
  type CareerDocument,
  type CpdCategory,
  type CpdSummary,
  type Evidence,
  type Goal,
  type StepStatus,
} from "../api/career";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";
import { Sheet } from "../components/Sheet";

const VIEWS = [
  { id: "overview", label: "Overview" },
  { id: "cpd", label: "CPD" },
  { id: "pathways", label: "Pathways" },
  { id: "competencies", label: "Competencies" },
  { id: "goals", label: "Goals" },
] as const;
type View = (typeof VIEWS)[number]["id"];

const STATUS: Record<StepStatus, { label: string; Icon: LucideIcon; tone: string }> = {
  todo: { label: "To do", Icon: Circle, tone: "" },
  doing: { label: "In progress", Icon: CircleDot, tone: "tone-warning" },
  done: { label: "Done", Icon: Check, tone: "tone-good" },
  na: { label: "Not needed", Icon: CircleSlash, tone: "muted" },
};
const NEXT_STATUS: Record<StepStatus, StepStatus> = { todo: "doing", doing: "done", done: "na", na: "todo" };
const CATEGORY_LABEL: Record<CpdCategory, string> = { area: "Area of practice", risk: "Risk management", business: "Business & management", other: "Other" };

/** The career document, shared by the tab and the Home widget. */
export function useCareer() {
  const res = useResource<Career>("career", () => careerApi.get(), { staleMs: 30_000 });
  return { career: res.data ?? null, error: res.data ? null : res.error, mutate: res.mutate, reload: res.reload };
}

const newId = () => Math.random().toString(36).slice(2, 14);
const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
const hours = (h: number) => `${Number.isInteger(h) ? h : h.toFixed(1)} h`;

export function Career() {
  const { career, error, mutate } = useCareer();
  const [params, setParams] = useSearchParams();
  const view = (VIEWS.find((v) => v.id === params.get("view"))?.id ?? "overview") as View;
  const [saveError, setSaveError] = useState<string | null>(null);

  async function save(next: CareerDocument) {
    if (!career) return;
    mutate({ ...career, document: next }); // optimistic
    try {
      mutate(await careerApi.save(next));
      setSaveError(null);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Couldn't save.");
    }
  }

  const doc = career?.document;
  return (
    <>
      <PageHead eyebrow={doc ? `${doc.profile.discipline} · ${doc.profile.area_of_practice}` : "Career"} title="Career" />
      <div className="row career-views" role="tablist" aria-label="Career views">
        {VIEWS.map((v) => (
          <button
            key={v.id}
            type="button"
            role="tab"
            aria-selected={view === v.id}
            className={`chip chip--button ${view === v.id ? "chip--active" : ""}`}
            onClick={() => setParams(v.id === "overview" ? {} : { view: v.id }, { replace: true })}
          >
            {v.label}
          </button>
        ))}
      </div>
      {error && <div className="error-banner" role="alert">{error}</div>}
      {saveError && <div className="error-banner" role="alert">{saveError}</div>}
      {!career && !error && <div className="skeleton" style={{ height: 180, marginTop: 16 }} aria-busy="true" />}
      {career && view === "overview" && <Overview career={career} />}
      {career && view === "cpd" && <CpdView career={career} onChange={mutate} />}
      {career && view === "pathways" && <Pathways doc={career.document} onSave={save} />}
      {career && view === "competencies" && <Competencies career={career} onSave={save} />}
      {career && view === "goals" && <Goals doc={career.document} onSave={save} />}
    </>
  );
}

function Card({ title, Icon, wide, children, action }: { title: string; Icon: LucideIcon; wide?: boolean; children: ReactNode; action?: ReactNode }) {
  return (
    <Glass as="section" className={`widget ${wide ? "widget--wide" : ""}`} aria-label={title}>
      <header className="widget__head">
        <Icon aria-hidden="true" />
        <span>{title}</span>
        {action && <span className="widget__source">{action}</span>}
      </header>
      {children}
    </Glass>
  );
}

function Bar({ value, max, tone }: { value: number; max: number; tone?: string }) {
  const pct = Math.max(0, Math.min(100, max ? (value / max) * 100 : 0));
  return (
    <span className="career-bar" role="presentation">
      <span className={`career-bar__fill ${tone ?? ""}`} style={{ width: `${pct}%` }} />
    </span>
  );
}

export function CpdProgress({ cpd }: { cpd: CpdSummary }) {
  return (
    <>
      <div className="row" style={{ alignItems: "baseline", gap: 10 }}>
        <span className="hud-big">{Math.round(cpd.total)}</span>
        <span className="muted" style={{ fontSize: 15 }}>of {cpd.required} hours · last {cpd.window.years} years</span>
      </div>
      <Bar value={cpd.total} max={cpd.required} tone={cpd.met ? "career-bar__fill--good" : ""} />
      <ul className="career-mins">
        {cpd.minimums.map((m) => (
          <li key={m.category}>
            <span className="career-mins__label">{m.label}</span>
            <Bar value={m.hours} max={m.minimum} tone={m.short ? "" : "career-bar__fill--good"} />
            <span className={`career-mins__value ${m.short ? "" : "tone-good"}`}>{Math.round(m.hours * 10) / 10}/{m.minimum}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

function Overview({ career }: { career: Career }) {
  const { overview: ov, document: doc } = career;
  const cpd = ov.cpd;
  return (
    <div className="widget-grid" style={{ marginTop: 16 }}>
      <Card title="Next steps" Icon={Compass} wide>
        {ov.next_steps.length ? (
          <ul className="items">
            {ov.next_steps.map((s, i) => (
              <li key={i} className="item">
                <span className={`item__dot ${s.kind === "cpd" ? "dot-warning" : ""}`} aria-hidden="true" />
                <span className="item__text">
                  <span className="item__title career-wrap">{s.title}</span>
                  <span className="item__subtitle career-wrap">{s.detail}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted" style={{ margin: 0 }}>Nothing outstanding.</p>
        )}
      </Card>

      <Card title="CPD" Icon={Award} action={<Link to="/career?view=cpd" className="widget__source">Details</Link>}>
        {cpd.records ? (
          <>
            <CpdProgress cpd={cpd} />
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>
              From Engineers Australia{cpd.last_import ? `, imported ${fmtDate(cpd.last_import.at)}` : ""}.
              {cpd.expiring_90_days > 0 && ` ${hours(cpd.expiring_90_days)} leave the window in the next 90 days.`}
            </p>
          </>
        ) : (
          <>
            <p className="muted" style={{ margin: 0 }}>Import your CPD record from Engineers Australia to see your 3-year totals.</p>
            <Link to="/career?view=cpd" className="brief-link">Import CPD</Link>
          </>
        )}
      </Card>

      <Card title="Pathways" Icon={RouteIcon} action={<Link to="/career?view=pathways" className="widget__source">Open</Link>}>
        <ul className="career-mins">
          {ov.pathways.map((p) => (
            <li key={p.id} className="career-path">
              <span className="career-mins__label">{p.name}</span>
              <Bar value={p.done} max={p.total} tone={p.done === p.total ? "career-bar__fill--good" : ""} />
              <span className="career-mins__value">{p.done}/{p.total}</span>
              {p.next && <span className="career-path__next">Next: {p.next.title}</span>}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Competencies" Icon={ListChecks} action={<Link to="/career?view=competencies" className="widget__source">Open</Link>}>
        <p className="muted" style={{ margin: 0 }}>{ov.competencies.evidenced} of {ov.competencies.total} Stage 2 elements have evidence</p>
        <div className="career-grid" aria-label="Evidence per element">
          {doc.elements.map((e) => {
            const n = ov.competencies.counts[e.id] ?? 0;
            return (
              <span key={e.id} className={`career-cell career-cell--${Math.min(n, 3)}`} title={`${e.id}. ${e.title}: ${n} piece${n === 1 ? "" : "s"} of evidence`}>
                {e.id}
              </span>
            );
          })}
        </div>
      </Card>

      <Card title="Goals" Icon={Flag} action={<Link to="/career?view=goals" className="widget__source">Open</Link>}>
        {ov.goals.length ? (
          <ul className="items">
            {ov.goals.slice(0, 4).map((g) => (
              <li key={g.id} className="item">
                <span className="item__dot" aria-hidden="true" />
                <span className="item__text">
                  <span className="item__title career-wrap">{g.title}</span>
                  <span className="item__subtitle career-wrap">{[g.target_date && `by ${fmtDate(g.target_date)}`, g.next_step].filter(Boolean).join(" · ")}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted" style={{ margin: 0 }}>No goals yet. <Link to="/career?view=goals" className="brief-link">Add one</Link></p>
        )}
      </Card>

      <Card title="In your Second Brain" Icon={BrainIcon}>
        <ul className="items">
          {doc.profile.brain_notes.map((n) => (
            <li key={n}>
              <Link className="item" to={`/brain?q=${encodeURIComponent(n)}`}>
                <span className="item__dot" style={{ background: "var(--brain)" }} aria-hidden="true" />
                <span className="item__text"><span className="item__title">{n}</span></span>
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function CpdView({ career, onChange }: { career: Career; onChange: (c: Career) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const { overview: ov, document: doc } = career;
  const records = doc.cpd.records;

  async function upload(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setMessage(null);
    try {
      const r = await careerApi.importCpd(file);
      onChange(r);
      const i = r.import;
      setMessage({ ok: true, text: `Imported ${file.name}: ${i.added} new, ${i.updated} updated, ${i.unchanged} already here.` });
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Import failed." });
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function recategorise(id: string, value: string) {
    try {
      onChange(await careerApi.recategorise(id, value === "auto" ? null : (value as CpdCategory)));
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Couldn't change the category." });
    }
  }

  return (
    <div className="stack" style={{ marginTop: 16 }}>
      <Glass className="widget" style={{ minHeight: 0 }} aria-label="Import from Engineers Australia">
        <header className="widget__head"><FileUp aria-hidden="true" /><span>From Engineers Australia</span></header>
        <p className="muted" style={{ margin: 0 }}>
          Keep logging CPD in Engineers Australia. To update this view, open myPortal, choose <b>Record my CPD</b>, set the date range to
          the last 3 years (or everything), and export as <b>CSV or Excel</b>. Then import that file here. Importing again only adds or
          updates activities, never duplicates them.
        </p>
        <div className="row" style={{ flexWrap: "wrap" }}>
          <input ref={input} type="file" accept=".csv,.xlsx,.xlsm,.txt" hidden onChange={(e) => upload(e.target.files?.[0])} aria-label="CPD export file" />
          <Glass as="button" type="button" variant="tint" shape="pill" interactive className="button button--small" onClick={() => input.current?.click()} disabled={busy}>
            <FileUp aria-hidden="true" /> {busy ? "Importing…" : "Import export file"}
          </Glass>
          <Glass as="a" href={EA_PORTAL} target="_blank" rel="noreferrer" shape="pill" interactive className="button button--small">
            Open Engineers Australia <ArrowUpRight aria-hidden="true" />
          </Glass>
        </div>
        {message && <p className={message.ok ? "tone-good" : "tone-critical"} style={{ margin: 0, fontSize: 14 }} role="status">{message.text}</p>}
      </Glass>

      {records.length > 0 && (
        <>
          <div className="widget-grid">
            <Card title="Last 3 years" Icon={Award}>
              <CpdProgress cpd={ov.cpd} />
              <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                {fmtDate(ov.cpd.window.from)} to {fmtDate(ov.cpd.window.to)}.
                {ov.cpd.expiring_90_days > 0 && ` ${hours(ov.cpd.expiring_90_days)} drop out in the next 90 days.`}
              </p>
            </Card>
            <Card title="By year" Icon={CircleDashed}>
              <ul className="career-mins">
                {Object.entries(ov.cpd.by_year).map(([year, h]) => (
                  <li key={year}>
                    <span className="career-mins__label">{year}</span>
                    <Bar value={h} max={Math.max(50, ...Object.values(ov.cpd.by_year))} />
                    <span className="career-mins__value">{hours(h)}</span>
                  </li>
                ))}
              </ul>
              {ov.cpd.guessed > 0 && (
                <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                  {ov.cpd.guessed} activit{ov.cpd.guessed === 1 ? "y's" : "ies'"} category was guessed from its title (marked “guess”). Change it below if it's wrong.
                </p>
              )}
            </Card>
          </div>

          <Glass className="widget" style={{ minHeight: 0 }} aria-label="Activities">
            <header className="widget__head"><ListChecks aria-hidden="true" /><span>{records.length} activities</span></header>
            <ul className="items">
              {records.map((r) => {
                const override = doc.cpd.overrides[r.id];
                const main = override ?? (Object.entries(r.split).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0]?.[0] as CpdCategory | undefined) ?? "other";
                const mixed = !override && Object.keys(r.split).length > 1;
                return (
                  <li key={r.id} className="item career-cpd">
                    <span className="item__text">
                      <span className="item__title career-wrap">{r.title}</span>
                      <span className="item__subtitle">{[fmtDate(r.date), r.provider, r.type].filter(Boolean).join(" · ")}</span>
                    </span>
                    <span className="career-cpd__hours">{hours(r.hours)}</span>
                    {mixed ? (
                      <span className="chip" title="Split by the export's own columns">
                        {Object.entries(r.split).map(([c, h]) => `${CATEGORY_LABEL[c as CpdCategory].split(" ")[0]} ${h}`).join(" · ")}
                      </span>
                    ) : (
                      <label className="career-cpd__cat">
                        <span className="sr-only">Category for {r.title}</span>
                        <select className="field career-select" value={override ?? (r.basis === "export" ? main : "auto")} onChange={(e) => recategorise(r.id, e.target.value)}>
                          {r.basis !== "export" && <option value="auto">{CATEGORY_LABEL[main]} (guess)</option>}
                          {(Object.keys(CATEGORY_LABEL) as CpdCategory[]).map((c) => (
                            <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>
                          ))}
                        </select>
                      </label>
                    )}
                  </li>
                );
              })}
            </ul>
          </Glass>
        </>
      )}
    </div>
  );
}

function Pathways({ doc, onSave }: { doc: CareerDocument; onSave: (d: CareerDocument) => void }) {
  function update(pathwayId: string, stepId: string, change: Partial<CareerDocument["pathways"][number]["steps"][number]>) {
    onSave({
      ...doc,
      pathways: doc.pathways.map((p) =>
        p.id !== pathwayId ? p : { ...p, steps: p.steps.map((s) => (s.id !== stepId ? s : { ...s, ...change })) },
      ),
    });
  }
  return (
    <div className="stack" style={{ marginTop: 16 }}>
      {doc.pathways.map((p) => {
        const live = p.steps.filter((s) => s.status !== "na");
        const done = live.filter((s) => s.status === "done").length;
        return (
          <Glass key={p.id} as="section" className="widget" style={{ minHeight: 0 }} aria-label={p.name}>
            <header className="widget__head">
              <RouteIcon aria-hidden="true" />
              <span style={{ color: "var(--ink)", fontSize: 15, letterSpacing: 0, textTransform: "none" }}>{p.name}</span>
              <span className="widget__source">{done}/{live.length}</span>
            </header>
            <p className="muted" style={{ margin: 0 }}>
              {p.summary}{" "}
              {p.url && <a href={p.url} target="_blank" rel="noreferrer" className="brief-link">{p.body} <ArrowUpRight size={12} aria-hidden="true" /></a>}
            </p>
            <ol className="career-steps">
              {p.steps.map((s) => {
                const st = STATUS[s.status];
                return (
                  <li key={s.id} className={`career-step career-step--${s.status}`}>
                    <button
                      type="button"
                      className={`icon-link ${st.tone}`}
                      onClick={() => {
                        const next = NEXT_STATUS[s.status];
                        update(p.id, s.id, { status: next, done_on: next === "done" ? new Date().toISOString().slice(0, 10) : null });
                      }}
                      aria-label={`${s.title}: ${st.label}. Change status`}
                      title={`${st.label}. Tap to change`}
                    >
                      <st.Icon size={18} aria-hidden="true" />
                    </button>
                    <div className="career-step__text">
                      <div className="career-step__title">{s.title} {s.status !== "todo" && <span className={`chip career-chip ${st.tone}`}>{st.label}{s.done_on ? ` ${fmtDate(s.done_on)}` : ""}</span>}</div>
                      {s.detail && <div className="item__subtitle career-wrap">{s.detail}</div>}
                      <NoteField value={s.note} label={`Note for ${s.title}`} onSave={(note) => update(p.id, s.id, { note })} />
                    </div>
                  </li>
                );
              })}
            </ol>
          </Glass>
        );
      })}
      <p className="muted" style={{ margin: "0 6px", fontSize: 13 }}>
        Steps are a starting point from October 2026. Check each body's current requirements with the links above.
      </p>
    </div>
  );
}

function NoteField({ value, label, onSave, placeholder = "Add a note" }: { value: string; label: string; onSave: (v: string) => void; placeholder?: string }) {
  const [text, setText] = useState(value);
  return (
    <input
      className="career-note"
      placeholder={placeholder}
      value={text}
      aria-label={label}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => text !== value && onSave(text)}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
    />
  );
}

function Competencies({ career, onSave }: { career: Career; onSave: (d: CareerDocument) => void }) {
  const doc = career.document;
  const [editing, setEditing] = useState<Evidence | null>(null);
  const units = useMemo(() => {
    const out = new Map<string, typeof doc.elements>();
    doc.elements.forEach((e) => out.set(e.unit, [...(out.get(e.unit) ?? []), e]));
    return [...out.entries()];
  }, [doc.elements]);
  const byElement = (id: string) => doc.evidence.filter((ev) => ev.elements.includes(id));

  function saveEvidence(ev: Evidence) {
    const exists = doc.evidence.some((x) => x.id === ev.id);
    onSave({ ...doc, evidence: exists ? doc.evidence.map((x) => (x.id === ev.id ? ev : x)) : [ev, ...doc.evidence] });
    setEditing(null);
  }
  function remove(id: string) {
    onSave({ ...doc, evidence: doc.evidence.filter((x) => x.id !== id) });
    setEditing(null);
  }

  return (
    <div className="stack" style={{ marginTop: 16 }}>
      <div className="row">
        <p className="muted" style={{ margin: "0 6px", flex: 1 }}>
          Chartered means showing all 16 elements from your own work. Add evidence (a project, a decision, a report) and tag the elements it shows.
        </p>
        <Glass as="button" type="button" variant="tint" shape="pill" interactive className="button button--small"
          onClick={() => setEditing({ id: newId(), title: "", summary: "", date: null, elements: [], links: [] })}>
          <Plus aria-hidden="true" /> Evidence
        </Glass>
      </div>
      {units.map(([unit, elements]) => (
        <Glass key={unit} as="section" className="widget" style={{ minHeight: 0 }} aria-label={unit}>
          <header className="widget__head"><ListChecks aria-hidden="true" /><span>{unit}</span></header>
          <ul className="items">
            {elements.map((e) => {
              const evidence = byElement(e.id);
              return (
                <li key={e.id} className="career-element">
                  <div className="row" style={{ gap: 10 }}>
                    <span className={`career-cell career-cell--${Math.min(evidence.length, 3)}`}>{e.id}</span>
                    <span className="item__title career-wrap" style={{ flex: 1 }}>{e.title}</span>
                    <span className={`muted ${evidence.length ? "" : "tone-warning"}`} style={{ fontSize: 13 }}>
                      {evidence.length ? `${evidence.length} piece${evidence.length === 1 ? "" : "s"}` : "No evidence yet"}
                    </span>
                  </div>
                  {evidence.length > 0 && (
                    <div className="career-evidence">
                      {evidence.map((ev) => (
                        <button key={ev.id} type="button" className="chip chip--button" onClick={() => setEditing(ev)}>{ev.title}</button>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </Glass>
      ))}
      {editing && (
        <EvidenceSheet
          evidence={editing}
          elements={doc.elements}
          isNew={!doc.evidence.some((x) => x.id === editing.id)}
          onClose={() => setEditing(null)}
          onSave={saveEvidence}
          onDelete={() => remove(editing.id)}
        />
      )}
    </div>
  );
}

function EvidenceSheet({ evidence, elements, isNew, onClose, onSave, onDelete }: {
  evidence: Evidence; elements: CareerDocument["elements"]; isNew: boolean;
  onClose: () => void; onSave: (e: Evidence) => void; onDelete: () => void;
}) {
  const [ev, setEv] = useState(evidence);
  const [link, setLink] = useState("");
  function addLink() {
    const value = link.trim();
    if (!value) return;
    const url = /^https?:\/\//i.test(value) || value.startsWith("/") ? value : `/brain?q=${encodeURIComponent(value)}`;
    const label = url.startsWith("/brain?q=") ? value : value.replace(/^https?:\/\//i, "").slice(0, 80);
    setEv({ ...ev, links: [...ev.links, { label, url }] });
    setLink("");
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    if (ev.title.trim()) onSave({ ...ev, title: ev.title.trim() });
  }
  return (
    <Sheet label={isNew ? "Add evidence" : "Edit evidence"} onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <h2 className="app-sheet__name">{isNew ? "Add evidence" : "Edit evidence"}</h2>
        <input className="field" placeholder="What you did, e.g. Pump station risk workshop" value={ev.title} onChange={(e) => setEv({ ...ev, title: e.target.value })} aria-label="Title" required />
        <input className="field" type="date" value={ev.date ?? ""} onChange={(e) => setEv({ ...ev, date: e.target.value || null })} aria-label="Date" />
        <textarea className="field" rows={4} placeholder="Your role, what you decided or delivered, and the outcome" value={ev.summary} onChange={(e) => setEv({ ...ev, summary: e.target.value })} aria-label="Summary" />
        <div>
          <p className="muted" style={{ margin: "0 0 8px", fontSize: 13 }}>Elements this shows</p>
          <div className="career-evidence">
            {elements.map((el) => {
              const on = ev.elements.includes(el.id);
              return (
                <button key={el.id} type="button" className={`chip chip--button ${on ? "chip--active" : ""}`} aria-pressed={on}
                  onClick={() => setEv({ ...ev, elements: on ? ev.elements.filter((x) => x !== el.id) : [...ev.elements, el.id] })}>
                  {el.id}. {el.title}
                </button>
              );
            })}
          </div>
        </div>
        <div className="stack" style={{ gap: 6 }}>
          {ev.links.map((l, i) => (
            <div key={i} className="row">
              {l.url.startsWith("/") ? <Link to={l.url} className="brief-link" style={{ flex: 1 }}>{l.label}</Link> : <a href={l.url} target="_blank" rel="noreferrer" className="brief-link" style={{ flex: 1 }}>{l.label}</a>}
              <button type="button" className="icon-link" aria-label={`Remove ${l.label}`} onClick={() => setEv({ ...ev, links: ev.links.filter((_, j) => j !== i) })}><Trash2 size={15} aria-hidden="true" /></button>
            </div>
          ))}
          <div className="row">
            <input className="field" placeholder="Link: a Second Brain note title, or a URL (APD PM, Archive…)" value={link} onChange={(e) => setLink(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addLink(); } }} aria-label="Add a link" />
            <Glass as="button" type="button" shape="pill" interactive className="button button--icon" onClick={addLink} aria-label="Add link"><Plus aria-hidden="true" /></Glass>
          </div>
        </div>
        <div className="row">
          {!isNew && <button type="button" className="icon-link tone-critical" onClick={onDelete} aria-label="Delete evidence"><Trash2 size={17} aria-hidden="true" /></button>}
          <span className="spacer" />
          <Glass as="button" type="submit" variant="tint" shape="pill" interactive className="button button--small" disabled={!ev.title.trim()}>Save</Glass>
        </div>
      </form>
    </Sheet>
  );
}

function Goals({ doc, onSave }: { doc: CareerDocument; onSave: (d: CareerDocument) => void }) {
  const [draft, setDraft] = useState({ title: "", target_date: "", next_step: "" });
  function add(e: FormEvent) {
    e.preventDefault();
    if (!draft.title.trim()) return;
    const goal: Goal = { id: newId(), title: draft.title.trim(), target_date: draft.target_date || null, next_step: draft.next_step.trim(), status: "active", note: "" };
    onSave({ ...doc, goals: [...doc.goals, goal] });
    setDraft({ title: "", target_date: "", next_step: "" });
  }
  const update = (id: string, change: Partial<Goal>) => onSave({ ...doc, goals: doc.goals.map((g) => (g.id === id ? { ...g, ...change } : g)) });
  return (
    <div className="stack" style={{ marginTop: 16 }}>
      <Glass as="form" className="widget" style={{ minHeight: 0 }} onSubmit={add} aria-label="New goal">
        <header className="widget__head"><Flag aria-hidden="true" /><span>New goal</span></header>
        <input className="field" placeholder="e.g. Chartered (CPEng) by mid 2027" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} aria-label="Goal" />
        <div className="row" style={{ flexWrap: "wrap" }}>
          <input className="field" style={{ flex: "1 1 160px" }} type="date" value={draft.target_date} onChange={(e) => setDraft({ ...draft, target_date: e.target.value })} aria-label="Target date" />
          <input className="field" style={{ flex: "3 1 240px" }} placeholder="Next step" value={draft.next_step} onChange={(e) => setDraft({ ...draft, next_step: e.target.value })} aria-label="Next step" />
        </div>
        <div className="row"><span className="spacer" />
          <Glass as="button" type="submit" variant="tint" shape="pill" interactive className="button button--small" disabled={!draft.title.trim()}><Plus aria-hidden="true" /> Add goal</Glass>
        </div>
      </Glass>
      {doc.goals.map((g) => (
        <Glass key={g.id} as="section" className={`widget ${g.status !== "active" ? "career-goal--quiet" : ""}`} style={{ minHeight: 0 }} aria-label={g.title}>
          <div className="row">
            <button type="button" className={`icon-link ${g.status === "done" ? "tone-good" : ""}`} aria-label={g.status === "done" ? `Mark ${g.title} active` : `Mark ${g.title} done`}
              onClick={() => update(g.id, { status: g.status === "done" ? "active" : "done" })}>
              {g.status === "done" ? <Check size={18} aria-hidden="true" /> : <Circle size={18} aria-hidden="true" />}
            </button>
            <span className="item__title career-wrap" style={{ flex: 1 }}>{g.title}</span>
            {g.target_date && <span className="chip">{fmtDate(g.target_date)}</span>}
            <button type="button" className="icon-link" aria-label={`Delete ${g.title}`} onClick={() => onSave({ ...doc, goals: doc.goals.filter((x) => x.id !== g.id) })}><Trash2 size={16} aria-hidden="true" /></button>
          </div>
          <NoteField value={g.next_step} label={`Next step for ${g.title}`} placeholder="Next step" onSave={(next_step) => update(g.id, { next_step })} />
        </Glass>
      ))}
    </div>
  );
}
