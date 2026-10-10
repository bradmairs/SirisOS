import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Glass } from "./Glass";

/** A modal sheet, rendered on <body> so it covers the page even when opened
 * from inside a glass card (whose backdrop-filter would otherwise become the
 * containing block for its fixed position). */
export function Sheet({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return createPortal(
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <Glass ref={ref} variant="strong" shape="xl" className="sheet" role="dialog" aria-modal="true" aria-label={label} tabIndex={-1}>
        <div className="sheet__grabber" />
        {children}
      </Glass>
    </div>,
    document.body,
  );
}
