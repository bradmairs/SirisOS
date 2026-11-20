import { useState } from "react";
import { ClipboardCheck } from "lucide-react";
import { ApiError } from "../api/client";
import { brain, type BrainDebriefAnswers } from "../api/hub";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

const EMPTY: BrainDebriefAnswers = { project: "", decided: "", went_wrong: "", differently: "", cpeng: "" };

const QUESTIONS: { key: keyof Omit<BrainDebriefAnswers, "project" | "cpeng">; label: string }[] = [
  { key: "decided", label: "What did you decide this week, and why?" },
  { key: "went_wrong", label: "What went wrong or surprised you?" },
  { key: "differently", label: "What would you do differently next time?" },
];

const LOCAL_DISMISS = "sirisos.debrief.dismissed";
const today = () => new Date().toLocaleDateString("en-CA");  // YYYY-MM-DD, this device's day

/**
 * The Friday work debrief (9.9). 10.33: on Friday only (not the weekend after); after saving, "Add another" for
 * another project or "Done"; "Nothing this week" puts it away until next Friday. Before SirisAI 7.29 (which decides
 * the day itself), it's shown on this device's Fridays only, and dismissed on this device.
 *
 * Open until it's answered. Each answer is filed by SirisAI
 * on the project picked (or Work Debriefs): the decision also goes in the Decision Log, what you'd do
 * differently in Lessons Learned, and a CPEng example where the nightly evidence check reads it.
 * Hidden when SirisAI is older than 7.07 (404) or the brain isn't set up.
 */
export function DebriefCard() {
  const res = useResource("brain:debrief", () => brain.debrief().catch((e) => {
    if (e instanceof ApiError && (e.status === 404 || e.status === 503)) return null;
    throw e;
  }), { staleMs: 30 * 60_000 });
  const [answers, setAnswers] = useState<BrainDebriefAnswers>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [another, setAnother] = useState(false);
  const [closed, setClosed] = useState(() => { try { return localStorage.getItem(LOCAL_DISMISS) === today(); } catch { return false; } });
  const status = res.data;

  if (closed) return null;
  if (done) {
    return (
      <Glass as="section" className="widget debrief" style={{ minHeight: 0, marginTop: 14 }} aria-label="Friday debrief">
        <header className="widget__head"><ClipboardCheck aria-hidden="true" /><span>Friday debrief</span></header>
        <p className="tone-good" role="status" style={{ margin: 0 }}>{done}</p>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <Glass as="button" type="button" shape="pill" interactive className="button button--small"
            onClick={() => { setAnswers(EMPTY); setDone(null); setAnother(true); }}>Add another</Glass>
          <button type="button" className="button button--small button--ghost" onClick={() => setClosed(true)}>Done</button>
        </div>
      </Glass>
    );
  }
  // Older SirisAI (no `dismissed`) kept it open all weekend: then it's Fridays only, by this device's clock.
  const fridayHere = new Date().getDay() === 5;
  if (!another && (!status?.open || (status.dismissed === undefined && !fridayHere))) return null;
  if (!status) return null;

  async function dismiss() {
    setError(null);
    try {
      res.mutate(await brain.dismissDebrief());
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 404)) { setError(e instanceof Error ? e.message : "That didn't work."); return; }
      try { localStorage.setItem(LOCAL_DISMISS, today()); } catch { /* fine */ }
    }
    setAnother(false);
    setClosed(true);
  }

  const set = (key: keyof BrainDebriefAnswers) => (e: { target: { value: string } }) =>
    setAnswers((a) => ({ ...a, [key]: e.target.value }));
  const written = QUESTIONS.some((q) => answers[q.key].trim()) || answers.cpeng.trim() !== "";

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const r = await brain.answerDebrief(answers);
      const extra = [r.decision && "the Decision Log", r.lesson && "Lessons Learned"].filter(Boolean).join(" and ");
      setDone(`Filed on ${r.filed}${extra ? `, and in ${extra}` : ""}. Another project to add, or done for the week?`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Glass as="section" className="widget debrief" style={{ minHeight: 0, marginTop: 14 }} aria-label="Friday debrief">
      <header className="widget__head"><ClipboardCheck aria-hidden="true" /><span>Friday debrief</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>
        A few lines on the work week, while it's fresh. Answer any of them; Siris files each where it belongs.
      </p>
      <label className="stack debrief__field">
        <span>Project</span>
        <select className="field" value={answers.project} onChange={set("project")}>
          <option value="">No particular project</option>
          {status.projects.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </label>
      {QUESTIONS.map((q) => (
        <label key={q.key} className="stack debrief__field">
          <span>{q.label}</span>
          <textarea className="field" rows={2} value={answers[q.key]} onChange={set(q.key)} />
        </label>
      ))}
      {status.cpeng_question && (
        <label className="stack debrief__field">
          <span>{status.cpeng_question}</span>
          <textarea className="field" rows={3} value={answers.cpeng} onChange={set("cpeng")} />
        </label>
      )}
      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <Glass as="button" type="button" shape="pill" interactive className="button button--small button--primary"
          onClick={save} disabled={busy || !written}>
          {busy ? "Saving…" : "Save to Siris"}
        </Glass>
        {another
          ? <button type="button" className="button button--small button--ghost" onClick={() => { setAnother(false); setClosed(true); }}>That's all</button>
          : <button type="button" className="button button--small button--ghost" onClick={() => void dismiss()}>Nothing this week</button>}
      </div>
    </Glass>
  );
}
