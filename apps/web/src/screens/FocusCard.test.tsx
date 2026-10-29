import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { FocusCard } from "./FocusCard";
import { SECTION_ORDER, localPhase, sectionOrder, type HomeContext } from "../api/home";

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
    // A local start time, as calendar events have: toISOString() is UTC, whose date is still
    // yesterday before 11 am in Melbourne, so the meeting wasn't "today" in the mornings.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 22, 10, 0));   // a Thursday, 10 am
    try {
      show(ctx({ phase: "work" }), [{ summary: "Werribee design review", start: "2026-10-22T10:30:00" }]);
      expect(screen.getByText("Werribee design review")).toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "Prepare" })).toBeNull();  // meeting prep archived (4.4)
    } finally {
      vi.useRealTimers();
    }
  });

  it("offers the wrap-up in the evening, then tomorrow's top 3 once it's done", () => {
    const { unmount } = show(ctx({ phase: "evening" }));
    expect(screen.getByRole("link", { name: /Wrap up/ })).toHaveAttribute("href", "/wrapup");
    unmount();
    show(ctx({ phase: "evening", wrapped_up: true, tomorrow_top3: ["Call Dana"] }));
    expect(screen.getByRole("region", { name: "This evening" })).toHaveTextContent("Call Dana");
    expect(screen.queryByRole("link", { name: /Wrap up/ })).not.toBeInTheDocument();
  });

  it("leads a weekend with what's on and the weather outside", () => {
    show(ctx({ phase: "weekend", weather_today: { date: "2026-10-24", high_c: 22, rain_chance_percent: 70, conditions: "showers" } }));
    const card = screen.getByRole("region", { name: "Today" });
    expect(card).toHaveTextContent("Nothing planned");
    expect(card).toHaveTextContent("70% chance of rain. Take an umbrella.");
  });
});

describe("the part of the day", () => {
  it("matches the server's default schedule: work is 8:30 to 4:30 on weekdays", () => {
    expect(localPhase(new Date(2026, 9, 22, 7, 30))).toBe("morning");   // Thursday
    expect(localPhase(new Date(2026, 9, 22, 8, 29))).toBe("morning");
    expect(localPhase(new Date(2026, 9, 22, 8, 30))).toBe("work");
    expect(localPhase(new Date(2026, 9, 22, 16, 29))).toBe("work");
    expect(localPhase(new Date(2026, 9, 22, 16, 30))).toBe("evening");
    expect(localPhase(new Date(2026, 9, 24, 9))).toBe("morning");       // Saturday: no work
    expect(localPhase(new Date(2026, 9, 24, 11))).toBe("weekend");
    expect(localPhase(new Date(2026, 9, 22, 23, 30))).toBe("night");
    expect(SECTION_ORDER.work[0]).toBe("Today");
  });

  it("follows the schedule's order, and puts Home last while you're out", () => {
    expect(sectionOrder("weekend", null)).toEqual(["Home", "Today", "Now"]);
    expect(sectionOrder("work", { sections: ["Now", "Home", "Today"], home: null })).toEqual(["Now", "Home", "Today"]);
    expect(sectionOrder("weekend", { home: false })).toEqual(["Today", "Now", "Home"]);
    expect(sectionOrder("weekend", { home: true })).toEqual(["Home", "Today", "Now"]);
  });
});
