import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

/** Long lists start with their first few items and a button to show the rest. */
export function useShowMore<T>(items: readonly T[], limit = 3) {
  const [open, setOpen] = useState(false);
  const hidden = items.length - limit;
  return {
    shown: open || hidden <= 0 ? items : items.slice(0, limit),
    toggle: hidden > 0 && (
      <button type="button" className="show-more" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {open ? <ChevronUp size={14} aria-hidden="true" /> : <ChevronDown size={14} aria-hidden="true" />}
        {/* 9.8: how many are hidden, not the total ("Show all 4" read as 4 hidden when only 1 was). */}
        {open ? "Show fewer" : `Show ${hidden} more`}
      </button>
    ),
  };
}
