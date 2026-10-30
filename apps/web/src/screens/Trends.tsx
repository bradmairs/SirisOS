import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Award, BookOpen, Footprints, Inbox, ListChecks, Table2, Zap } from "lucide-react";
import { useResource } from "../api/resource";
import { trends, type TrendMonth, type Trends } from "../api/trends";
import { Glass } from "../components/Glass";
import { GoalsCard } from "./Goals";

const monthName = (m: string, style: "short" | "long" = "short") => new Date(`${m}-01T00:00:00`).toLocaleDateString(undefined, { month: style, ...(style === "long" ? { year: "numeric" } : {}) });
const fmt = (v: number, unit = "") => `${Number.isInteger(v) ? v : v.toFixed(1)}${unit}`;

type Metric = { key: keyof TrendMonth; title: string; unit: string; Icon: typeof Award; total: "sum" | "avg"; note?: string };

/** This year's goals (4.4), then the last 12 months, one small chart per measure (4.1). */
export function TrendsScreen() {
  const { data, error, loading } = useResource("trends", () => trends.get(), { staleMs: 10 * 60_000, persist: true });
  const [table, setTable] = useState(false);
  useEffect(() => {
    document.title = "Year · SirisOS";
  }, []);
  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{data ? `${monthName(data.months[0].month, "long")} – ${monthName(data.months[11].month, "long")}` : "The last 12 months"}</p>
          <h1 className="page-head__title">Your year</h1>
        </div>
        <button type="button" className="button button--small" aria-pressed={table} onClick={() => setTable((t) => !t)}>
          <Table2 size={14} aria-hidden="true" /> {table ? "Charts" : "Table"}
        </button>
      </header>
      {error && !data && <div className="error-banner" role="alert">{error}</div>}
      {!data && loading && <div className="skeleton" style={{ height: 300, marginTop: 16 }} />}
      <div style={{ marginTop: 16 }}><GoalsCard thisYear={Number((data?.today ?? new Date().toISOString()).slice(0, 4))} /></div>
      {data && (table ? <TrendsTable data={data} /> : <TrendsCharts data={data} />)}
    </>
  );
}

function metrics(data: Trends): Metric[] {
  return [
    { key: "cpd_hours", title: "CPD hours", unit: " h", Icon: Award, total: "sum", note: `${fmt(data.cpd.window_total)} of ${data.cpd.required} in your three-year window` },
    { key: "running_km", title: "Running", unit: " km", Icon: Footprints, total: "sum", note: data.available.health ? undefined : "SirisAI didn't answer" },
    { key: "tasks_done", title: "Tasks done", unit: "", Icon: ListChecks, total: "sum" },
    { key: "journal_days", title: "Journal days", unit: "", Icon: BookOpen, total: "sum", note: `${data.journal.current}-day streak now · longest ${data.journal.longest}` },
    { key: "inbox", title: "Inbox at its busiest", unit: "", Icon: Inbox, total: "avg", note: "Average of each day's most" },
    ...(data.available.energy ? [{ key: "energy_kwh" as const, title: "Power used", unit: " kWh", Icon: Zap, total: "sum" as const, note: "From Home Assistant, counted by SirisOS" }] : []),
  ];
}

function TrendsCharts({ data }: { data: Trends }) {
  return (
    <div className="trends" style={{ marginTop: 16 }}>
      {metrics(data).map((m) => <TrendCard key={m.key} metric={m} months={data.months} />)}
      {data.since.log && (
        <p className="muted" style={{ margin: "4px 6px 0", fontSize: 13, gridColumn: "1 / -1" }}>
          Tasks, the Inbox and journal days are logged from {new Date(`${data.since.log}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "long" })}; before that SirisOS has only the last 60 days. <Link to="/career?view=cpd">CPD</Link>
        </p>
      )}
    </div>
  );
}

function TrendCard({ metric: m, months }: { metric: Metric; months: TrendMonth[] }) {
  const values = months.map((r) => (r[m.key] as number | null) ?? null);
  const known = values.filter((v): v is number => v !== null);
  const peak = Math.max(1, ...known);
  const total = m.total === "sum" ? known.reduce((a, b) => a + b, 0) : known.length ? known.reduce((a, b) => a + b, 0) / known.length : null;
  const [focus, setFocus] = useState<number | null>(null);
  const shown = focus ?? months.length - 1;
  return (
    <Glass as="section" className="widget trend" style={{ minHeight: 0 }} aria-label={m.title}>
      <header className="widget__head"><m.Icon aria-hidden="true" /><span>{m.title}</span></header>
      <div className="trend__headline">
        <span className="trend__value">{total === null ? "–" : fmt(Math.round(total * 10) / 10, m.unit)}</span>
        <span className="muted">{m.total === "sum" ? "in 12 months" : "on average"}</span>
      </div>
      <div className="trend__bars" role="list" onMouseLeave={() => setFocus(null)}>
        {values.map((v, i) => (
          <span key={months[i].month} role="listitem" tabIndex={0} className={`trend__slot ${i === shown ? "trend__slot--on" : ""}`}
            aria-label={`${monthName(months[i].month, "long")}: ${v === null ? "no data" : fmt(v, m.unit)}`}
            onMouseEnter={() => setFocus(i)} onFocus={() => setFocus(i)} onBlur={() => setFocus(null)}>
            <span className={`trend__bar ${v === null ? "trend__bar--none" : ""}`} style={{ height: v ? `${Math.max(4, (v / peak) * 100)}%` : "2px" }} />
          </span>
        ))}
      </div>
      <div className="trend__axis muted"><span>{monthName(months[0].month)}</span><span>{monthName(months[months.length - 1].month)}</span></div>
      <p className="trend__readout" aria-live="polite">
        <b>{monthName(months[shown].month, "long")}{shown === months.length - 1 ? " so far" : ""}:</b> {values[shown] === null ? "no data" : fmt(values[shown]!, m.unit)}
      </p>
      {m.note && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{m.note}</p>}
    </Glass>
  );
}

function TrendsTable({ data }: { data: Trends }) {
  const cols = metrics(data);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0, marginTop: 16, overflowX: "auto" }} aria-label="The year as a table">
      <table className="trend-table">
        <thead><tr><th scope="col">Month</th>{cols.map((c) => <th key={c.key} scope="col">{c.title}</th>)}</tr></thead>
        <tbody>
          {[...data.months].reverse().map((r) => (
            <tr key={r.month}>
              <th scope="row">{monthName(r.month, "long")}</th>
              {cols.map((c) => { const v = r[c.key] as number | null; return <td key={c.key}>{v === null ? "–" : fmt(v, c.unit)}</td>; })}
            </tr>
          ))}
        </tbody>
      </table>
    </Glass>
  );
}
