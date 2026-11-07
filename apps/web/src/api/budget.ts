import { api } from "./client";

/** The budget (7.6): income, then where it goes, in three sections. Every
 * line has an amount and how often, so the whole plan can be shown per week,
 * fortnight, month or year. */
export type Every = "weekly" | "fortnightly" | "monthly" | "quarterly" | "yearly";
export type Section = "expenses" | "savings" | "spending";
export type Period = "week" | "fortnight" | "month" | "year";

export interface Line {
  id: string;
  name: string;
  amount: number;
  every: Every;
  /** Savings only: what you're saving towards, and what's put by already. */
  goal?: number;
  saved?: number;
  note?: string;
}

export interface Totals { income: number; expenses: number; savings: number; spending: number; left: number }

export interface Budget {
  currency: string;
  income: Line[];
  sections: Record<Section, Line[]>;
  history: ({ month: string } & Totals)[];
  totals: Totals;
  updated_at?: string;
}

export const SECTIONS: Section[] = ["expenses", "savings", "spending"];
export const SECTION_LABEL: Record<Section, string> = { expenses: "Expenses", savings: "Savings", spending: "Spending" };
export const SECTION_HINT: Record<Section, string> = {
  expenses: "Bills and fixed costs: rent or mortgage, power, insurance, phone, subscriptions.",
  savings: "Money put away, with a goal if there is one.",
  spending: "The day-to-day: groceries, eating out, fun, clothes.",
};
export const PRESETS: Record<Section | "income", string[]> = {
  income: ["Salary", "Side work", "Interest"],
  expenses: ["Rent or mortgage", "Power and gas", "Internet", "Phone", "Insurance", "Car rego", "Subscriptions"],
  savings: ["Emergency fund", "Holiday", "House deposit", "Super top-up"],
  spending: ["Groceries", "Eating out", "Fuel", "Fun", "Clothes", "Gifts"],
};
export const EVERY: Every[] = ["weekly", "fortnightly", "monthly", "quarterly", "yearly"];
export const PER_MONTH: Record<Every, number> = { weekly: 52 / 12, fortnightly: 26 / 12, monthly: 1, quarterly: 1 / 3, yearly: 1 / 12 };
export const MONTHS_PER: Record<Period, number> = { week: 12 / 52, fortnight: 12 / 26, month: 1, year: 12 };

export const monthly = (l: Pick<Line, "amount" | "every">) => (Number(l.amount) || 0) * PER_MONTH[l.every];

export function totals(b: Pick<Budget, "income" | "sections">): Totals {
  const sum = (lines: Line[]) => lines.reduce((t, l) => t + monthly(l), 0);
  const t = { income: sum(b.income), expenses: sum(b.sections.expenses), savings: sum(b.sections.savings), spending: sum(b.sections.spending) };
  return { ...t, left: t.income - t.expenses - t.savings - t.spending };
}

/** A monthly figure shown per `period`. */
export const per = (monthlyValue: number, period: Period) => monthlyValue * MONTHS_PER[period];

export function money(value: number, currency = "AUD", compact = false): string {
  const v = Math.round(value * 100) / 100;
  if (compact && Math.abs(v) >= 1000) {
    const k = (Math.abs(v) / 1000).toFixed(Math.abs(v) >= 100_000 ? 0 : 1).replace(/[.]0$/, "");
    return `${v < 0 ? "-" : ""}$${k}k`;
  }
  return new Intl.NumberFormat("en-AU", { style: "currency", currency, maximumFractionDigits: Math.abs(v) >= 1000 ? 0 : 2, minimumFractionDigits: 0 }).format(v);
}

/** Needs, wants and savings against the 50/30/20 guide, as shares of income. */
export function rule503020(t: Totals): { key: Section; label: string; share: number; target: number }[] {
  const income = t.income || 1;
  return [
    { key: "expenses", label: "Needs", share: t.expenses / income, target: 0.5 },
    { key: "spending", label: "Wants", share: t.spending / income, target: 0.3 },
    { key: "savings", label: "Savings", share: t.savings / income, target: 0.2 },
  ];
}

/** Each savings goal: how long until it's reached at its current rate. */
export function goals(lines: Line[]): { line: Line; months: number | null; progress: number }[] {
  return lines.filter((l) => l.goal && l.goal > 0).map((l) => {
    const saved = l.saved ?? 0;
    const rate = monthly(l);
    const left = Math.max(0, (l.goal ?? 0) - saved);
    return { line: l, progress: Math.min(1, saved / (l.goal ?? 1)), months: left === 0 ? 0 : rate > 0 ? Math.ceil(left / rate) : null };
  });
}

/** Total put by over the next `months`, month by month (what's saved now, plus each month's savings). */
export function savingsProjection(lines: Line[], months = 12): { month: number; total: number }[] {
  const start = lines.reduce((t, l) => t + (l.saved ?? 0), 0);
  const rate = lines.reduce((t, l) => t + monthly(l), 0);
  return Array.from({ length: months + 1 }, (_, m) => ({ month: m, total: start + rate * m }));
}

export const newLine = (name = "", every: Every = "monthly"): Line => ({
  id: Math.random().toString(36).slice(2, 12), name, amount: 0, every,
});

export const EMPTY: Budget = {
  currency: "AUD", income: [], sections: { expenses: [], savings: [], spending: [] }, history: [],
  totals: { income: 0, expenses: 0, savings: 0, spending: 0, left: 0 },
};

const B = "/api/v1/budget";
const DRAFT = "sirisos.budget.draft";

export const budget = {
  get: () => api<Budget>(B),
  save: (b: Pick<Budget, "currency" | "income" | "sections">) =>
    api<Budget>(B, { method: "PUT", body: JSON.stringify({ currency: b.currency, income: b.income, sections: b.sections }) }),
  fromBills: () => api<Pick<Line, "name" | "amount" | "every" | "note">[]>(`${B}/from-bills`),
  /** Unsaved changes kept on this device when SirisOS can't be reached. */
  draft: {
    read(): Pick<Budget, "currency" | "income" | "sections"> | null {
      try { const raw = localStorage.getItem(DRAFT); return raw ? JSON.parse(raw) : null; } catch { return null; }
    },
    write(b: Pick<Budget, "currency" | "income" | "sections">) {
      try { localStorage.setItem(DRAFT, JSON.stringify({ currency: b.currency, income: b.income, sections: b.sections })); } catch { /* full or blocked */ }
    },
    clear() { try { localStorage.removeItem(DRAFT); } catch { /* blocked */ } },
  },
};
