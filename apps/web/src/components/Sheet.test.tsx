import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { Sheet } from "./Sheet";

describe("drag a sheet down to close it (8.5, from the top tab only since 9.0)", () => {
  it("closes when pulled down far enough, and springs back from a short pull", () => {
    vi.useFakeTimers();
    let now = 0;
    vi.spyOn(performance, "now").mockImplementation(() => now);
    const onClose = vi.fn();
    render(<Sheet label="Exercise" onClose={onClose}><p>History</p></Sheet>);
    const sheet = screen.getByRole("dialog", { name: "Exercise" });
    const tab = screen.getByTestId("sheet-handle");
    fireEvent.touchStart(tab, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(tab, { touches: [{ clientY: 140 }] });
    expect(sheet.style.transform).toBe("translateY(40px)");
    now = 500;  // a slow, short pull: not a flick
    fireEvent.touchEnd(tab);
    expect(sheet.style.transform).toBe("");  // sprang back
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.touchStart(tab, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(tab, { touches: [{ clientY: 260 }] });
    now = 900;
    fireEvent.touchEnd(tab);
    act(() => { vi.advanceTimersByTime(300); });
    expect(onClose).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("never closes from scrolling a list inside it, even at the top", () => {
    const onClose = vi.fn();
    render(<Sheet label="Pick" onClose={onClose}><ul data-testid="list"><li>Bench</li></ul></Sheet>);
    const sheet = screen.getByRole("dialog", { name: "Pick" });
    const list = screen.getByTestId("list");
    fireEvent.touchStart(list, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(list, { touches: [{ clientY: 400 }] });
    fireEvent.touchEnd(list);
    expect(sheet.style.transform).toBe("");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes on a tap on the page behind, not a drag that started in the sheet", () => {
    const onClose = vi.fn();
    render(<Sheet label="Pick" onClose={onClose}><input aria-label="Search" /></Sheet>);
    const scrim = screen.getByRole("dialog", { name: "Pick" }).parentElement!;
    fireEvent.pointerDown(screen.getByRole("textbox", { name: "Search" }));
    fireEvent.click(scrim);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.pointerDown(scrim);
    fireEvent.click(scrim);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
