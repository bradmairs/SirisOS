import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { Sheet } from "./Sheet";

describe("drag a sheet down to close it (8.5)", () => {
  it("closes when pulled down far enough, and springs back from a short pull", () => {
    vi.useFakeTimers();
    let now = 0;
    vi.spyOn(performance, "now").mockImplementation(() => now);
    const onClose = vi.fn();
    render(<Sheet label="Exercise" onClose={onClose}><p>History</p></Sheet>);
    const sheet = screen.getByRole("dialog", { name: "Exercise" });
    fireEvent.touchStart(sheet, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(sheet, { touches: [{ clientY: 140 }] });
    expect(sheet.style.transform).toBe("translateY(40px)");
    now = 500;  // a slow, short pull: not a flick
    fireEvent.touchEnd(sheet);
    expect(sheet.style.transform).toBe("");  // sprang back
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.touchStart(sheet, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(sheet, { touches: [{ clientY: 260 }] });
    now = 900;
    fireEvent.touchEnd(sheet);
    act(() => { vi.advanceTimersByTime(300); });
    expect(onClose).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("leaves scrolling alone when the sheet isn't at its top", () => {
    const onClose = vi.fn();
    render(<Sheet label="Long" onClose={onClose}><p>Lots</p></Sheet>);
    const sheet = screen.getByRole("dialog", { name: "Long" });
    Object.defineProperty(sheet, "scrollTop", { value: 300, configurable: true });
    fireEvent.touchStart(sheet, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(sheet, { touches: [{ clientY: 400 }] });
    fireEvent.touchEnd(sheet);
    expect(sheet.style.transform).toBe("");
    expect(onClose).not.toHaveBeenCalled();
  });
});
