import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { FocusCard } from "./FocusCard";
import { SECTION_ORDER, localPhase, type HomeContext } from "../api/home";

const ctx = (over: Partial<HomeContext>): HomeContext => ({ phase: "morning", local_time: "", home: null, wrapped_up: false, top3: [], tomorrow_top3: [], ...over });
const show = (c: HomeContext, events?: { summary: string; start: string }[]) =>
  render(<MemoryRouter><FocusCard ctx={c} events={events} /></MemoryRouter>);

describe("<FocusCard />", () => {
  it("leads the morning with last night's top 3 and the brief", () => {
    show(ctx({ top3: ["Draft the drainage report", "Call Dana"] }));
    expect(screen.getByRole("region", { name: "This morning" })).toHaveTextContent("Draft the drainage report");
    expect(screen.getByRole("link", { name: /Today's brief/ })).toHaveAttribute("href", "/brief");
  });

  it("shows the next meeting at work", () => {
    const soon = new Date(Date.now() + 30 * 60_000);
    if (soon.getDate() !== new Date().getDate()) return; // just before midnight: nothing "today" to show
    show(ctx({ phase: "work" }), [{ summary: "Werribee design review", start: soon.toISOString() }]);
    expect(screen.getByText("Werribee design review")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Prepare" })).toBeNull();  // meeting prep archived (4.4)
  });

  it("offers the wrap-up in the evening, then tomorrow's top 3 once it's done", () => {
    const { unmount } = show(ctx({ phase: "evening" }));
    expect(screen.getByRole("link", { name: /Wrap up/ })).toHaveAttribute("href", "/wrapup");
    unmount();
    show(ctx({ phase: "evening", wrapped_up: true, tomorrow_top3: ["Call Dana"] }));
    expect(screen.getByRole("region", { name: "This evening" })).toHaveTextContent("Call Dana");
    expect(screen.queryByRole("link", { name: /Wrap up/ })).not.toBeInTheDocument();
  });

  it("has nothing to lead with at the weekend", () => {
    const { container } = show(ctx({ phase: "weekend" }));
    expect(container).toBeEmptyDOMElement();
  });
});

describe("the part of the day", () => {
  it("matches the server's rules", () => {
    expect(localPhase(new Date(2026, 9, 22, 7, 30))).toBe("morning");
    expect(localPhase(new Date(2026, 9, 22, 11))).toBe("work");
    expect(localPhase(new Date(2026, 9, 24, 11))).toBe("weekend");
    expect(localPhase(new Date(2026, 9, 22, 18))).toBe("evening");
    expect(localPhase(new Date(2026, 9, 22, 23, 30))).toBe("night");
    expect(SECTION_ORDER.work[0]).toBe("Today");
    expect(SECTION_ORDER.evening[0]).toBe("Home");
  });
});
