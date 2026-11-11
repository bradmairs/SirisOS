import { useEffect, useRef, type ReactNode } from "react";
import type React from "react";
import { createPortal } from "react-dom";
import { Glass } from "./Glass";

/** A modal sheet, rendered on <body> so it covers the page even when opened
 * from inside a glass card (whose backdrop-filter would otherwise become the
 * containing block for its fixed position). */
export function Sheet({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLElement>(null);
  const drag = useSwipeDown(ref, onClose);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return createPortal(
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <Glass ref={ref} variant="strong" shape="xl" className="sheet" role="dialog" aria-modal="true" aria-label={label} tabIndex={-1} {...drag}>
        <div className="sheet__grabber" />
        {children}
      </Glass>
    </div>,
    document.body,
  );
}


/** 8.5: drag a sheet down to close it, as on iOS. It follows the finger once you pull down from the top of the
 * sheet (scrolled to the top), and closes past CLOSE_PX or on a quick flick; otherwise it springs back. */
const CLOSE_PX = 110;
const FLICK = 0.6;  // px per ms
export function useSwipeDown(ref: React.RefObject<HTMLElement | null>, onClose: () => void) {
  const start = useRef<{ y: number; t: number; armed: boolean } | null>(null);
  const dy = useRef(0);
  const set = (y: number, animate: boolean) => {
    const el = ref.current;
    if (!el) return;
    el.style.transition = animate ? "transform 0.25s ease" : "none";
    el.style.transform = y > 0 ? `translateY(${y}px)` : "";
  };
  return {
    onTouchStart: (e: React.TouchEvent) => {
      const el = ref.current;
      start.current = { y: e.touches[0].clientY, t: performance.now(), armed: !el || el.scrollTop <= 0 };
      dy.current = 0;
    },
    onTouchMove: (e: React.TouchEvent) => {
      const s = start.current;
      if (!s?.armed) return;
      const d = e.touches[0].clientY - s.y;
      if (d <= 0) { if (dy.current) set(0, false); dy.current = 0; return; }  // scrolling up: let the sheet scroll
      dy.current = d;
      set(d, false);
    },
    onTouchEnd: () => {
      const s = start.current;
      start.current = null;
      if (!s?.armed || dy.current <= 0) return;
      const speed = dy.current / Math.max(1, performance.now() - s.t);
      if (dy.current > CLOSE_PX || (speed > FLICK && dy.current > 30)) {
        set(window.innerHeight, true);
        window.setTimeout(onClose, 180);
      } else {
        set(0, true);
      }
      dy.current = 0;
    },
  };
}
