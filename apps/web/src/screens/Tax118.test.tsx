import { afterEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import type { TaxYear } from "../api/tax";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { TaxScreen } from "./Tax";

const YEAR: TaxYear = {
  fy: 2027, label: "2026-27", start: "2026-07-01", end: "2027-06-30",
  claims: [{ id: "tx_1", date: "2026-11-03", vendor: "Officeworks", description: "Monitor", category: "equipment", amount: 1249, work_pct: 80, reimbursed: false,
    has_receipt: true, doc_id: 7, source: "email", claimable: 999.2, treatment: "depreciate", treatment_note: "Over $300: claim its decline in value", work: true }],
  by_category: [{ category: "equipment", label: "Tools and equipment", count: 1, claimable: 0, depreciate: 1 }],
  wfh: { hours: 100, rate: 0.7, claimable: 70 }, car: { km: 0, rate: 0.88, cap: 5000, claimable: 0 },
  work_total: 70, total: 70, missing_receipts: [], checks: [{ level: "ok", text: "Work claims come to $70.00: $300 or less" }],
  to_sort: [{ doc_id: 8, date: "2026-10-01", vendor: "Engineers Australia", description: "Membership", amount: 512.5, category: "professional" }],
  years: [2027, 2026], email_problem: null,
  categories: [{ id: "equipment", label: "Tools and equipment", hint: "Over $300 is depreciated" }, { id: "professional", label: "Memberships and registration", hint: "Fees" }],
};

afterEach(() => clearResources());

describe("SirisOS 11.18: tax claims", () => {
  it("shows the year, and claims a receipt from email with its guess filled in", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/tax/claims": () => jsonResponse({ id: "tx_2" }), "/api/v1/tax": () => jsonResponse(YEAR) });
    const user = userEvent.setup();
    render(<MemoryRouter><TaxScreen /></MemoryRouter>);
    expect(await screen.findByLabelText("Total to claim")).toHaveTextContent("$70.00");
    expect(screen.getByText(/\$300 or less/)).toBeInTheDocument();
    expect(screen.getByText(/depreciate/, { selector: ".item__subtitle" })).toBeInTheDocument();
    const sort = screen.getByRole("region", { name: "Receipts to sort" });
    await user.click(within(sort).getByRole("button", { name: "Claim Engineers Australia" }));
    expect(within(sort).getByRole("combobox", { name: "Category" })).toHaveValue("professional");
    expect(within(sort).getByRole("textbox", { name: "Amount" })).toHaveValue("512.5");
    await user.click(within(sort).getByRole("button", { name: "Add the claim" }));
    await waitFor(() => expect(calls.some((c) => c.url === "/api/v1/tax/claims")).toBe(true));
    const body = JSON.parse(String(calls.find((c) => c.url === "/api/v1/tax/claims")!.init.body));
    expect(body).toMatchObject({ doc_id: 8, amount: 512.5, category: "professional", work_pct: 100, has_receipt: true });
  });
});
