import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Mail, PiggyBank, Plus, Table2, Trash2, Wallet } from "lucide-react";
import {
  EMPTY, EVERY, PRESETS, SECTIONS, SECTION_HINT, SECTION_LABEL, budget, goals, money, monthly, newLine, nextPay, per, rule503020,
  savingsProjection, totals, type Budget, type Every, type Line, type Period, type Section,
} from "../api/budget";
import { Glass } from "../components/Glass";
import { Donut, Legend, LineChart, RankBars, ShareBar, TargetBars, type Datum } from "../components/Charts";

const COLOR: Record<Section | "left", string> = {
  expenses: "var(--b-expenses)", savings: "var(--b-savings)", spending: "var(--b-spending)", left: "var(--b-left)",
};
const PERIODS: { id: Period; label: string; noun: string }[] = [
  { id: "week", label: "Week", noun: "a week" }, { id: "fortnight", label: "Fortnight", noun: "a fortnight" },
  { id: "month", label: "Month", noun: "a month" }, { id: "year", label: "Year", noun: "a year" },
];
const EVERY_LABEL: Record<Every, string> = { weekly: "a week", fortnightly: "a fortnight", monthly: "a month", quarterly: "a quarter", yearly: "a year" };
const MONTH = (m: string) => new Date(`${m}-01T00:00:00`).toLocaleDateString(undefined, { month: "short", year: "2-digit" });

type Plan = Pick<Budget, "currency" | "income" | "sections">;

function LineRows({ lines, section, onChange, currency }: {
  lines: Line[]; section: Section | "income"; onChange: (lines: Line[]) => void; currency: string;
}) {
  const update = (id: string, patch: Partial<Line>) => onChange(lines.map((l) => (l.id === id ? { ...l, ...patch } : l)));
  const unused = PRESETS[section].filter((p) => !lines.some((l) => l.name.toLowerCase() === p.toLowerCase()));
  return (
    <>
      <ul className="budget-lines">
        {lines.map((l) => (
          <li key={l.id} className="budget-line">
            <input className="field budget-line__name" value={l.name} placeholder="What" aria-label="What"
              onChange={(e) => update(l.id, { name: e.target.value })} />
            <span className="budget-line__amount">
              <span aria-hidden="true">$</span>
              <input className="field" type="number" inputMode="decimal" min={0} step="0.01" value={l.amount || ""} placeholder="0" aria-label={`${l.name || "Line"} amount`}
                onChange={(e) => update(l.id, { amount: Math.max(0, Number(e.target.value) || 0) })} />
            </span>
            <select className="field" value={l.every} aria-label={`${l.name || "Line"}: how often`} onChange={(e) => update(l.id, { every: e.target.value as Every })}>
              {EVERY.map((ev) => <option key={ev} value={ev}>{EVERY_LABEL[ev]}</option>)}
            </select>
            {section === "savings" && (
              <span className="budget-line__goal">
                <label><span className="muted">Saved</span>
                  <input className="field" type="number" inputMode="decimal" min={0} value={l.saved ?? ""} placeholder="0" aria-label={`${l.name || "Line"}: saved so far`}
                    onChange={(e) => update(l.id, { saved: e.target.value === "" ? undefined : Math.max(0, Number(e.target.value)) })} />
                </label>
                <label><span className="muted">Goal</span>
                  <input className="field" type="number" inputMode="decimal" min={0} value={l.goal ?? ""} placeholder="none" aria-label={`${l.name || "Line"}: goal`}
                    onChange={(e) => update(l.id, { goal: e.target.value === "" ? undefined : Math.max(0, Number(e.target.value)) })} />
                </label>
              </span>
            )}
            {section === "income" && (
              <span className="budget-line__pay">
                {/* 9.5: a pay day; SirisAI reminds you that morning and Home shows it on the day. */}
                <label><span className="muted">Pay day</span>
                  <input className="field" type="date" value={l.pay_day ?? ""} aria-label={`${l.name || "Line"}: pay day`}
                    onChange={(e) => update(l.id, { pay_day: e.target.value || undefined })} />
                </label>
                {(() => { const n = nextPay(l); return n ? <span className="muted budget-line__next">Next {new Date(`${n}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}</span> : null; })()}
              </span>
            )}
            <span className="budget-line__monthly muted">{money(monthly(l), currency)}/mo</span>
            <button type="button" className="icon-link" aria-label={`Remove ${l.name || "line"}`} onClick={() => onChange(lines.filter((x) => x.id !== l.id))}>
              <Trash2 size={16} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
      <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
        <button type="button" className="button button--small" onClick={() => onChange([...lines, newLine()])}><Plus size={14} aria-hidden="true" /> Add</button>
        {unused.slice(0, 4).map((p) => (
          <button key={p} type="button" className="button button--small button--ghost" onClick={() => onChange([...lines, newLine(p, section === "income" ? "fortnightly" : "monthly")])}>{p}</button>
        ))}
      </div>
    </>
  );
}

const FOLDED = "sirisos.budget.folded";

function Tile({ label, value, tone, sub, color }: { label: string; value: string; tone?: "good" | "critical"; sub?: string; color?: string }) {
  return (
    <div className="budget-tile">
      <div className="budget-tile__label">{color && <span className="chart-swatch" style={{ background: color }} aria-hidden="true" />}{label}</div>
      <div className={`budget-tile__value${tone ? ` tone-${tone}` : ""}`}>{value}</div>
      {sub && <div className="budget-tile__sub muted">{sub}</div>}
    </div>
  );
}

export function BudgetScreen() {
  // 8.22: Expenses, Savings and Spending fold away to their total; remembered on this device.
  const [folded, setFolded] = useState<Set<string>>(() => { try { return new Set(JSON.parse(window.localStorage.getItem(FOLDED) ?? "[]") as string[]); } catch { return new Set(); } });
  const fold = (s: string) => setFolded((f) => {
    const next = new Set(f);
    if (next.has(s)) next.delete(s); else next.add(s);
    try { window.localStorage.setItem(FOLDED, JSON.stringify([...next])); } catch { /* fine */ }
    return next;
  });
  const [plan, setPlan] = useState<Plan | null>(null);
  const [history, setHistory] = useState<Budget["history"]>([]);
  const [period, setPeriod] = useState<Period>("month");
  const [status, setStatus] = useState<string>("");
  const [table, setTable] = useState(false);
  const [billNote, setBillNote] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  const dirty = useRef(false);

  useEffect(() => {
    document.title = "Budget · SirisOS";
    let live = true;
    budget.get().then((b) => {
      if (!live) return;
      const draft = budget.draft.read();
      setPlan(draft ?? { currency: b.currency, income: b.income, sections: b.sections });
      setHistory(b.history);
      if (draft) { dirty.current = true; setStatus("Unsaved changes from this device"); }
    }).catch(() => {
      if (!live) return;
      const draft = budget.draft.read();
      setPlan(draft ?? { currency: EMPTY.currency, income: [], sections: EMPTY.sections });
      setStatus("Offline: changes stay on this device until SirisOS is back");
    });
    return () => { live = false; };
  }, []);

  // Save a moment after the last change; keep a copy here if SirisOS can't be reached.
  useEffect(() => {
    if (!plan || !dirty.current) return;
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      setStatus("Saving…");
      try {
        const saved = await budget.save(plan);
        setHistory(saved.history);
        budget.draft.clear();
        dirty.current = false;
        setStatus("Saved");
      } catch (e) {
        budget.draft.write(plan);
        setStatus(e instanceof Error && /\b422\b|range|negative|how often/i.test(e.message) ? e.message : "Offline: saved on this device, sent when SirisOS is back");
      }
    }, 800);
    return () => { if (timer.current) window.clearTimeout(timer.current); };
  }, [plan]);

  const change = (next: Plan) => { dirty.current = true; setPlan(next); };
  const t = useMemo(() => (plan ? totals(plan) : EMPTY.totals), [plan]);
  if (!plan) return <div className="screen-fallback" aria-busy="true" aria-label="Loading" />;

  const c = plan.currency;
  const fmt = (v: number) => money(v, c);
  const show = (monthlyValue: number) => fmt(per(monthlyValue, period));
  const noun = PERIODS.find((p) => p.id === period)!.noun;
  const over = t.left < -0.005;
  const savingsRate = t.income > 0 ? Math.round((100 * t.savings) / t.income) : 0;

  const parts: Datum[] = [
    ...SECTIONS.map((s) => ({ key: s, label: SECTION_LABEL[s], value: per(t[s], period), color: COLOR[s] })),
    { key: "left", label: "Left over", value: Math.max(0, per(t.left, period)), color: COLOR.left },
  ];
  const biggest: Datum[] = SECTIONS.flatMap((s) => plan.sections[s].map((l) => ({ key: l.id, label: l.name || "Unnamed", value: per(monthly(l), period), color: COLOR[s] })))
    .filter((d) => d.value > 0).sort((a, b) => b.value - a.value).slice(0, 8);
  const goalRows = goals(plan.sections.savings);
  const projection = savingsProjection(plan.sections.savings, 12);
  // Goals reached in the same month share one marker, so their labels never overlap.
  const byMonth = new Map<number, string[]>();
  for (const g of goalRows) if (g.months != null && g.months > 0 && g.months <= 12) byMonth.set(g.months, [...(byMonth.get(g.months) ?? []), g.line.name]);
  const goalMarks = [...byMonth].map(([index, names]) => ({ index, label: names.length > 1 ? `${names.length} goals` : names[0] }));
  const monthLabels = projection.map((p) => {
    const d = new Date();
    d.setMonth(d.getMonth() + p.month);
    return p.month === 0 ? "Now" : d.toLocaleDateString(undefined, { month: "short" });
  });
  const shownHistory = history.length > 1 ? history : [];

  return (
    <div className="budget">
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow" role="status">{status || "Your plan, per " + period}</p>
          <h1 className="page-head__title">Budget</h1>
        </div>
        <div className="segmented" role="group" aria-label="Show per">
          {PERIODS.map((p) => (
            <button key={p.id} type="button" className={`segmented__item${period === p.id ? " segmented__item--on" : ""}`} aria-pressed={period === p.id}
              onClick={() => setPeriod(p.id)}>{p.label}</button>
          ))}
        </div>
      </header>

      <Glass as="section" className="widget budget-tiles" aria-label="Totals">
        <Tile label="Income" value={show(t.income)} sub={noun} />
        <Tile label="Expenses" value={show(t.expenses)} color={COLOR.expenses} sub={t.income ? `${Math.round((100 * t.expenses) / t.income)}% of income` : undefined} />
        <Tile label="Savings" value={show(t.savings)} color={COLOR.savings} sub={`${savingsRate}% saved`} />
        <Tile label="Spending" value={show(t.spending)} color={COLOR.spending} sub={t.income ? `${Math.round((100 * t.spending) / t.income)}% of income` : undefined} />
        <Tile label={over ? "Over by" : "Left over"} value={show(Math.abs(t.left))} tone={over ? "critical" : t.left > 0 ? "good" : undefined}
          sub={over ? "⚠ more going out than coming in" : t.income ? "✓ unallocated" : "Add your income to start"} />
      </Glass>

      {t.income + t.expenses + t.savings + t.spending > 0 && (
        <div className="budget-charts">
          <Glass as="section" className="widget" aria-label="Where it goes">
            <header className="widget__head"><Wallet aria-hidden="true" /><span>Where it goes</span></header>
            <div className="budget-donut">
              <Donut data={parts} format={fmt} center={show(over ? -t.left : Math.max(0, t.left))} centerLabel={over ? "over budget" : "left over"} />
              <Legend items={parts.map((p) => ({ label: p.label, color: p.color, value: `${fmt(p.value)}${t.income ? ` · ${Math.round((100 * p.value) / per(t.income, period))}%` : ""}` }))} />
            </div>
            <h3 className="budget-chart-title">All of your income</h3>
            <ShareBar data={parts} whole={per(t.income, period)} format={fmt} />
            {over && <p className="tone-critical" style={{ margin: 0, fontSize: 14 }}>⚠ The line marks your income: everything past it is money you don't have.</p>}
          </Glass>

          <Glass as="section" className="widget" aria-label="Against the 50/30/20 guide">
            <header className="widget__head"><span>Against the 50/30/20 guide</span></header>
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>A common rule of thumb: about half on needs, under a third on wants, a fifth or more saved. The tick is the guide.</p>
            <TargetBars format={fmt} rows={rule503020(t).map((r) => ({ ...r, color: COLOR[r.key], amount: per(t[r.key], period) }))} />
            <h3 className="budget-chart-title">Biggest lines</h3>
            {biggest.length ? (
              <>
                <Legend items={SECTIONS.map((s) => ({ label: SECTION_LABEL[s], color: COLOR[s] }))} />
                <RankBars data={biggest} format={fmt} />
              </>
            ) : <p className="muted">Nothing going out yet.</p>}
          </Glass>

          <Glass as="section" className="widget" aria-label="Savings over the next year">
            <header className="widget__head"><PiggyBank aria-hidden="true" /><span>Savings over the next year</span></header>
            {plan.sections.savings.length ? (
              <>
                <LineChart labels={monthLabels} format={(v) => money(v, c, true)} markers={goalMarks}
                  series={[{ key: "saved", label: "Put by", color: COLOR.savings, values: projection.map((p) => p.total), area: true }]} />
                {goalRows.length > 0 && (
                  <ul className="budget-goals">
                    {goalRows.map((g) => (
                      <li key={g.line.id}>
                        <div className="row" style={{ justifyContent: "space-between" }}>
                          <span>{g.line.name}</span>
                          <span className="muted">{fmt(g.line.saved ?? 0)} of {fmt(g.line.goal ?? 0)} · {g.months === 0 ? "✓ reached" : g.months == null ? "add a monthly amount" : `${g.months} month${g.months === 1 ? "" : "s"} to go`}</span>
                        </div>
                        <div className="budget-goal__track" role="progressbar" aria-valuenow={Math.round(g.progress * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={`${g.line.name} progress`}>
                          <div className="budget-goal__bar" style={{ width: `${Math.max(2, g.progress * 100)}%` }} />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            ) : <p className="muted">Add a savings line (with a goal, if there is one) to see it grow.</p>}
          </Glass>

          <Glass as="section" className="widget" aria-label="Your plan over time">
            <header className="widget__head"><span>Your plan over time</span></header>
            {shownHistory.length ? (
              <>
                <Legend items={[{ label: "Income", color: "var(--b-income)" }, ...SECTIONS.map((s) => ({ label: SECTION_LABEL[s], color: COLOR[s] }))]} />
                <LineChart labels={shownHistory.map((h) => MONTH(h.month))} format={(v) => money(v, c, true)}
                  series={[{ key: "income", label: "Income", color: "var(--b-income)", values: shownHistory.map((h) => per(h.income, period)) },
                    ...SECTIONS.map((s) => ({ key: s, label: SECTION_LABEL[s], color: COLOR[s], values: shownHistory.map((h) => per(h[s], period)) }))]} />
              </>
            ) : <p className="muted">Each month's plan is kept as you change it; from next month this shows how it's moving.</p>}
          </Glass>
        </div>
      )}

      <div className="row" style={{ justifyContent: "flex-end", margin: "6px 0" }}>
        <button type="button" className="button button--small" aria-pressed={table} onClick={() => setTable(!table)}><Table2 size={14} aria-hidden="true" /> {table ? "Hide table" : "Show as a table"}</button>
      </div>
      {table && (
        <Glass as="section" className="widget" aria-label="Budget table">
          <table className="budget-table">
            <thead><tr><th scope="col">Line</th><th scope="col">Section</th><th scope="col">Per {period}</th><th scope="col">Share of income</th></tr></thead>
            <tbody>
              {[...plan.income.map((l) => ({ l, s: "Income" })), ...SECTIONS.flatMap((s) => plan.sections[s].map((l) => ({ l, s: SECTION_LABEL[s] })))].map(({ l, s }) => (
                <tr key={l.id}><td>{l.name || "Unnamed"}</td><td>{s}</td><td>{show(monthly(l))}</td><td>{t.income ? `${((100 * monthly(l)) / t.income).toFixed(1)}%` : "–"}</td></tr>
              ))}
            </tbody>
          </table>
        </Glass>
      )}

      <div className="stack" style={{ marginTop: 12 }}>
        <Glass as="section" className="widget" aria-label="Income">
          <header className="widget__head"><span>Income</span><span className="widget__source">{show(t.income)} {noun}</span></header>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>What comes in after tax, and how often.</p>
          <LineRows lines={plan.income} section="income" currency={c} onChange={(income) => change({ ...plan, income })} />
        </Glass>
        {SECTIONS.map((s) => (
          <Glass as="section" key={s} className="widget" aria-label={SECTION_LABEL[s]}>
            <header className="widget__head">
              <span className="chart-swatch" style={{ background: COLOR[s] }} aria-hidden="true" />
              <span>{SECTION_LABEL[s]}</span>
              <span className="widget__source">{show(t[s])} {noun}</span>
              <button type="button" className="icon-link" aria-expanded={!folded.has(s)} aria-label={`${folded.has(s) ? "Show" : "Hide"} ${SECTION_LABEL[s]}`} onClick={() => fold(s)}>
                {folded.has(s) ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronUp size={16} aria-hidden="true" />}
              </button>
            </header>
            {!folded.has(s) && <>
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>{SECTION_HINT[s]}</p>
            <LineRows lines={plan.sections[s]} section={s} currency={c} onChange={(lines) => change({ ...plan, sections: { ...plan.sections, [s]: lines } })} />
            {s === "expenses" && (
              <div>
                <button type="button" className="button button--small button--ghost" onClick={async () => {
                  try {
                    const found = await budget.fromBills();
                    const fresh = found.filter((b) => !plan.sections.expenses.some((l) => l.name.toLowerCase() === b.name.toLowerCase()));
                    if (fresh.length) change({ ...plan, sections: { ...plan.sections, expenses: [...plan.sections.expenses, ...fresh.map((b) => ({ ...newLine(b.name, b.every), amount: b.amount, note: b.note }))] } });
                    setBillNote(fresh.length ? `Added ${fresh.length} from your email.` : "Nothing new from your email.");
                  } catch (e) {
                    setBillNote(e instanceof Error ? e.message : String(e));
                  }
                }}><Mail size={14} aria-hidden="true" /> Add subscriptions and bills from email</button>
                {billNote && <span className="muted" role="status" style={{ marginLeft: 8, fontSize: 13 }}>{billNote}</span>}
              </div>
            )}
            </>}
          </Glass>
        ))}
      </div>
    </div>
  );
}
