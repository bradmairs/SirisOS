import { useRef, useState } from "react";
import { Landmark, Receipt, Upload } from "lucide-react";
import { Glass } from "../components/Glass";
import { LineChart } from "../components/Charts";
import { useResource } from "../api/resource";
import { actuals, KIND_LABEL, money, SECTION_LABEL, SECTIONS, type AccountKind, type Actuals, type Balances, type Budget } from "../api/budget";

/**
 * 10.0: what you actually spend (from a bank's CSV export) against the plan, and what you actually have (balances,
 * towards the savings goals, and net worth over time). Both sit on the Budget screen under the totals.
 */

type Plan = Pick<Budget, "currency" | "income" | "sections">;
const MONTH = (m: string) => new Date(`${m}-01T00:00:00`).toLocaleDateString(undefined, { month: "long", year: "numeric" });
const SHORT = (m: string) => new Date(`${m}-01T00:00:00`).toLocaleDateString(undefined, { month: "short", year: "2-digit" });
const DAY = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });

function LinePicker({ plan, value, onPick, label }: { plan: Plan; value?: string | null; onPick: (id: string | null) => void; label: string }) {
  return (
    <select className="field" aria-label={label} value={value ?? ""} onChange={(e) => onPick(e.target.value || null)}>
      <option value="">Choose a line…</option>
      {SECTIONS.map((s) => (
        <optgroup key={s} label={SECTION_LABEL[s]}>
          {plan.sections[s].map((l) => <option key={l.id} value={l.id}>{l.name || "Unnamed"}</option>)}
        </optgroup>
      ))}
      <option value="ignore">Leave out (a transfer or not spending)</option>
    </select>
  );
}

export function SpendingCard({ plan }: { plan: Plan }) {
  const [month, setMonth] = useState<string | undefined>(undefined);
  const res = useResource(`budget:actuals:${month ?? "now"}`, () => actuals.get(month), {});
  const [account, setAccount] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const a: Actuals | undefined = res.data && Array.isArray(res.data.lines) ? res.data : undefined;
  const c = plan.currency;
  const fmt = (v: number) => money(v, c);

  const upload = async (f: File) => {
    setBusy(true);
    setNote(null);
    try {
      const out = await actuals.import(f, account || "Bank");
      setNote(`Added ${out.imported} transaction${out.imported === 1 ? "" : "s"}${out.skipped ? ` (${out.skipped} already in)` : ""}.`);
      setMonth(undefined);
      res.mutate(out.month);
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (file.current) file.current.value = "";
    }
  };
  const assign = async (id: string, line: string | null) => {
    try {
      const out = await actuals.assign(id, line);
      setNote(out.sorted_too ? `Sorted, and ${out.sorted_too} more from the same place.` : "Sorted. It'll remember that shop.");
      void res.reload();
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <Glass as="section" className="widget" aria-label="Spending this month">
      <header className="widget__head"><Receipt aria-hidden="true" /><span>{a ? `Spending in ${MONTH(a.month)}` : "Spending"}</span>
      </header>
      {a?.has_data ? (
        <>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            {fmt(a.spent)} out so far{a.through < 1 ? `, ${Math.round(a.through * 100)}% of the way through the month` : ""}.
            {a.over.length ? ` ⚠ ${a.over.length} line${a.over.length === 1 ? "" : "s"} over plan.` : " ✓ Nothing over plan."}
          </p>
          {a.months.length > 1 && (
            <label className="row muted" style={{ gap: 6, fontSize: 13 }}>Month
              <select className="field" aria-label="Month" value={a.month} onChange={(e) => setMonth(e.target.value)} style={{ width: "auto", maxWidth: "100%" }}>
                {a.months.map((m) => <option key={m} value={m}>{SHORT(m)}</option>)}
              </select>
            </label>
          )}
          <ul className="budget-goals" aria-label="Each line against its plan">
            {a.lines.map((l) => {
              const share = l.plan ? l.spent / l.plan : 1;
              const tone = l.status === "over" ? "critical" : l.status === "ahead" ? "warning" : "good";
              return (
                <li key={l.id}>
                  <div className="row" style={{ justifyContent: "space-between", gap: "2px 8px", flexWrap: "wrap" }}>
                    <span style={{ whiteSpace: "nowrap" }}>{l.name || "Unnamed"}</span>
                    <span className={l.status === "over" ? "tone-critical" : "muted"} style={{ fontSize: 13 }}>
                      {fmt(l.spent)}{l.plan ? ` of ${fmt(l.plan)}` : " (not in the plan)"}
                      {l.status === "over" ? ` · ⚠ over by ${fmt(l.spent - l.plan)}` : l.status === "ahead" ? " · ahead of the month" : ""}
                    </span>
                  </div>
                  <div className="budget-goal__track" role="progressbar" aria-valuenow={Math.round(share * 100)} aria-valuemin={0} aria-valuemax={100}
                    aria-label={`${l.name}: ${Math.round(share * 100)}% of plan`}>
                    <div className={`budget-goal__bar budget-actual--${tone}`} style={{ width: `${Math.max(2, Math.min(1, share) * 100)}%` }} />
                    {a.through < 1 && l.plan > 0 && <span className="budget-actual__now" style={{ left: `${a.through * 100}%` }} aria-hidden="true" />}
                  </div>
                </li>
              );
            })}
          </ul>
          {a.unsorted_count > 0 && (
            <details className="budget-unsorted" open={a.unsorted_count <= 8}>
              <summary>{a.unsorted_count} to sort</summary>
              <ul className="stack" style={{ gap: 6, padding: 0, listStyle: "none" }}>
                {a.unsorted.slice(0, 30).map((t) => (
                  <li key={t.id} className="budget-tx">
                    <span className="budget-tx__what"><span>{t.description}</span><span className="muted">{DAY(t.date)} · {t.account}</span></span>
                    <span className="budget-tx__amount">{fmt(-t.amount)}</span>
                    <LinePicker plan={plan} label={`Line for ${t.description}`} onPick={(id) => id && void assign(t.id, id)} />
                  </li>
                ))}
              </ul>
            </details>
          )}
          {a.guessed.length > 0 && (
            <details className="budget-unsorted">
              <summary>{a.guessed.length} sorted by a guess: check them</summary>
              <ul className="stack" style={{ gap: 6, padding: 0, listStyle: "none" }}>
                {a.guessed.map((t) => (
                  <li key={t.id} className="budget-tx">
                    <span className="budget-tx__what"><span>{t.description}</span><span className="muted">{DAY(t.date)}</span></span>
                    <span className="budget-tx__amount">{fmt(-t.amount)}</span>
                    <LinePicker plan={plan} value={t.line_id} label={`Line for ${t.description}`} onPick={(id) => id && void assign(t.id, id)} />
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      ) : (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          Export your transactions from your bank's website or app as CSV and add them here: each spend goes on one of your lines, and the month
          shows against the plan. Correct one and it remembers the shop.
        </p>
      )}
      <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
        <input className="field" placeholder="Account (e.g. Everyday)" aria-label="Which account the file is from" value={account}
          onChange={(e) => setAccount(e.target.value)} style={{ flex: "1 1 140px" }} />
        <input ref={file} type="file" accept=".csv,text/csv" hidden aria-hidden="true" onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); }} />
        <button type="button" className="button button--small" disabled={busy} onClick={() => file.current?.click()}>
          <Upload size={14} aria-hidden="true" /> {busy ? "Adding…" : "Add a bank CSV"}
        </button>
      </div>
      {note && <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>{note}</p>}
    </Glass>
  );
}

export function BalancesCard({ plan }: { plan: Plan }) {
  const res = useResource("budget:balances", () => actuals.balances(), {});
  const b: Balances | undefined = res.data && Array.isArray(res.data.accounts) ? res.data : undefined;
  const [name, setName] = useState("");
  const [kind, setKind] = useState<AccountKind>("savings");
  const [amount, setAmount] = useState("");
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const c = plan.currency;
  const fmt = (v: number) => money(v, c);
  const savings = plan.sections.savings;

  const run = async (p: Promise<Balances>) => {
    setNote(null);
    try { res.mutate(await p); } catch (e) { setNote(e instanceof Error ? e.message : String(e)); }
  };
  const add = () => {
    const v = Number(amount.replace(/[$,\s]/g, ""));
    if (!name.trim() || !Number.isFinite(v)) { setNote("Give the account a name and a balance."); return; }
    void run(actuals.setBalance({ account: name.trim(), balance: v, kind })).then(() => { setName(""); setAmount(""); });
  };

  return (
    <Glass as="section" className="widget" aria-label="Balances">
      <header className="widget__head"><Landmark aria-hidden="true" /><span>Balances</span>
        {b?.net_worth != null && <span className="widget__source">Net worth {fmt(b.net_worth)}</span>}
      </header>
      {b && b.accounts.length > 0 ? (
        <>
          {b.series.length > 1 && (
            <LineChart labels={b.series.map((s) => SHORT(s.month))} format={(v) => money(v, c, true)}
              series={[{ key: "net", label: "Net worth", color: "var(--b-savings)", values: b.series.map((s) => s.net_worth), area: true }]} />
          )}
          <ul className="budget-goals" aria-label="Accounts">
            {b.accounts.map((a) => (
              <li key={a.id}>
                <div className="row" style={{ justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                  <span>{a.name} <span className="muted" style={{ fontSize: 12 }}>{KIND_LABEL[a.kind] ?? a.kind}</span></span>
                  <span>
                    {a.balance != null ? fmt(a.balance) : "–"}
                    {a.per_month != null && <span className="muted" style={{ fontSize: 12 }}> · {a.per_month >= 0 ? "+" : ""}{fmt(a.per_month)}/month</span>}
                  </span>
                </div>
                {a.goal && (
                  <>
                    <div className="budget-goal__track" role="progressbar" aria-valuenow={a.goal.percent ?? 0} aria-valuemin={0} aria-valuemax={100} aria-label={`${a.goal.line} progress`}>
                      <div className="budget-goal__bar" style={{ width: `${Math.max(2, a.goal.percent ?? 0)}%` }} />
                    </div>
                    <span className="muted" style={{ fontSize: 12 }}>
                      {a.goal.line}: {a.goal.percent ?? 0}% of {fmt(a.goal.target)}
                      {a.goal.eta === "reached" ? " · ✓ reached" : a.goal.eta ? ` · on track for ${a.goal.eta}` : " · a forecast once it's grown for a few weeks"}
                    </span>
                  </>
                )}
                {editing && <div className="row budget-account__edit" style={{ gap: 6, flexWrap: "wrap" }}>
                  <input className="field" inputMode="decimal" placeholder="New balance" aria-label={`New balance for ${a.name}`}
                    value={edits[a.id] ?? ""} onChange={(e) => setEdits({ ...edits, [a.id]: e.target.value })} style={{ flex: "1 1 90px" }} />
                  <button type="button" className="button button--small" disabled={!edits[a.id]} onClick={() => {
                    const v = Number((edits[a.id] ?? "").replace(/[$,\s]/g, ""));
                    if (Number.isFinite(v)) void run(actuals.setBalance({ account: a.name, balance: v })).then(() => setEdits({ ...edits, [a.id]: "" }));
                  }}>Update</button>
                  {(a.kind === "savings" || a.kind === "super" || a.kind === "investment") && savings.some((l) => l.goal) && (
                    <select className="field" aria-label={`Goal for ${a.name}`} value={a.line_id ?? ""}
                      onChange={(e) => void run(actuals.changeAccount(a.id, { line_id: e.target.value || null }))}>
                      <option value="">No goal</option>
                      {savings.filter((l) => l.goal).map((l) => <option key={l.id} value={l.id}>Towards {l.name}</option>)}
                    </select>
                  )}
                </div>}
              </li>
            ))}
          </ul>
          <button type="button" className="button button--small" style={{ alignSelf: "flex-start" }} aria-pressed={editing} onClick={() => setEditing(!editing)}>
            {editing ? "Done" : "Update balances or add an account"}
          </button>
        </>
      ) : (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          Add your accounts and super with what's in them now, and update them now and then (a bank CSV with a balance column does it for you).
          Tie a savings account to a goal to see real progress and when you'll get there.
        </p>
      )}
      {(editing || !b?.accounts.length) && <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
        <input className="field" placeholder="Account (e.g. Holiday saver)" aria-label="New account name" value={name} onChange={(e) => setName(e.target.value)} style={{ flex: "2 1 140px" }} />
        <select className="field" aria-label="Kind of account" value={kind} onChange={(e) => setKind(e.target.value as AccountKind)}>
          {(Object.keys(KIND_LABEL) as AccountKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
        </select>
        <input className="field" inputMode="decimal" placeholder="Balance" aria-label="Balance" value={amount} onChange={(e) => setAmount(e.target.value)} style={{ flex: "1 1 90px" }} />
        <button type="button" className="button button--small" onClick={add}>Add account</button>
      </div>}
      {note && <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>{note}</p>}
    </Glass>
  );
}
