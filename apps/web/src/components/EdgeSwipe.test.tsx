import { describe, expect, it, vi } from "vitest";
import { fireEvent, render } from "@testing-library/react";
import { useEdgeSwipe } from "./EdgeSwipe";

function Menu({ open, onOpen, onClose }: { open: boolean; onOpen: () => void; onClose: () => void }) {
  useEdgeSwipe({ open, onOpen, onClose });
  return <><div className="sidebar" /><div className="sidebar-scrim" /></>;
}

const at = (x: number, y = 300) => ({ clientX: x, clientY: y });
function swipe(from: [number, number], to: [number, number], steps = 5) {
  fireEvent.touchStart(document, { touches: [at(...from)] });
  for (let i = 1; i <= steps; i++) {
    fireEvent.touchMove(document, { touches: [at(from[0] + ((to[0] - from[0]) * i) / steps, from[1] + ((to[1] - from[1]) * i) / steps)] });
  }
  fireEvent.touchEnd(document, { changedTouches: [at(...to)] });
}

function setup(open = false) {
  const onOpen = vi.fn(), onClose = vi.fn();
  render(<Menu open={open} onOpen={onOpen} onClose={onClose} />);
  return { onOpen, onClose, menu: document.querySelector<HTMLElement>(".sidebar")! };
}

describe("useEdgeSwipe", () => {
  it("opens the menu on a swipe in from the left edge, the menu following the finger", () => {
    const { onOpen, menu } = setup();
    fireEvent.touchStart(document, { touches: [at(8)] });
    fireEvent.touchMove(document, { touches: [at(40)] });
    fireEvent.touchMove(document, { touches: [at(120)] });
    expect(menu.style.transform).toMatch(/^translateX\(-\d+px\)$/);
    fireEvent.touchEnd(document, { changedTouches: [at(200)] });
    expect(onOpen).toHaveBeenCalledOnce();
    expect(menu.style.transform).toBe("");   // back to the CSS, which settles it open
  });

  it("ignores swipes that start away from the edge, go up and down, or barely move", () => {
    const { onOpen } = setup();
    swipe([120, 300], [300, 300]);
    swipe([10, 300], [20, 500]);
    swipe([10, 300], [14, 300]);
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("springs back from a short, slow swipe", () => {
    const { onOpen } = setup();
    const now = vi.spyOn(performance, "now");
    now.mockReturnValueOnce(0);
    fireEvent.touchStart(document, { touches: [at(8)] });
    fireEvent.touchMove(document, { touches: [at(30)] });
    fireEvent.touchMove(document, { touches: [at(60)] });
    now.mockReturnValue(2000);
    fireEvent.touchEnd(document, { changedTouches: [at(60)] });
    now.mockRestore();
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("closes an open menu on a swipe to the left, from anywhere", () => {
    const { onClose, onOpen } = setup(true);
    swipe([250, 300], [40, 310]);
    expect(onClose).toHaveBeenCalledOnce();
    swipe([100, 300], [260, 300]);   // rightwards on an open menu: nothing to do
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("leaves wide screens alone, where the menu is always there", () => {
    const wide = vi.spyOn(window, "matchMedia").mockReturnValue({ matches: false } as MediaQueryList);
    const { onOpen } = setup();
    swipe([8, 300], [250, 300]);
    expect(onOpen).not.toHaveBeenCalled();
    wide.mockRestore();
  });
});
