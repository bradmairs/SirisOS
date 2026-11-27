import { api } from "./client";

/** The budget (7.7): income, then where it goes, in three sections. Every
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
  /** 9.5, income only: a day it's paid (any one); the next follows from how often. */
  pay_day?: string;
}

export interface PayDay { id: string; name: string; amount: number; every: Every; next: string; days: number }

export interface Totals { income: number; expenses: number; savings: number; spending: number; left: number }

export interface Budget {
  currency: string;
  income: Line[];
  sections: Record<Section, Line[]>;
  history: ({ month: string } & Totals)[];
  totals: Totals;
  updated_at?: string;
  pay_days?: PayDay[];
}

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
/** The next pay day on or after `today` (9.5), as SirisOS works it out: monthly pay on the 31st falls on the last day of shorter months. */
export function nextPay(line: Pick<Line, "pay_day" | "every">, today = new Date()): string | null {
  if (!line.pay_day || !/^\d{4}-\d{2}-\d{2}$/.test(line.pay_day)) return null;
  const [y, m, d] = line.pay_day.split("-").map(Number);
  const start = new Date(y, m - 1, d);
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  if (start >= t) return iso(start);
  if (line.every === "weekly" || line.every === "fortnightly") {
    const step = line.every === "weekly" ? 7 : 14;
    const days = Math.round((t.getTime() - start.getTime()) / 86_400_000);
    const out = new Date(start); out.setDate(start.getDate() + Math.ceil(days / step) * step);
    return iso(out);
  }
  const months = line.every === "quarterly" ? 3 : line.every === "yearly" ? 12 : 1;
  let k = Math.floor(((t.getFullYear() - y) * 12 + t.getMonth() - (m - 1)) / months);
  for (let i = 0; i < 3; i++, k++) {
    const yy = y + Math.floor((m - 1 + k * months) / 12), mm = (m - 1 + k * months) % 12;
    const out = new Date(yy, mm, Math.min(d, new Date(yy, mm + 1, 0).getDate()));
    if (out >= t) return iso(out);
  }
  return null;
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

/** 11.12: the budget split between income sources. */
export type SplitMethod = "income" | "equal" | "lines";
export interface SplitSource {
  id: string; name: string; every: Every; income: number; total: number; per_pay: number; left: number;
  percent_of_income: number | null; share_of_budget: number; share_of_income: number;
  sections: Record<"expenses" | "savings" | "spending", number>;
  lines: { id: string; name: string; section: string; monthly: number; whole: boolean; personal: boolean }[];
}
export interface Split {
  method: SplitMethod; sources: SplitSource[]; left_out: { id: string; name: string; income: number }[]; total: number; income: number; short: number;
  personal: Record<string, string>; suggested: Record<string, string>; lines: { id: string; name: string; section: string; monthly: number }[];
}
export interface SplitChoices { sources: string[]; method: SplitMethod; personal: Record<string, string> }
export interface SplitState { saved: { made_at: string; result: Split } | null; now: Split | null; stale: boolean; changes: string[]; settings: SplitChoices; error?: string | null }

export const budget = {
  get: () => api<Budget>(B),
  save: (b: Pick<Budget, "currency" | "income" | "sections">) =>
    api<Budget>(B, { method: "PUT", body: JSON.stringify({ currency: b.currency, income: b.income, sections: b.sections }) }),
  split: () => api<SplitState>(`${B}/split`),
  previewSplit: (c: SplitChoices) => api<Split>(`${B}/split/preview`, { method: "POST", body: JSON.stringify(c) }),
  keepSplit: (c: SplitChoices) => api<SplitState>(`${B}/split`, { method: "PUT", body: JSON.stringify(c) }),
  fromBills: () => api<Pick<Line, "name" | "amount" | "every" | "note">[]>(`${B}/from-bills`),
  /** 9.5: each income line's next pay day; `today` is what's paid today, for Home. */
  payDays: () => api<{ currency: string; pay_days: PayDay[]; today: PayDay[] }>(`${B}/pay-days`),
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

/** 9.9: what was actually spent, from a bank's CSV export, against each line's plan. */
export interface Tx { id: string; date: string; description: string; amount: number; account: string; line_id?: string | null; ignored?: boolean; guessed?: boolean }
export interface ActualLine { id: string; name: string; section: Section; plan: number; spent: number; status: "ok" | "ahead" | "over" }
export interface Actuals {
  month: string; through: number; lines: ActualLine[]; over: ActualLine[]; spent: number;
  unsorted: Tx[]; unsorted_count: number; guessed: Tx[]; months: string[]; currency: string; has_data: boolean;
  /** 10.3: the files added, newest first ("earlier": from before files were listed), and duplicates taken out. */
  imports?: CsvFile[]; dupes_removed?: number;
}
export interface CsvFile { id: string; name: string; account: string; at: string | null; added: number; transactions: number; first: string; last: string }
/** 9.9: accounts and balances, towards the savings goals, and net worth over time. */
export type AccountKind = "everyday" | "savings" | "super" | "investment" | "loan" | "credit";
export interface Account {
  id: string; name: string; kind: AccountKind; line_id?: string | null; balance: number | null; as_of: string | null; per_month: number | null;
  goal?: { line: string; target: number; percent: number | null; eta?: string; months?: number };
}
export interface Balances { accounts: Account[]; net_worth: number | null; series: { month: string; net_worth: number }[]; kinds: AccountKind[]; currency: string }
export const KIND_LABEL: Record<AccountKind, string> = { everyday: "Everyday", savings: "Savings", super: "Super", investment: "Investments", loan: "Loan", credit: "Credit card" };

export const actuals = {
  get: (month?: string) => api<Actuals>(`${B}/actuals${month ? `?month=${encodeURIComponent(month)}` : ""}`),
  import: (file: File, account: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("account", account);
    return api<{ imported: number; skipped: number; account: string; month: Actuals }>(`${B}/actuals/import`, { method: "POST", body: form });
  },
  removeFile: (id: string) => api<{ removed: number; month: Actuals }>(`${B}/actuals/imports/${encodeURIComponent(id)}`, { method: "DELETE" }),
  assign: (id: string, lineId: string | null) => api<{ sorted_too: number }>(`${B}/actuals/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify({ line_id: lineId }) }),
  balances: () => api<Balances>(`${B}/balances`),
  setBalance: (b: { account: string; balance: number; kind?: AccountKind; line_id?: string | null }) =>
    api<Balances>(`${B}/balances`, { method: "POST", body: JSON.stringify(b) }),
  changeAccount: (id: string, c: { name?: string; kind?: AccountKind; line_id?: string | null }) =>
    api<Balances>(`${B}/accounts/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(c) }),
  removeAccount: (id: string) => api<Balances>(`${B}/accounts/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

/** 10.1: the everyday balance day by day to after the next pay day. */
export interface CashFlow {
  ready: boolean; currency: string; why?: string;
  start?: number; as_of?: string; per_day?: number; basis?: string; next_pay?: string | null;
  days?: { date: string; balance: number; events: { name: string; amount: number }[] }[];
  low?: { date: string; balance: number }; end?: number; warn?: boolean; low_mark?: number;
  bills?: { date: string; name: string; amount: number }[];
}
export type RecurringFlag = "price_up" | "not_in_budget" | "check";
export interface Recurring {
  id: string; name: string; key: string; every: Every; amount: number; was: number | null; per_month: number; last: string; next: string;
  times: number; line_id: string | null; line: string | null; subscription: boolean; status: "keep" | "cancelling" | "ignore" | null; flags: RecurringFlag[];
}
export interface RecurringOverview { items: Recurring[]; per_month: number; subscriptions_per_month: number; flagged: number; currency: string }
export interface Suggestion {
  line_id: string; name: string; section: Section; kind: "raise" | "lower" | "add"; plan: number; average: number;
  amount: number; every: Every; monthly: number; where: { shop: string; per_month: number }[];
}
export interface Suggestions { ready: boolean; why?: string; months: string[]; items: Suggestion[]; currency: string }

export const ahead = {
  cashflow: () => api<CashFlow>(`${B}/cashflow`),
  recurring: () => api<RecurringOverview>(`${B}/recurring`),
  mark: (id: string, status: Recurring["status"]) => api<RecurringOverview>(`${B}/recurring/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify({ status }) }),
  suggestions: () => api<Suggestions>(`${B}/suggestions`),
};
