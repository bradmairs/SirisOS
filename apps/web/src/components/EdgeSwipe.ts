import { useEffect, useRef } from "react";

/** How close to the left edge a swipe has to start to open the menu (px). */
export const EDGE = 28;
/** How far it has to travel, as a share of the menu's width, to count (else it springs back). */
const ENOUGH = 0.33;
/** A quick flick counts whatever the distance (px per ms). */
const FLICK = 0.45;

/**
 * Open the side menu by swiping in from the left edge, and close it by swiping it back
 * (phones and tablets, where it's a drawer). The menu follows the finger, then settles open
 * or shut. A swipe that turns out to be vertical is left to scroll the page.
 */
export function useEdgeSwipe({ open, onOpen, onClose }: { open: boolean; onOpen: () => void; onClose: () => void }) {
  const latest = useRef({ open, onOpen, onClose });
  latest.current = { open, onOpen, onClose };

  useEffect(() => {
    const narrow = () => !window.matchMedia || window.matchMedia("(max-width: 959px)").matches;
    let drag: { x: number; y: number; t: number; opening: boolean; width: number; menu: HTMLElement; scrim: HTMLElement | null; live: boolean } | null = null;

    const place = (dx: number) => {
      if (!drag) return;
      const shown = drag.opening ? Math.min(Math.max(dx, 0), drag.width) : Math.max(drag.width + Math.min(dx, 0), 0);
      drag.menu.style.transform = `translateX(${shown - drag.width - 24}px)`;
      if (drag.scrim) drag.scrim.style.opacity = String(shown / drag.width);
    };
    // Hand the menu back to its CSS, which animates it to where it settles.
    const release = (d: NonNullable<typeof drag>) => {
      d.menu.style.transition = d.menu.style.transform = "";
      if (d.scrim) d.scrim.style.transition = d.scrim.style.opacity = d.scrim.style.pointerEvents = "";
    };

    const onStart = (e: TouchEvent) => {
      if (e.touches.length !== 1 || !narrow()) return;
      const t = e.touches[0];
      const { open } = latest.current;
      if (!open && t.clientX > EDGE) return;
      const menu = document.querySelector<HTMLElement>(".sidebar");
      if (!menu) return;
      drag = { x: t.clientX, y: t.clientY, t: performance.now(), opening: !open, width: menu.offsetWidth || 272, menu,
        scrim: document.querySelector<HTMLElement>(".sidebar-scrim"), live: false };
    };
    const onMove = (e: TouchEvent) => {
      if (!drag) return;
      const t = e.touches[0];
      const dx = t.clientX - drag.x, dy = t.clientY - drag.y;
      if (!drag.live) {
        if (Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx)) { drag = null; return; }   // scrolling, not swiping
        if (Math.abs(dx) < 10) return;
        if (drag.opening ? dx < 0 : dx > 0) { drag = null; return; }
        drag.live = true;
        drag.menu.style.transition = "none";
        if (drag.scrim) { drag.scrim.style.transition = "none"; drag.scrim.style.pointerEvents = "auto"; }
      }
      if (e.cancelable) e.preventDefault();   // the menu moves, not the page
      place(dx);
    };
    const onEnd = (e: TouchEvent) => {
      if (!drag) return;
      const d = drag;
      drag = null;
      if (!d.live) return;
      const dx = (e.changedTouches[0]?.clientX ?? d.x) - d.x;
      const speed = Math.abs(dx) / Math.max(1, performance.now() - d.t);
      release(d);
      if (Math.abs(dx) >= d.width * ENOUGH || speed >= FLICK) (d.opening ? latest.current.onOpen : latest.current.onClose)();
    };

    document.addEventListener("touchstart", onStart, { passive: true });
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("touchend", onEnd);
    document.addEventListener("touchcancel", onEnd);
    return () => {
      document.removeEventListener("touchstart", onStart);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend", onEnd);
      document.removeEventListener("touchcancel", onEnd);
    };
  }, []);
}
