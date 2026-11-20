import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { clearResources } from "../api/resource";
import type { Actuals, Budget } from "../api/budget";
import { activeTab, Dock } from "../components/Dock";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { SpendingCard } from "./BudgetActuals";

afterEach(() => { clearResources(); vi.restoreAllMocks(); localStorage.clear(); });

beforeAll(() => {
  // jsdom has no layout or PointerEvent: each tab is 70px wide, side by side; pointer events carry clientX and pointerId.
  const at = (el: HTMLElement) => (el.classList.contains("dock__item") ? Array.from(el.parentElement!.querySelectorAll(".dock__item")).indexOf(el) : -1);
  Object.defineProperty(HTMLElement.prototype, "offsetLeft", { configurable: true, get() { return Math.max(0, at(this)) * 70; } });
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", { configurable: true, get() { return at(this) >= 0 ? 70 : 0; } });
  if (!("PointerEvent" in window)) {
    class PE extends MouseEvent { pointerId: number; pointerType: string; constructor(type: string, init: PointerEventInit = {}) { super(type, init); this.pointerId = init.pointerId ?? 1; this.pointerType = init.pointerType ?? "touch"; } }
    (window as unknown as { PointerEvent: typeof PE }).PointerEvent = PE;
  }
});

function Where() { return <span data-testid="where">{useLocation().pathname}</span>; }

describe("SirisOS 10.3", () => {
  it("knows the active tab the way the links do", () => {
    const tabs = [{ to: "/", end: true }, { to: "/assistant", end: false }, { to: "/brain", end: false }];
    expect(activeTab(tabs, "/")).toBe(0);
    expect(activeTab(tabs, "/brain/inbox")).toBe(2);
    expect(activeTab(tabs, "/budget")).toBe(-1);
  });

  it("slides the bubble along the tab bar with a finger and opens the tab it's let go on", () => {
    signIn();
    mockFetch({ "/api/v1/attention": () => jsonResponse({ items: [], counts: { open: 0, urgent: 0 } }), "/api/v1": () => jsonResponse({}) });
    const { container } = render(<MemoryRouter initialEntries={["/"]}><Dock /><Routes><Route path="*" element={<Where />} /></Routes></MemoryRouter>);
    const bar = screen.getByRole("navigation", { name: "Main" });
    const lens = container.querySelector(".dock__lens") as HTMLElement;
    expect(lens.style.transform).toBe("translateX(0px)");  // under Home
    fireEvent.pointerDown(bar, { pointerId: 1, clientX: 30 });
    fireEvent.pointerMove(bar, { pointerId: 1, clientX: 60 });
    fireEvent.pointerMove(bar, { pointerId: 1, clientX: 175 });  // over the third tab (Siris)
    expect(bar.className).toContain("dock--dragging");
    expect(lens.style.transform).toBe("translateX(140px)");
    expect(container.querySelectorAll(".dock__item")[2].className).toContain("dock__item--over");
    fireEvent.pointerUp(bar, { pointerId: 1, clientX: 175 });
    expect(screen.getByTestId("where").textContent).toBe("/brain");
    expect(bar.className).not.toContain("dock--dragging");
  });

  it("still opens a tab with a plain tap", async () => {
    signIn();
    mockFetch({ "/api/v1/attention": () => jsonResponse({ items: [], counts: { open: 0, urgent: 0 } }), "/api/v1": () => jsonResponse({}) });
    render(<MemoryRouter initialEntries={["/"]}><Dock /><Routes><Route path="*" element={<Where />} /></Routes></MemoryRouter>);
    const bar = screen.getByRole("navigation", { name: "Main" });
    fireEvent.pointerDown(bar, { pointerId: 2, clientX: 100 });
    fireEvent.pointerUp(bar, { pointerId: 2, clientX: 101 });
    await userEvent.setup().click(within(bar).getByText("SirisAI"));
    expect(screen.getByTestId("where").textContent).toBe("/assistant");
  });

  const plan: Pick<Budget, "currency" | "income" | "sections"> = { currency: "AUD", income: [], sections: { expenses: [], savings: [], spending: [{ id: "groc", name: "Groceries", amount: 200, every: "weekly" }] } };
  const month: Actuals = {
    month: "2026-11", through: 0.6, spent: 1059.5, currency: "AUD", has_data: true, months: ["2026-11"], over: [], unsorted: [], unsorted_count: 0, guessed: [],
    lines: [{ id: "groc", name: "Groceries", section: "spending", plan: 866.67, spent: 1059.5, status: "over" }],
    imports: [{ id: "abcdef1234", name: "nov-2.csv", account: "Everyday", at: "2026-11-20T09:00", added: 2, transactions: 2, first: "2026-11-12", last: "2026-11-13" },
      { id: "earlier", name: "Added before files were listed", account: "Bank", at: null, added: 6, transactions: 6, first: "2026-11-03", last: "2026-11-12" }],
  };

  it("folds the lines away, lists the files and takes one out", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/budget/actuals/imports/abcdef1234": () => jsonResponse({ removed: 2, month: { ...month, imports: month.imports!.slice(1) } }),
      "/api/v1/budget/actuals": () => jsonResponse(month),
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    render(<SpendingCard plan={plan} />);
    const card = await screen.findByRole("region", { name: "Spending this month" });
    expect(within(card).getByRole("list", { name: "Each line against its plan" })).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Hide the lines" }));
    expect(within(card).queryByRole("list", { name: "Each line against its plan" })).not.toBeInTheDocument();
    expect(localStorage.getItem("sirisos.budget.spending.folded")).toBe("1");
    expect(within(card).getByText("2 files added")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Add another CSV" })).toBeInTheDocument();
    await user.click(within(card).getByText("2 files added"));
    await user.click(within(card).getByRole("button", { name: "Take out nov-2.csv" }));
    expect(await within(card).findByText("Took out 2 transactions.")).toBeInTheDocument();
    expect(calls.find((c) => c.url === "/api/v1/budget/actuals/imports/abcdef1234")?.init.method).toBe("DELETE");
    expect(within(card).getByText("1 file added")).toBeInTheDocument();
  });

  it("says when a file had nothing new", async () => {
    signIn();
    mockFetch({
      "/api/v1/budget/actuals/import": () => jsonResponse({ imported: 0, skipped: 6, account: "Everyday", import_id: null, month }),
      "/api/v1/budget/actuals": () => jsonResponse(month),
    });
    const user = userEvent.setup();
    const { container } = render(<SpendingCard plan={plan} />);
    await screen.findByRole("region", { name: "Spending this month" });
    await user.upload(container.querySelector("input[type=file]") as HTMLInputElement, new File(["x"], "nov-1.csv", { type: "text/csv" }));
    expect(await screen.findByText("Nothing new: all 6 were already in.")).toBeInTheDocument();
  });
});
