import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { goals, monthly, per, rule503020, savingsProjection, totals, type Budget } from "../api/budget";
import { BudgetScreen } from "./Budget";

const PLAN: Budget = {
  currency: "AUD",
  income: [{ id: "i1", name: "Salary", amount: 3000, every: "fortnightly" }],
  sections: {
    expenses: [{ id: "e1", name: "Rent", amount: 2000, every: "monthly" }, { id: "e2", name: "Car rego", amount: 900, every: "yearly" }],
    savings: [{ id: "s1", name: "Holiday", amount: 500, every: "monthly", goal: 6000, saved: 1000 }],
    spending: [{ id: "p1", name: "Groceries", amount: 200, every: "weekly" }],
  },
  history: [
    { month: "2026-10", income: 6500, expenses: 2075, savings: 400, spending: 866.67, left: 3158.33 },
    { month: "2026-11", income: 6500, expenses: 2075, savings: 500, spending: 866.67, left: 3058.33 },
  ],
  totals: { income: 6500, expenses: 2075, savings: 500, spending: 866.67, left: 3058.33 },
};

afterEach(() => { vi.useRealTimers(); localStorage.clear(); });

describe("budget maths", () => {
  it("brings every line to a month, and a month to any period", () => {
    expect(monthly({ amount: 3000, every: "fortnightly" })).toBeCloseTo(6500);
    expect(monthly({ amount: 900, every: "yearly" })).toBe(75);
    const t = totals(PLAN);
    expect(t).toEqual({ income: 6500, expenses: 2075, savings: 500, spending: expect.closeTo(866.67, 1), left: expect.closeTo(3058.33, 1) });
    expect(per(t.income, "year")).toBeCloseTo(78000);
    expect(per(t.income, "week")).toBeCloseTo(1500);
  });

  it("measures against 50/30/20, works out goals and projects savings", () => {
    const rule = rule503020(totals(PLAN));
    expect(rule.map((r) => [r.label, Math.round(r.share * 100), r.target])).toEqual([["Needs", 32, 0.5], ["Wants", 13, 0.3], ["Savings", 8, 0.2]]);
    expect(goals(PLAN.sections.savings)[0]).toMatchObject({ months: 10, progress: 1000 / 6000 });
    const p = savingsProjection(PLAN.sections.savings, 12);
    expect(p[0].total).toBe(1000);
    expect(p[12].total).toBe(7000);
  });
});

describe("<BudgetScreen />", () => {
  it("shows the totals and charts, switches period, and saves edits", async () => {
    signIn();
    const saved: unknown[] = [];
    mockFetch({
      "/api/v1/budget": (_url, init) => {
        if (init.method === "PUT") { saved.push(JSON.parse(String(init.body))); return jsonResponse({ ...PLAN, ...JSON.parse(String(init.body)) }); }
        return jsonResponse(PLAN);
      },
    });
    const user = userEvent.setup();
    render(<BudgetScreen />);
    const tiles = await screen.findByRole("region", { name: "Totals" });
    expect(within(tiles).getByText("$6,500")).toBeInTheDocument();
    expect(within(tiles).getByText("$3,058")).toBeInTheDocument();
    expect(within(tiles).getByText("8% saved")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "left over: $3,058" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Against the 50/30/20 guide" })).toHaveTextContent("Needs32% of 50%");
    const savings = screen.getByRole("region", { name: "Savings over the next year" });
    expect(within(savings).getByRole("progressbar", { name: "Holiday progress" })).toBeInTheDocument();
    expect(within(savings).getByText("10 months to go", { exact: false })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Year" }));
    expect(within(tiles).getByText("$78,000")).toBeInTheDocument();

    const rent = screen.getByLabelText("Rent amount");
    await user.clear(rent);
    await user.type(rent, "2100");
    await waitFor(() => expect(saved.length).toBeGreaterThan(0), { timeout: 3000 });
    expect((saved.at(-1) as Budget).sections.expenses[0].amount).toBe(2100);
    await screen.findByText("Saved", { selector: "p.page-head__eyebrow" });
  });

  it("says when more goes out than comes in, and has a table view", async () => {
    signIn();
    const over = { ...PLAN, sections: { ...PLAN.sections, spending: [{ id: "p1", name: "Everything", amount: 5000, every: "monthly" as const }] } };
    mockFetch({ "/api/v1/budget": () => jsonResponse(over) });
    const user = userEvent.setup();
    render(<BudgetScreen />);
    expect(await screen.findByText("Over by")).toBeInTheDocument();
    expect(screen.getByText(/more going out than coming in/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show as a table" }));
    expect(within(screen.getByRole("table")).getByText("Everything")).toBeInTheDocument();
  });

  it("keeps changes on the phone when SirisOS can't be reached", async () => {
    signIn();
    mockFetch({
      "/api/v1/budget": (_url, init) => (init.method === "PUT" ? Promise.reject(new TypeError("Failed to fetch")) : jsonResponse(PLAN)),
    });
    const user = userEvent.setup();
    render(<BudgetScreen />);
    await screen.findByRole("region", { name: "Totals" });
    await user.click(screen.getAllByRole("button", { name: "Add" })[0]);
    await waitFor(() => expect(localStorage.getItem("sirisos.budget.draft")).not.toBeNull(), { timeout: 3000 });
    expect(await screen.findByText(/saved on this device/)).toBeInTheDocument();
  });

  it("folds Expenses, Savings and Spending away to their totals, and remembers it (8.22)", async () => {
    signIn();
    mockFetch({ "/api/v1/budget": () => jsonResponse(PLAN) });
    const user = userEvent.setup();
    const { unmount } = render(<BudgetScreen />);
    await screen.findByLabelText("Rent amount");
    await user.click(screen.getByRole("button", { name: "Hide Expenses" }));
    expect(screen.queryByLabelText("Rent amount")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show Expenses" })).toHaveAttribute("aria-expanded", "false");
    unmount();
    render(<BudgetScreen />);
    expect(await screen.findByRole("button", { name: "Show Expenses" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show Expenses" }));
    expect(screen.getByLabelText("Rent amount")).toBeInTheDocument();
    window.localStorage.removeItem("sirisos.budget.folded");
  });
});
