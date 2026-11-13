import { Link } from "react-router-dom";
import { Banknote } from "lucide-react";
import { budget, money } from "../api/budget";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

/** Pay day on Home (9.5): on the day, what's due in from the budget's income. SirisAI also reminds you at 8am. */
export function PayDayCard() {
  const res = useResource("budget:pay-days", () => budget.payDays(), { staleMs: 30 * 60_000, refreshMs: 60 * 60_000, persist: true });
  const today = res.data?.today ?? [];
  if (!today.length) return null;
  const currency = res.data!.currency;
  const total = today.reduce((n, p) => n + p.amount, 0);
  return (
    <Glass as="section" className="widget" aria-label="Pay day">
      <header className="widget__head"><Banknote aria-hidden="true" /><span>Pay day</span><Link to="/budget" className="widget__source">Budget</Link></header>
      <p style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{money(total, currency)} due in today</p>
      <ul className="items">
        {today.map((p) => (
          <li key={p.id} className="item"><span className="item__text"><span className="item__title">{p.name}</span>
            <span className="item__subtitle">{money(p.amount, currency)} · {p.every}</span></span></li>
        ))}
      </ul>
    </Glass>
  );
}
