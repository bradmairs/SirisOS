import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { sunHeadsUp } from "../api/home";
import type { Actuals, Balances, Budget } from "../api/budget";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { BalancesCard, SpendingCard } from "./BudgetActuals";
import { HomeListsCard } from "./Tasks";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

const plan: Pick<Budget, "currency" | "income" | "sections"> = {
  currency: "AUD", income: [],
  sections: {
    expenses: [{ id: "rent", name: "Rent", amount: 2000, every: "monthly" }],
    savings: [{ id: "hol", name: "Holiday", amount: 500, every: "monthly", goal: 6000 }],
    spending: [{ id: "groc", name: "Groceries", amount: 200, every: "weekly" }],
  },
};

const month: Actuals = {
  month: "2026-11", through: 0.6, spent: 1137.5, currency: "AUD", has_data: true, months: ["2026-11", "2026-10"],
  lines: [{ id: "groc", name: "Groceries", section: "spending", plan: 866.67, spent: 1059.5, status: "over" }],
  over: [{ id: "groc", name: "Groceries", section: "spending", plan: 866.67, spent: 1059.5, status: "over" }],
  unsorted: [{ id: "tx1", date: "2026-11-06", description: "JB HIFI 0042 MELBOURNE", amount: -39, account: "Everyday" }],
  unsorted_count: 1, guessed: [],
};

describe("SirisOS 10.0", () => {
  it("shows spending against the plan and sorts a transaction onto a line", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/budget/actuals/tx1": () => jsonResponse({ sorted_too: 1 }),
      "/api/v1/budget/actuals": () => jsonResponse(month),
    });
    const user = userEvent.setup();
    render(<SpendingCard plan={plan} />);
    const card = await screen.findByRole("region", { name: "Spending this month" });
    expect(await within(card).findByText(/over by/)).toBeInTheDocument();
    expect(within(card).getByText(/1 line over plan/)).toBeInTheDocument();
    await user.selectOptions(within(card).getByRole("combobox", { name: "Line for JB HIFI 0042 MELBOURNE" }), "rent");
    expect(await within(card).findByText("Sorted, and 1 more from the same place.")).toBeInTheDocument();
    const put = calls.find((c) => c.url === "/api/v1/budget/actuals/tx1");
    expect(put?.init.method).toBe("PUT");
    expect(JSON.parse(String(put?.init.body))).toEqual({ line_id: "rent" });
  });

  it("explains how to start before anything is imported, and takes a CSV", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/budget/actuals/import": () => jsonResponse({ imported: 6, skipped: 0, account: "Everyday", month }),
      "/api/v1/budget/actuals": () => jsonResponse({ ...month, has_data: false, lines: [], over: [], unsorted: [], unsorted_count: 0, months: [] }),
    });
    const user = userEvent.setup();
    const { container } = render(<SpendingCard plan={plan} />);
    expect(await screen.findByText(/Export your transactions/)).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Which account the file is from" }), "Everyday");
    const input = container.querySelector("input[type=file]") as HTMLInputElement;
    await user.upload(input, new File(["03/11/2026,-85.40,WOOLWORTHS,100"], "cba.csv", { type: "text/csv" }));
    expect(await screen.findByText("Added 6 transactions.")).toBeInTheDocument();
    const post = calls.find((c) => c.url === "/api/v1/budget/actuals/import");
    expect((post?.init.body as FormData).get("account")).toBe("Everyday");
  });

  it("shows balances, a goal's progress and forecast, and net worth", async () => {
    signIn();
    const b: Balances = {
      currency: "AUD", net_worth: -1500, kinds: ["everyday", "savings", "super", "investment", "loan", "credit"],
      series: [{ month: "2026-10", net_worth: -2000 }, { month: "2026-11", net_worth: -1500 }],
      accounts: [
        { id: "a1", name: "Holiday saver", kind: "savings", line_id: "hol", balance: 2500, as_of: "2026-11-01", per_month: 496,
          goal: { line: "Holiday", target: 6000, percent: 42, eta: "Jun 2027", months: 7.1 } },
        { id: "a2", name: "Car loan", kind: "loan", balance: 4000, as_of: "2026-11-01", per_month: null },
      ],
    };
    const calls = mockFetch({ "/api/v1/budget/balances": () => jsonResponse(b) });
    const user = userEvent.setup();
    render(<BalancesCard plan={plan} />);
    const card = await screen.findByRole("region", { name: "Balances" });
    expect(await within(card).findByText(/Net worth/)).toBeInTheDocument();
    expect(within(card).getByText(/on track for Jun 2027/)).toBeInTheDocument();
    expect(within(card).queryByRole("textbox", { name: "New balance for Car loan" })).not.toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Update balances or add an account" }));
    await user.type(within(card).getByRole("textbox", { name: "New balance for Car loan" }), "3800");
    await user.click(within(card).getAllByRole("button", { name: "Update" })[1]);
    const post = calls.find((c) => c.url === "/api/v1/budget/balances" && c.init.method === "POST");
    expect(JSON.parse(String(post?.init.body))).toEqual({ account: "Car loan", balance: 3800 });
  });

  it("ticks off and adds to a Home Assistant list", async () => {
    signIn();
    const lists = { lists: [{ entity_id: "todo.shopping", name: "Shopping", items: [{ summary: "Milk", status: "needs_action" }, { summary: "Eggs", status: "completed" }] }] };
    const calls = mockFetch({
      "/api/v1/tasks/lists/todo.shopping/done": () => jsonResponse({ lists: [{ ...lists.lists[0], items: [{ summary: "Milk", status: "completed" }, { summary: "Eggs", status: "completed" }] }] }),
      "/api/v1/tasks/lists/todo.shopping/items": () => jsonResponse({ lists: [{ ...lists.lists[0], items: [...lists.lists[0].items, { summary: "Bread", status: "needs_action" }] }] }),
      "/api/v1/tasks/lists": () => jsonResponse(lists),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><HomeListsCard /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Shopping" });
    expect(within(card).getByText("1 to get")).toBeInTheDocument();
    await user.type(within(card).getByRole("textbox", { name: "Add to Shopping" }), "Bread");
    await user.click(within(card).getByRole("button", { name: "Add" }));
    expect(await within(card).findByText("Bread")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Milk: done" }));
    expect(await within(card).findByText("All done")).toBeInTheDocument();
    expect(calls.some((c) => c.url === "/api/v1/tasks/lists/todo.shopping/done")).toBe(true);
  });

  it("gives a sun and heat heads-up only when it's worth it", () => {
    expect(sunHeadsUp({ date: "2026-11-19", high_c: 24, uv_index_max: 4 })).toBeNull();
    expect(sunHeadsUp({ date: "2026-11-19", high_c: 34, uv_index_max: 11.2, sun_protection_from: "09:00", sun_protection_to: "16:00" }))
      .toBe("UV 11 (extreme) 9am–4pm: sunscreen, hat and shade. Hot: 34°. Drink water and keep out of the afternoon sun.");
  });
});
