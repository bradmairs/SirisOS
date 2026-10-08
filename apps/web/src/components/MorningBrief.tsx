import { useCallback, useEffect, useRef, useState } from "react";
import { brief } from "../api/brief";

const CHECK_MS = 5 * 60_000;

/**
 * Whether the morning brief should be open. Asks the API on load, whenever
 * the app comes back to the foreground, and every few minutes (so a tab left
 * open overnight opens it the next morning). Closing it dismisses it for the
 * day on the server, so it stays closed on every device.
 */
export function useMorningBrief(enabled = true) {
  const [open, setOpen] = useState(false);
  const day = useRef<string | null>(null);
  const closedOn = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const check = () => {
      if (document.visibilityState !== "visible") return;
      brief
        .status()
        .then((s) => {
          if (!alive) return;
          day.current = s.date;
          if (s.show && closedOn.current !== s.date) setOpen(true);
          else if (s.dismissed_today) setOpen(false); // closed on another device
        })
        .catch(() => undefined);
    };
    check();
    const timer = window.setInterval(check, CHECK_MS);
    document.addEventListener("visibilitychange", check);
    return () => {
      alive = false;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", check);
    };
  }, [enabled]);

  const close = useCallback(() => {
    setOpen(false);
    closedOn.current = day.current;
    brief.dismiss().catch(() => undefined);
  }, []);

  return { open, close };
}
