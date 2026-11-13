import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { nextPay } from "../api/budget";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { BudgetScreen } from "./Budget";
import { PayDayCard } from "./PayDayCard";

afterEach(() => { clearResources(); vi.restoreAllMocks(); window.localStorage.clear(); });

describe("SirisOS 9.5: pay day", () => {
  it("works out the next pay day as SirisOS does", () => {
    const on = new Date(2026, 10, 13);
    expect(nextPay({ pay_day: "2026-10-30", every: "fortnightly" }, on)).toBe("2026-11-13");
    expect(nextPay({ pay_day: "2026-01-31", every: "monthly" }, new Date(2026, 1, 10))).toBe("2026-02-28");
    expect(nextPay({ pay_day: undefined, every: "monthly" }, on)).toBeNull();
  });

  it("takes a pay day for a salary in Budget and saves it", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/budget": (_u, init) => jsonResponse(init?.method === "PUT" ? { ...JSON.parse(String(init.body)), history: [], totals: { income: 0, expenses: 0, savings: 0, spending: 0, left: 0 } }
        : { currency: "AUD", income: [{ id: "sal", name: "Salary", amount: 3200, every: "fortnightly" }], sections: { expenses: [], savings: [], spending: [] }, history: [],
            totals: { income: 6933, expenses: 0, savings: 0, spending: 0, left: 6933 } }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><BudgetScreen /></MemoryRouter>);
    const box = await screen.findByLabelText("Salary: pay day");
    await user.type(box, "2026-10-30");
    expect(await screen.findByText(/^Next /)).toBeInTheDocument();
    await vi.waitFor(() => {
      const put = calls.filter((c) => c.init?.method === "PUT").at(-1);
      expect(put && JSON.parse(String(put.init.body)).income[0].pay_day).toBe("2026-10-30");
    }, { timeout: 4000 });
  });

  it("shows the pay on Home on the day, and nothing on other days", async () => {
    signIn();
    mockFetch({ "/api/v1/budget/pay-days": () => jsonResponse({ currency: "AUD", pay_days: [], today: [{ id: "sal", name: "Salary", amount: 3200, every: "fortnightly", next: "2026-11-13", days: 0 }] }) });
    render(<MemoryRouter><PayDayCard /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Pay day" });
    expect(card).toHaveTextContent("$3,200");
    expect(within(card).getByText("Salary")).toBeInTheDocument();
    clearResources();
    mockFetch({ "/api/v1/budget/pay-days": () => jsonResponse({ currency: "AUD", pay_days: [], today: [] }) });
    const { container } = render(<MemoryRouter><PayDayCard /></MemoryRouter>);
    await new Promise((r) => setTimeout(r, 50));
    expect(container).toBeEmptyDOMElement();
  });
});
