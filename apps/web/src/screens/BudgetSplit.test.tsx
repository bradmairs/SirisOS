import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { SplitCard } from "./BudgetSplit";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const src = (id: string, name: string, every: string, total: number, income: number) => ({
  id, name, every, income, total, per_pay: every === "fortnightly" ? Math.round(total * 12 / 26) : total, left: income - total,
  percent_of_income: Math.round(total / income * 1000) / 10, share_of_budget: 50, share_of_income: 50,
  sections: { expenses: total * 0.5, savings: total * 0.3, spending: total * 0.2 }, lines: [{ id: "rent", name: "Rent", section: "expenses", monthly: 1500, whole: false, personal: false }] });
const split = (method = "income") => ({
  method, sources: [src("sam", "Sam's Pay", "monthly", 4800, 6000), src("alex", "Alex's Pay", "fortnightly", 3200, 4000)],
  left_out: [{ id: "allow", name: "Car Allowance", income: 1000 }], total: 8000, income: 10000, short: 0,
  personal: { sb: "sam" }, suggested: { sb: "sam" }, lines: [{ id: "rent", name: "Rent", section: "expenses", monthly: 3000 }, { id: "ss", name: "Sam", section: "spending", monthly: 500 }] });

describe("<SplitCard />", () => {
  it("works out the split for the chosen incomes and keeps it", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/budget/split/preview": (_u, init) => jsonResponse(split(JSON.parse(String(init?.body)).method)),
      "/api/v1/budget/split": (_u, init) => jsonResponse({ saved: init?.method === "PUT" ? { made_at: "2026-11-27T01:00:00Z", result: split() } : null,
        now: split(), stale: false, changes: [], settings: init?.method === "PUT" ? JSON.parse(String(init.body)) : { sources: [], method: "income", personal: {} } }),
    });
    const user = userEvent.setup();
    render(<SplitCard savedAt={0} />);
    const card = await screen.findByRole("region", { name: "Split between incomes" });
    expect(await within(card).findByText("$1,477")).toBeInTheDocument();  // Alex's part per fortnight
    await user.click(within(card).getByRole("button", { name: "Car Allowance" }));  // leave it out
    await user.click(within(card).getByRole("radio", { name: "Whole lines" }));
    await waitFor(() => {
      const last = calls.filter((c) => c.url.endsWith("/split/preview")).at(-1);
      expect(JSON.parse(String(last?.init.body))).toMatchObject({ sources: ["sam", "alex"], method: "lines" });
    });
    await user.click(within(card).getByRole("button", { name: "Keep this split" }));
    const put = calls.find((c) => c.init.method === "PUT");
    expect(JSON.parse(String(put?.init.body))).toMatchObject({ sources: ["sam", "alex"], method: "lines" });
  });

  it("says what changed in the budget and redoes the split", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/budget/split/preview": () => jsonResponse(split()),
      "/api/v1/budget/split": (_u, init) => jsonResponse({ saved: { made_at: "2026-11-20T01:00:00Z", result: split() }, now: split(),
        stale: init?.method !== "PUT", changes: ["Rent up from $3,000 to $3,400 a month"], settings: { sources: ["sam", "alex"], method: "income", personal: {} } }),
    });
    const user = userEvent.setup();
    render(<SplitCard savedAt={0} />);
    const note = await screen.findByText(/The budget changed since this split/);
    expect(note.closest("div")).toHaveTextContent("Rent up from $3,000 to $3,400 a month");
    await user.click(screen.getByRole("button", { name: /Redo the split/ }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "PUT")).toBe(true));
    expect(await screen.findByText(/Kept/)).toBeInTheDocument();
  });
});
