import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import type { Budget, CashFlow, RecurringOverview, Suggestions } from "../api/budget";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { CashFlowCard, MoneyTightCard, RecurringCard, SuggestionsCard } from "./BudgetAhead";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

const plan: Pick<Budget, "currency" | "income" | "sections"> = {
  currency: "AUD", income: [],
  sections: { expenses: [], savings: [], spending: [{ id: "groc", name: "Groceries", amount: 200, every: "weekly" }] },
};

const cf: CashFlow = {
  ready: true, currency: "AUD", start: 400, as_of: "2026-11-19", per_day: 29.6, basis: "your spending over the last two months", next_pay: "2026-11-27",
  days: [{ date: "2026-11-19", balance: 400, events: [] }, { date: "2026-11-26", balance: 135, events: [] }, { date: "2026-11-27", balance: 3105, events: [{ name: "Salary", amount: 3000 }] }],
  low: { date: "2026-11-26", balance: 135 }, end: 3105, warn: true, low_mark: 200, bills: [{ date: "2026-11-21", name: "NETFLIX.COM", amount: -25.99 }],
};

describe("SirisOS 10.1", () => {
  it("shows the lowest point before pay, on Budget and on Home", async () => {
    signIn();
    mockFetch({ "/api/v1/budget/cashflow": () => jsonResponse(cf) });
    render(<MemoryRouter><CashFlowCard /><MoneyTightCard /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Until pay day" });
    expect(within(card).getByText(/Lowest point \$135 on/)).toBeInTheDocument();
    expect(within(card).getByText("1 charge due")).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Money before pay" })).toBeInTheDocument();
  });

  it("stays off Home when money's fine, and explains what Budget needs first", async () => {
    signIn();
    mockFetch({ "/api/v1/budget/cashflow": () => jsonResponse({ ready: false, currency: "AUD", why: "Add your everyday account's balance." }) });
    render(<MemoryRouter><CashFlowCard /><MoneyTightCard /></MemoryRouter>);
    expect(await screen.findByText("Add your everyday account's balance.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Money before pay" })).not.toBeInTheDocument();
  });

  it("flags recurring charges and keeps a subscription", async () => {
    signIn();
    const item = { id: "abc123def456", name: "NETFLIX.COM MELBOURNE", key: "netflix.com melbourne", every: "monthly" as const, amount: 25.99, was: 22.99,
      per_month: 26.37, last: "2026-10-22", next: "2026-11-21", times: 3, line_id: null, line: null, subscription: true, status: null, flags: ["price_up", "not_in_budget", "check"] as const };
    const overview: RecurringOverview = { items: [{ ...item, flags: [...item.flags] }], per_month: 26.37, subscriptions_per_month: 26.37, flagged: 1, currency: "AUD" };
    const calls = mockFetch({
      "/api/v1/budget/recurring/abc123def456": () => jsonResponse({ ...overview, flagged: 0, items: [{ ...overview.items[0], status: "keep", flags: ["price_up", "not_in_budget"] }] }),
      "/api/v1/budget/recurring": () => jsonResponse(overview),
    });
    const user = userEvent.setup();
    render(<RecurringCard />);
    const card = await screen.findByRole("region", { name: "Recurring charges" });
    expect(within(card).getByText(/price went up \(was \$22.99\)/)).toBeInTheDocument();
    expect(within(card).getByText("still using it?")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Keep it" }));
    expect(await within(card).findByText(/keeping/)).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("abc123def456"))?.init.body))).toEqual({ status: "keep" });
  });

  it("suggests a new amount and applies it to the plan", async () => {
    signIn();
    const s: Suggestions = { ready: true, currency: "AUD", months: ["2026-09", "2026-10"], items: [{ line_id: "groc", name: "Groceries", section: "spending", kind: "raise",
      plan: 866.67, average: 1104.2, amount: 254, every: "weekly", monthly: 1100, where: [{ shop: "Woolworths", per_month: 1104.2 }] }] };
    mockFetch({ "/api/v1/budget/suggestions": () => jsonResponse(s) });
    const onApply = vi.fn();
    const user = userEvent.setup();
    render(<SuggestionsCard plan={plan} onApply={onApply} />);
    const card = await screen.findByRole("region", { name: "Plan suggestions" });
    expect(within(card).getByText(/Averages \$1,104 a month against \$866.67 planned/)).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Make it $254 a week" }));
    expect(onApply).toHaveBeenCalledWith("groc", 254);
    expect(screen.queryByRole("region", { name: "Plan suggestions" })).not.toBeInTheDocument();
  });
});
