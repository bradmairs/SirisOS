import { afterEach, describe, expect, it, vi } from "vitest";
import { installViewportFix, settle } from "./viewport";

describe("fixed bars stay put on iPhone (9.62)", () => {
  let undo: (() => void) | null = null;
  afterEach(() => { undo?.(); undo = null; vi.useRealTimers(); vi.restoreAllMocks(); document.body.innerHTML = ""; });

  it("makes a real one-pixel scroll and back, which iOS doesn't ignore", () => {
    const to = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    Object.defineProperty(window, "scrollY", { value: 300, configurable: true });
    settle();
    expect(to.mock.calls).toEqual([[0, 299], [0, 300]]);
    Object.defineProperty(window, "scrollY", { value: 0, configurable: true });
    to.mockClear();
    settle();
    expect(to.mock.calls).toEqual([[0, 1], [0, 0]]);
  });

  it("runs after the keyboard closes and on coming back to the app, never while typing", () => {
    vi.useFakeTimers();
    const to = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    undo = installViewportFix();
    const input = document.createElement("input");
    const other = document.createElement("input");
    document.body.append(input, other);
    input.focus();
    other.focus();   // moving between fields: the keyboard stays up
    vi.advanceTimersByTime(400);
    expect(to).not.toHaveBeenCalled();
    other.blur();
    vi.advanceTimersByTime(400);
    expect(to).toHaveBeenCalled();
    to.mockClear();
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
    vi.advanceTimersByTime(400);
    expect(to).toHaveBeenCalled();
  });
});
