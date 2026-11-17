import { describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { useEffect, useState } from "react";
import { Sheet } from "./Sheet";

/** 9.61: a parent that re-renders every second (the workout's clock) mustn't pull focus out of the search box. */
function Ticking({ onClose }: { onClose: () => void }) {
  const [, tick] = useState(0);
  useEffect(() => { const t = window.setInterval(() => tick((n) => n + 1), 1000); return () => window.clearInterval(t); }, []);
  return (
    <Sheet label="Pick an exercise" onClose={() => onClose()}>
      <input aria-label="Search exercises" />
    </Sheet>
  );
}

describe("Sheet focus (9.61)", () => {
  it("keeps the search box focused while the page behind it ticks", () => {
    vi.useFakeTimers();
    const closed = vi.fn();
    render(<Ticking onClose={closed} />);
    const search = screen.getByRole("textbox", { name: "Search exercises" });
    search.focus();
    act(() => { vi.advanceTimersByTime(5000); });
    expect(document.activeElement).toBe(search);
    expect(closed).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("still closes on Escape with the latest handler", () => {
    const closed = vi.fn();
    render(<Ticking onClose={closed} />);
    act(() => { window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })); });
    expect(closed).toHaveBeenCalledTimes(1);
  });
});
