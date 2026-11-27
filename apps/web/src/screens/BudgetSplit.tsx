import { useEffect, useRef, useState } from "react";
import { RefreshCw, Scale } from "lucide-react";
import { budget, type Split, type SplitChoices, type SplitMethod, type SplitState } from "../api/budget";
import { Glass } from "../components/Glass";

const METHODS: { id: SplitMethod; label: string; about: string }[] = [
  { id: "income", label: "By income", about: "Everyone puts in the same share of what they earn." },
  { id: "equal", label: "Equally", about: "Everyone puts in the same amount." },
  { id: "lines", label: "Whole lines", about: "Each line goes to one source, as close to by-income as whole lines allow: fewer transfers." },
];
const SECTION = { expenses: "Expenses", savings: "Savings", spending: "Spending" } as const;
const PER = { weekly: "week", fortnightly: "fortnight", monthly: "month", quarterly: "quarter", yearly: "year" } as const;
const money = (n: number) => `$${Math.round(n).toLocaleString()}`;
const when = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

/** How the expenses, savings and spending are best split between the incomes (11.12): all of them or some, by income,
 * equally or by whole lines, with personal lines kept to their owner. A kept split is checked against the budget, and
 * when the budget changes it says what changed, with Redo. `savedAt` changes when the budget is saved. */
export function SplitCard({ savedAt }: { savedAt: number }) {
  const [state, setState] = useState<SplitState | null>(null);
  const [choices, setChoices] = useState<SplitChoices | null>(null);
  const [preview, setPreview] = useState<Split | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);  // the source whose lines are shown
  const [busy, setBusy] = useState(false);
  const first = useRef(true);

  // The kept split (or the default), again after each budget save.
  useEffect(() => {
    let live = true;
    budget.split().then((s) => {
      if (!live) return;
      setState(s);
      if (first.current) { setChoices(s.settings); first.current = false; }
    }).catch((e) => live && setMsg(e instanceof Error ? e.message : "Couldn't work out the split."));
    return () => { live = false; };
  }, [savedAt]);

  // What the chosen split would be, worked out as you choose.
  useEffect(() => {
    if (!choices) return undefined;
    const t = window.setTimeout(() => {
      budget.previewSplit(choices).then((p) => { setPreview(p); setMsg(null); })
        .catch((e) => { setPreview(null); setMsg(e instanceof Error ? e.message.replace(/^.*?: /, "") : "Couldn't work it out."); });
    }, 250);
    return () => window.clearTimeout(t);
  }, [choices, savedAt]);

  if (!state || !choices) return null;
  const all = [...(preview?.sources ?? state.now?.sources ?? []), ...(preview?.left_out ?? state.now?.left_out ?? [])];
  const incomes = (state.now ? [...state.now.sources, ...state.now.left_out] : all).map((s) => ({ id: s.id, name: s.name }));
  const chosen = new Set(choices.sources.length ? choices.sources : incomes.map((s) => s.id));
  const toggle = (id: string) => {
    const next = new Set(chosen);
    if (next.has(id)) next.delete(id); else next.add(id);
    setChoices({ ...choices, sources: next.size === incomes.length ? [] : [...next] });
  };
  const same = JSON.stringify(state.settings) === JSON.stringify(choices);
  const keep = async () => {
    setBusy(true);
    try { setState(await budget.keepSplit(choices)); } catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't keep it."); } finally { setBusy(false); }
  };
  const shown = preview;
  const personalNames = shown ? Object.keys(shown.personal).length : 0;

  return (
    <Glass as="section" className="widget budget-split" aria-label="Split between incomes">
      <header className="widget__head"><Scale aria-hidden="true" /><span>Split between incomes</span>
        {state.saved && <span className="widget__source">Kept {when(state.saved.made_at)}</span>}</header>

      {state.saved && state.stale && (
        <div className="budget-split__stale" role="status">
          <p style={{ margin: 0 }}><strong>The budget changed since this split.</strong> {state.changes.length ? state.changes.slice(0, 4).join("; ") + "." : ""}</p>
          <button type="button" className="button button--primary button--small" disabled={busy} onClick={() => { setChoices(state.settings); void budget.keepSplit(state.settings).then(setState); }}>
            <RefreshCw size={13} aria-hidden="true" /> Redo the split</button>
        </div>
      )}

      <div className="stack" style={{ gap: 6 }}>
        <span className="muted" style={{ fontSize: 13 }}>Which incomes share it</span>
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }} role="group" aria-label="Incomes in the split">
          <button type="button" className={`chip chip--button ${choices.sources.length === 0 ? "chip--active" : ""}`} aria-pressed={choices.sources.length === 0}
            onClick={() => setChoices({ ...choices, sources: [] })}>All</button>
          {incomes.map((s) => (
            <button key={s.id} type="button" className={`chip chip--button ${chosen.has(s.id) && choices.sources.length ? "chip--active" : ""}`}
              aria-pressed={chosen.has(s.id)} onClick={() => toggle(s.id)}>{s.name}</button>
          ))}
        </div>
      </div>

      <div className="segmented budget-split__methods" role="radiogroup" aria-label="How to split">
        {METHODS.map((m) => (
          <button key={m.id} type="button" role="radio" aria-checked={choices.method === m.id} className={`segmented__item${choices.method === m.id ? " segmented__item--on" : ""}`}
            onClick={() => setChoices({ ...choices, method: m.id })}>{m.label}</button>
        ))}
      </div>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>{METHODS.find((m) => m.id === choices.method)!.about}</p>

      {msg && <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}

      {shown && (
        <>
          {shown.short > 0 && (
            <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 14 }}>
              These incomes are {money(shown.short)} a month short of the budget ({money(shown.income)} in, {money(shown.total)} out).
              {shown.left_out.length ? ` ${shown.left_out.map((s) => s.name).join(" and ")} would cover ${money(Math.min(shown.short, shown.left_out.reduce((n, s) => n + s.income, 0)))} of it.` : ""}
            </p>
          )}
          <ul className="items budget-split__sources" aria-label="Each income's part">
            {shown.sources.map((s) => (
              <li key={s.id} className="budget-split__source">
                <button type="button" className="budget-split__head" aria-expanded={open === s.id} onClick={() => setOpen(open === s.id ? null : s.id)}>
                  <span className="budget-split__name">{s.name}</span>
                  <span className="budget-split__amount">{money(s.per_pay)} <span className="muted">a {PER[s.every]}</span></span>
                </button>
                <div className="budget-split__bar" aria-hidden="true">
                  {(Object.keys(SECTION) as (keyof typeof SECTION)[]).map((k) => (
                    <span key={k} className={`budget-split__seg budget-split__seg--${k}`} style={{ width: `${s.income ? (s.sections[k] / s.income) * 100 : 0}%` }} />
                  ))}
                </div>
                <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                  {s.every !== "monthly" ? `${money(s.total)} a month: ` : ""}{s.percent_of_income}% of its income ({s.share_of_budget}% of the budget, from {s.share_of_income}% of the income)
                  · {s.left >= 0 ? `${money(s.left)} left` : <span className="tone-warning">{money(-s.left)} over</span>}
                </p>
                <p style={{ margin: 0, fontSize: 13 }}>{(Object.keys(SECTION) as (keyof typeof SECTION)[]).filter((k) => s.sections[k] > 0)
                  .map((k) => `${SECTION[k]} ${money(s.sections[k])}`).join(" · ")}</p>
                {open === s.id && (
                  <ul className="budget-split__lines" aria-label={`${s.name}: the lines`}>
                    {s.lines.map((l) => (
                      <li key={l.id}><span>{l.name}{l.personal ? <span className="muted"> · personal</span> : !l.whole ? <span className="muted"> · share</span> : null}</span><span>{money(l.monthly)}</span></li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>

          <details className="budget-split__personal">
            <summary style={{ fontSize: 14 }}>Personal lines ({personalNames})</summary>
            <p className="muted" style={{ margin: "4px 0", fontSize: 12 }}>A personal line is paid by its owner's income, whatever the method; the rest is shared. Lines naming someone are suggested.</p>
            <ul className="items">
              {shown.lines.map((l) => {
                const value = choices.personal[l.id] ?? shown.personal[l.id] ?? "shared";
                return (
                  <li key={l.id} className="item budget-split__pick">
                    <span className="item__text"><span className="item__title">{l.name}</span><span className="item__subtitle">{SECTION[l.section as keyof typeof SECTION]} · {money(l.monthly)} a month</span></span>
                    <select className="field" aria-label={`Who pays ${l.name}`} value={value}
                      onChange={(e) => setChoices({ ...choices, personal: { ...choices.personal, [l.id]: e.target.value } })}>
                      <option value="shared">Shared</option>
                      {shown.sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                  </li>
                );
              })}
            </ul>
          </details>

          <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <button type="button" className="button button--primary" disabled={busy || (same && !!state.saved && !state.stale)} onClick={keep}>
              {state.saved ? (same && !state.stale ? "Kept" : "Keep this split") : "Keep this split"}</button>
            {!same && state.saved && <button type="button" className="chip chip--button" onClick={() => setChoices(state.settings)}>Back to the kept one</button>}
          </div>
        </>
      )}
    </Glass>
  );
}
