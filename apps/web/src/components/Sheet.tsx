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
  // A tap on the dimmed page closes it, but only one that started there (9.0): a drag that began in the sheet (scrolling
  // a list, selecting search text) and ended outside it used to close it.
  const downOnScrim = useRef(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return createPortal(
    <div className="scrim" onPointerDown={(e) => { downOnScrim.current = e.target === e.currentTarget; }}
      onClick={(e) => { if (e.target === e.currentTarget && downOnScrim.current) onClose(); downOnScrim.current = false; }}>
      <Glass ref={ref} variant="strong" shape="xl" className="sheet" role="dialog" aria-modal="true" aria-label={label} tabIndex={-1}>
        {/* Drag down from here to close (9.0): only the tab at the top, so scrolling a list inside never closes it. */}
        <div className="sheet__handle" data-testid="sheet-handle" {...drag}><div className="sheet__grabber" /></div>
        {children}
      </Glass>
    </div>,
    document.body,
  );
}


/** 8.5: drag a sheet down to close it, as on iOS. Since 9.0 it's only from the tab at the top (the handlers go on it):
 * from anywhere in a sheet scrolled to the top, scrolling a list inside it (the exercise picker's) pulled it shut. It
 * follows the finger, and closes past CLOSE_PX or on a quick flick; otherwise it springs back. */
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
      start.current = { y: e.touches[0].clientY, t: performance.now(), armed: true };
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
