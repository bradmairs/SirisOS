import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Check, Circle, ClipboardCheck, Download, FileUp, Sparkles, Trash2 } from "lucide-react";
import { application as appApi, type ApplicationAnswers, type ApplicationView, type BiaState, type FormId } from "../api/career";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

const words = (s: string) => (s.match(/\w+/g) ?? []).length;

/** Career → Application (4.6): Engineers Australia's three forms for the
 * Chartered interview, worked through here, with what's left. */
export function ApplicationTab({ areaHint }: { areaHint: string }) {
  const res = useResource<ApplicationView>("career:application", () => appApi.get(), { staleMs: 30_000 });
  const [error, setError] = useState<string | null>(null);
  const view = res.data;

  async function save(next: ApplicationAnswers) {
    if (!view) return;
    res.mutate({ ...view, application: next }); // optimistic
    try {
      res.mutate(await appApi.save(next));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save.");
    }
  }

  if (!view) return res.error ? <div className="error-banner" role="alert">{res.error}</div> : <div className="skeleton" style={{ height: 180, marginTop: 16 }} aria-busy="true" />;
  const a = view.application;
  const doc = (id: FormId) => view.documents.find((d) => d.id === id)!;
  const set = (change: Partial<ApplicationAnswers>) => save({ ...a, ...change });

  return (
    <div className="stack" style={{ marginTop: 16 }}>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <Readiness view={view} />

      <FormCard form={doc("reflection")} file={a.files.reflection} onView={res.mutate}>
        <h3 className="career-app__h">Area of practice</h3>
        <TextField label="Primary area of practice sought" value={a.area_of_practice} placeholder={areaHint ? `e.g. ${areaHint}` : "Your main role"} onSave={(v) => set({ area_of_practice: v })} />
        <TextField label="Additional area of practice (optional)" value={a.additional_area} onSave={(v) => set({ additional_area: v })} />
        {a.additional_area.trim() && <TextField label="Why the additional area is relevant" value={a.additional_reason} multiline onSave={(v) => set({ additional_reason: v })} />}

        <h3 className="career-app__h">Part 1 · honest reflection</h3>
        <p className="muted career-app__note">"Not sure" isn't held against you: it shows what to prepare, and what to talk through with your assessor.</p>
        <ul className="items">
          {view.part1.map((q) => (
            <li key={q.id} className="career-app__q">
              <span className="career-wrap">{q.q} <span className="muted">· E{q.elements.join(", E")}</span></span>
              <Choice label={q.q} value={a.part1[q.id]} options={[["yes", "Yes"], ["not_sure", "Not sure"]]} onChange={(v) => set({ part1: { ...a.part1, [q.id]: v as "yes" | "not_sure" } })} />
            </li>
          ))}
        </ul>

        <h3 className="career-app__h">Part 2</h3>
        <ul className="items">
          {view.part2.map((q) => (
            <li key={q.id} className="career-app__q">
              <span className="career-wrap">{q.q}</span>
              <Choice label={q.q} value={a.part2[q.id]} options={[["yes", "Yes"], ["no", "No"]]} onChange={(v) => set({ part2: { ...a.part2, [q.id]: v as "yes" | "no" } })} />
            </li>
          ))}
        </ul>

        <h3 className="career-app__h">Part 3 · the 16 elements</h3>
        <p className="muted career-app__note">Two or three sentences each, about one specific, recent work episode and what you did. They help you get ready: your evidence is what you share at the interview.</p>
        {view.elements.map((el) => (
          <ElementComment key={el.id} el={el} value={a.part3[el.id] ?? ""} onSave={(v) => set({ part3: { ...a.part3, [el.id]: v } })} />
        ))}

        <h3 className="career-app__h">Part 4 · statement</h3>
        <label className="career-app__check">
          <input type="checkbox" checked={a.signed} onChange={(e) => set({ signed: e.target.checked })} />
          <span>I completed this myself, and it reflects my own understanding. Signed and dated on the form.</span>
        </label>
      </FormCard>

      <FormCard form={doc("cpd")} file={a.files.cpd} onView={res.mutate}>
        <p className="muted career-app__note">No minimum hours to apply. Once you're Chartered, it's 150 hours every three years with the area, risk and business minimums (the CPD tab tracks them).</p>
        <Choice label="How you'll show your CPD" value={a.cpd_evidence ?? undefined} options={[["log", "Send my EA CPD log"], ["questionnaire", "Answer the questionnaire"]]} onChange={(v) => set({ cpd_evidence: v as "log" | "questionnaire" })} />
        {a.cpd_evidence === "log" && (
          <p className="muted career-app__note">Export your CPD from the Engineers Australia portal and send it with the application. Import the same file in <Link to="/career?view=cpd" className="brief-link">CPD</Link> to keep the totals here.</p>
        )}
        {a.cpd_evidence === "questionnaire" && (
          <>
            <p className="muted career-app__note">Answer for the last three years, with rough hours. Write N/A where a question doesn't apply.</p>
            {view.cpd_questions.map((q) => (
              <CpdAnswer key={q.id} q={q} value={a.cpd_answers[q.id] ?? ""} onSave={(v) => set({ cpd_answers: { ...a.cpd_answers, [q.id]: v } })} />
            ))}
          </>
        )}
      </FormCard>

      <FormCard form={doc("bia")} file={a.files.bia} onView={res.mutate}>
        <p className="muted career-app__note">Needed only if you provide professional engineering services in the building industry in Victoria, WA or the ACT. Civil infrastructure work, like water and wastewater networks, usually isn't building work: check against your own projects.</p>
        <Choice label="Do you need a Building Industry Assessment?" value={a.bia.required == null ? undefined : a.bia.required ? "yes" : "no"} options={[["yes", "Yes"], ["no", "No"]]} onChange={(v) => set({ bia: { ...a.bia, required: v === "yes" } })} />
        {a.bia.required && (
          <>
            <Choice label="State or territory" value={a.bia.state ?? undefined} options={(Object.keys(view.bia_states) as BiaState[]).map((s) => [s, s])} onChange={(v) => set({ bia: { ...a.bia, state: v as BiaState } })} />
            {a.bia.state && (() => {
              const st = view.bia_states[a.bia.state];
              return (
                <>
                  <p className="muted career-app__note"><strong>{st.name}.</strong> Before the interview: a detailed CV, your CPD specific to the building industry, and a short statement showing {st.years} years of successful, relevant building-industry experience, with your knowledge and use of {st.laws}.</p>
                  <label className="career-app__check"><input type="checkbox" checked={a.bia.cv} onChange={(e) => set({ bia: { ...a.bia, cv: e.target.checked } })} /><span>Detailed CV ready</span></label>
                  <label className="career-app__check"><input type="checkbox" checked={a.bia.building_cpd} onChange={(e) => set({ bia: { ...a.bia, building_cpd: e.target.checked } })} /><span>Building-industry CPD gathered</span></label>
                  <TextField label="Statement of experience" value={a.bia.statement} multiline rows={8} onSave={(v) => set({ bia: { ...a.bia, statement: v } })} />
                </>
              );
            })()}
          </>
        )}
      </FormCard>
    </div>
  );
}

function Readiness({ view }: { view: ApplicationView }) {
  const r = view.readiness;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Ready for the interview">
      <header className="widget__head"><ClipboardCheck aria-hidden="true" /><span>Ready for the interview</span><span className="widget__source">{r.percent}%</span></header>
      <div className="career-bar" aria-hidden="true"><div className={`career-bar__fill ${r.percent === 100 ? "career-bar__fill--good" : ""}`} style={{ width: `${r.percent}%` }} /></div>
      <ul className="items">
        {r.items.map((i) => (
          <li key={i.id} className="item">
            {i.done ? <Check size={16} className="tone-good" aria-label="Done" /> : <Circle size={16} className="muted" aria-label="To do" />}
            <span className="item__text">
              <span className="item__title career-wrap">{i.label}</span>
              <span className="item__subtitle career-wrap">{i.detail}</span>
            </span>
          </li>
        ))}
      </ul>
      {r.prepare.length > 0 && (
        <>
          <p className="muted career-app__note" style={{ marginTop: 8 }}>To prepare (you said Not sure):</p>
          <ul className="career-app__prepare">{r.prepare.map((p) => <li key={p.id} className="career-wrap">{p.q} <span className="muted">(E{p.elements.join(", E")})</span></li>)}</ul>
        </>
      )}
      <p className="muted career-app__note">Track it on <Link to="/year" className="brief-link">Your year</Link> with a "Chartered application ready" goal.</p>
    </Glass>
  );
}

function FormCard({ form, file, onView, children }: {
  form: ApplicationView["documents"][number];
  file: ApplicationAnswers["files"][FormId];
  onView: (v: ApplicationView) => void;
  children: ReactNode;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState<string | null>(null);
  async function upload(f: File | undefined) {
    if (!f) return;
    try {
      onView(await appApi.upload(form.id, f));
      setMessage(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      if (input.current) input.current.value = "";
    }
  }
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label={form.title}>
      <details className="career-app__form">
        <summary>
          <span className="item__title">{form.title}</span>
          <span className="item__subtitle career-wrap">{form.summary}</span>
        </summary>
        <div className="career-app__body">
          <p className="muted career-app__note">{form.form}</p>
          {children}
        </div>
      </details>
      <div className="row career-app__file">
        {file ? (
          <>
            <button type="button" className="button button--small" onClick={() => appApi.download(form.id, file.filename).catch(() => undefined)}>
              <Download size={14} aria-hidden="true" /> {file.filename}
            </button>
            <button type="button" className="icon-link" aria-label={`Remove your copy of the ${form.title}`} onClick={async () => onView(await appApi.remove(form.id))}><Trash2 size={15} aria-hidden="true" /></button>
          </>
        ) : null}
        <button type="button" className="button button--small" onClick={() => input.current?.click()}>
          <FileUp size={14} aria-hidden="true" /> {file ? "Replace" : "Add your filled-in copy"}
        </button>
        <input ref={input} type="file" accept=".pdf,.doc,.docx,application/pdf" hidden aria-label={`Upload the ${form.title}`} onChange={(e) => upload(e.target.files?.[0])} />
      </div>
      {message && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 13 }}>{message}</p>}
    </Glass>
  );
}

function Choice({ label, value, options, onChange }: { label: string; value: string | undefined; options: [string, string][]; onChange: (v: string) => void }) {
  return (
    <div className="row career-app__choice" role="radiogroup" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={v} type="button" role="radio" aria-checked={value === v} className={`chip chip--button ${value === v ? "chip--active" : ""}`} onClick={() => onChange(v)}>{text}</button>
      ))}
    </div>
  );
}

function TextField({ label, value, onSave, placeholder, multiline, rows = 3 }: { label: string; value: string; onSave: (v: string) => void; placeholder?: string; multiline?: boolean; rows?: number }) {
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);
  const blur = () => { if (text !== value) onSave(text); };
  return (
    <label className="career-app__field">
      <span className="career-app__label">{label}</span>
      {multiline
        ? <textarea className="field" rows={rows} value={text} placeholder={placeholder} onChange={(e) => setText(e.target.value)} onBlur={blur} />
        : <input className="field" value={text} placeholder={placeholder} onChange={(e) => setText(e.target.value)} onBlur={blur} />}
    </label>
  );
}

function ElementComment({ el, value, onSave }: { el: ApplicationView["elements"][number]; value: string; onSave: (v: string) => void }) {
  const [text, setText] = useState(value);
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => setText(value), [value]);
  async function start() {
    const d = await appApi.draftElement(el.id).catch(() => null);
    if (d?.text) { setText(d.text); onSave(d.text); setNote(null); }
    else setNote("No evidence tagged to this element yet: add some in Competencies.");
  }
  const n = words(text);
  return (
    <div className="career-app__element">
      <label className="career-app__field">
        <span className="career-app__label">E{el.id} {el.title}</span>
        <span className="muted career-app__note">{el.meaning}</span>
        <textarea className="field" rows={3} value={text} onChange={(e) => setText(e.target.value)} onBlur={() => { if (text !== value) onSave(text); }} />
      </label>
      <div className="row career-app__tools">
        <span className={`muted ${n > 0 && n < 15 ? "tone-warning" : ""}`}>{n ? `${n} words` : "Not written"}</span>
        {!text.trim() && <button type="button" className="button button--small" onClick={start}><Sparkles size={14} aria-hidden="true" /> Start from my evidence</button>}
      </div>
      {note && <p className="muted career-app__note">{note}</p>}
    </div>
  );
}

function CpdAnswer({ q, value, onSave }: { q: ApplicationView["cpd_questions"][number]; value: string; onSave: (v: string) => void }) {
  const [text, setText] = useState(value);
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => setText(value), [value]);
  async function fill() {
    const d = await appApi.draftCpd(q.id).catch(() => null);
    if (d?.text) { setText(d.text); onSave(d.text); setNote(null); }
    else setNote("Nothing in your imported CPD matches this one.");
  }
  return (
    <div className="career-app__element">
      <label className="career-app__field">
        <span className="career-app__label">{q.q}</span>
        {q.type && <span className="muted career-app__note">{q.type}</span>}
        <textarea className="field" rows={3} value={text} onChange={(e) => setText(e.target.value)} onBlur={() => { if (text !== value) onSave(text); }} />
      </label>
      {!text.trim() && (
        <div className="row career-app__tools">
          <button type="button" className="button button--small" onClick={fill}><Sparkles size={14} aria-hidden="true" /> Fill from my CPD</button>
          <button type="button" className="button button--small" onClick={() => { setText("N/A"); onSave("N/A"); }}>N/A</button>
        </div>
      )}
      {note && <p className="muted career-app__note">{note}</p>}
    </div>
  );
}
