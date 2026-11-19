import { useState } from "react";
import { Link } from "react-router-dom";
import { CalendarClock, Lightbulb, Repeat, TrendingDown } from "lucide-react";
import { Glass } from "../components/Glass";
import { LineChart } from "../components/Charts";
import { useResource } from "../api/resource";
import { ahead, money, type Budget, type CashFlow, type Recurring, type RecurringOverview, type Suggestions } from "../api/budget";

/**
 * 10.1: looking ahead with the money, from the bank imports: the balance to the next pay day, the recurring charges
 * (subscriptions included), and what the plan could change to.
 */

type Plan = Pick<Budget, "currency" | "income" | "sections">;
const DAY = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
const SHORT = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
const EVERY: Record<string, string> = { weekly: "a week", fortnightly: "a fortnight", monthly: "a month", quarterly: "a quarter", yearly: "a year" };

export function CashFlowCard() {
  const res = useResource("budget:cashflow", () => ahead.cashflow(), { staleMs: 10 * 60_000 });
  const cf: CashFlow | undefined = res.data && typeof res.data.ready === "boolean" ? res.data : undefined;
  if (!cf) return null;
  const fmt = (v: number) => money(v, cf.currency);
  const days = Array.isArray(cf.days) ? cf.days : [];
  return (
    <Glass as="section" className="widget" aria-label="Until pay day">
      <header className="widget__head"><CalendarClock aria-hidden="true" /><span>{cf.next_pay ? "Until pay day" : "The month ahead"}</span>
        {cf.next_pay && <span className="widget__source">Pay {SHORT(cf.next_pay)}</span>}
      </header>
      {!cf.ready || !cf.low ? <p className="muted" style={{ margin: 0, fontSize: 13 }}>{cf.why}</p> : (
        <>
          <p style={{ margin: 0 }} className={cf.warn ? "tone-critical" : undefined}>
            {cf.warn ? "⚠ " : "✓ "}Lowest point {fmt(cf.low.balance)} on {DAY(cf.low.date)}
            {cf.warn ? `: under your ${fmt(cf.low_mark ?? 0)} cushion.` : "."}
          </p>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            From {fmt(cf.start ?? 0)} in your everyday account{cf.as_of ? ` (as of ${SHORT(cf.as_of)})` : ""}, about {fmt(cf.per_day ?? 0)} a day going out
            ({cf.basis}), and the charges below as they fall due.
          </p>
          {days.length > 1 && (
            <LineChart labels={days.map((d) => SHORT(d.date))} format={(v) => money(v, cf.currency, true)}
              markers={[{ index: Math.max(0, days.findIndex((d) => d.date === cf.low!.date)), label: "Lowest" }]}
              series={[{ key: "bal", label: "Balance", color: "var(--b-income)", values: days.map((d) => d.balance), area: true }]} />
          )}
          {Array.isArray(cf.bills) && cf.bills.length > 0 && (
            <details className="budget-unsorted">
              <summary>{cf.bills.length} charge{cf.bills.length === 1 ? "" : "s"} due</summary>
              <ul className="stack" style={{ gap: 4, padding: 0, listStyle: "none", fontSize: 14 }}>
                {cf.bills.map((b, i) => (
                  <li key={`${b.date}-${i}`} className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                    <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{SHORT(b.date)} · {b.name}</span>
                    <span className="budget-tx__amount">{fmt(-b.amount)}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </Glass>
  );
}

const FLAG: Record<string, string> = { price_up: "price went up", not_in_budget: "not in your budget", check: "still using it?" };

export function RecurringCard() {
  const res = useResource("budget:recurring", () => ahead.recurring(), { staleMs: 10 * 60_000 });
  const r: RecurringOverview | undefined = res.data && Array.isArray(res.data.items) ? res.data : undefined;
  const [showAll, setShowAll] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  if (!r || !r.items.length) return null;
  const fmt = (v: number) => money(v, r.currency);
  const shown = showAll ? r.items : r.items.filter((i) => i.flags.length).slice(0, 8);
  const mark = async (i: Recurring, status: Recurring["status"]) => {
    setNote(null);
    try { res.mutate(await ahead.mark(i.id, status)); } catch (e) { setNote(e instanceof Error ? e.message : String(e)); }
  };
  return (
    <Glass as="section" className="widget" aria-label="Recurring charges">
      <header className="widget__head"><Repeat aria-hidden="true" /><span>Recurring charges</span><span className="widget__source">{fmt(r.per_month)} a month</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        {r.items.length} found in your bank imports{r.subscriptions_per_month ? `, ${fmt(r.subscriptions_per_month)} a month of it subscriptions` : ""}.
        {r.flagged ? ` ${r.flagged} worth a look.` : " ✓ Nothing to check."}
      </p>
      <ul className="budget-goals" aria-label="Recurring charges found">
        {shown.map((i) => (
          <li key={i.id} className={i.status === "ignore" || i.status === "cancelling" ? "muted" : undefined}>
            <div className="row" style={{ justifyContent: "space-between", gap: "2px 8px", flexWrap: "wrap" }}>
              <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "100%" }}>{i.name}</span>
              <span>{fmt(i.amount)} {EVERY[i.every] ?? i.every}</span>
            </div>
            <span className="muted" style={{ fontSize: 12 }}>
              Next about {SHORT(i.next)}{i.line ? ` · on ${i.line}` : ""}{i.status === "cancelling" ? " · cancelling" : i.status === "keep" ? " · keeping" : ""}
            </span>
            {i.flags.length > 0 && (
              <div className="row" style={{ gap: 6, flexWrap: "wrap", marginTop: 4 }}>
                {i.flags.map((f) => (
                  <span key={f} className={`chip${f === "price_up" ? " tone-critical" : ""}`} style={{ fontSize: 12 }}>
                    {f === "price_up" ? "⚠ " : ""}{FLAG[f]}{f === "price_up" && i.was ? ` (was ${fmt(i.was)})` : ""}
                  </span>
                ))}
              </div>
            )}
            <div className="row" style={{ gap: 6, flexWrap: "wrap", marginTop: 4 }}>
              {i.status ? (
                <button type="button" className="button button--small button--ghost" onClick={() => void mark(i, null)}>Undo</button>
              ) : (
                <>
                  {i.subscription && <button type="button" className="button button--small" onClick={() => void mark(i, "keep")}>Keep it</button>}
                  <button type="button" className="button button--small button--ghost" onClick={() => void mark(i, "cancelling")}>Cancelling</button>
                  <button type="button" className="button button--small button--ghost" onClick={() => void mark(i, "ignore")}>Not a bill</button>
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
      {r.items.length > shown.length || showAll ? (
        <button type="button" className="brief-link link-button" style={{ alignSelf: "flex-start", fontSize: 13 }} onClick={() => setShowAll(!showAll)}>
          {showAll ? "Only the ones worth a look" : `Show all ${r.items.length}`}
        </button>
      ) : null}
      {note && <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>{note}</p>}
    </Glass>
  );
}

export function SuggestionsCard({ plan, onApply }: { plan: Plan; onApply: (lineId: string, amount: number) => void }) {
  const res = useResource("budget:suggestions", () => ahead.suggestions(), { staleMs: 30 * 60_000 });
  const s: Suggestions | undefined = res.data && Array.isArray(res.data.items) ? res.data : undefined;
  const [done, setDone] = useState<Set<string>>(new Set());
  if (!s || !s.ready) return null;
  const fmt = (v: number) => money(v, plan.currency);
  const items = s.items.filter((i) => !done.has(i.line_id));
  if (!items.length) return null;
  return (
    <Glass as="section" className="widget" aria-label="Plan suggestions">
      <header className="widget__head"><Lightbulb aria-hidden="true" /><span>Suggestions for your plan</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>From the last {s.months.length} full months of spending.</p>
      <ul className="budget-goals">
        {items.map((i) => (
          <li key={i.line_id}>
            <div className="row" style={{ gap: 6 }}>
              {i.kind === "lower" ? <TrendingDown size={16} aria-hidden="true" /> : null}
              <strong>{i.name}</strong>
            </div>
            <p style={{ margin: "2px 0", fontSize: 14 }}>
              {i.kind === "add"
                ? `Not in the plan, but about ${fmt(i.average)} a month goes on it.`
                : `Averages ${fmt(i.average)} a month against ${fmt(i.plan)} planned.`}{" "}
              {i.kind === "lower" ? "You could plan less and put the rest to a goal." : ""}
            </p>
            {i.where.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 12 }}>Mostly {i.where.map((w) => `${w.shop} ${fmt(w.per_month)}`).join(", ")} a month.</p>}
            <div className="row" style={{ gap: 6, marginTop: 4, flexWrap: "wrap" }}>
              <button type="button" className="button button--small" onClick={() => { onApply(i.line_id, i.amount); setDone(new Set([...done, i.line_id])); }}>
                Make it {fmt(i.amount)} {EVERY[i.every] ?? i.every}
              </button>
              <button type="button" className="button button--small button--ghost" onClick={() => setDone(new Set([...done, i.line_id]))}>Not now</button>
            </div>
          </li>
        ))}
      </ul>
    </Glass>
  );
}

/** Home (10.1): only when money looks like getting tight before pay. */
export function MoneyTightCard() {
  const res = useResource("budget:cashflow", () => ahead.cashflow(), { staleMs: 30 * 60_000, persist: true });
  const cf = res.data;
  if (!cf || !cf.ready || !cf.warn || !cf.low) return null;
  return (
    <Glass as="section" className="widget" aria-label="Money before pay">
      <header className="widget__head"><CalendarClock aria-hidden="true" /><span>Money before pay</span><Link to="/budget" className="widget__source">Budget</Link></header>
      <p style={{ margin: 0 }} className="tone-critical">⚠ Down to about {money(cf.low.balance, cf.currency)} on {DAY(cf.low.date)}{cf.next_pay ? `, before pay on ${DAY(cf.next_pay)}` : ""}.</p>
    </Glass>
  );
}
