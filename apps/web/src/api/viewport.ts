/**
 * Keep fixed bars where they belong on iPhone (9.62).
 *
 * iOS can leave the page's fixed elements (the dock, the rest timer, the
 * composer) floating mid-screen after the keyboard closes, after coming back
 * from another app (the rest-timer Shortcut, the lock screen), or after a
 * rotation, until the next scroll. Until 9.62 SirisOS "scrolled" to where it
 * already was, which iOS ignores; a real one-pixel scroll and back makes it
 * lay the fixed bars out again. It runs once the keyboard has finished
 * closing (its animation is about a quarter of a second), and never while
 * you're typing in a field.
 */

const FIELDS = "input, textarea, select, [contenteditable]";

function typing(): boolean {
  return !!document.activeElement?.matches?.(FIELDS);
}

/** A real (one-pixel) scroll and back, so iOS re-lays-out fixed elements. */
export function settle(): void {
  if (typing()) return;
  const x = window.scrollX, y = window.scrollY;
  window.scrollTo(x, y > 0 ? y - 1 : y + 1);
  window.scrollTo(x, y);
}

let installed = false;

export function installViewportFix(): () => void {
  if (installed) return () => {};
  installed = true;
  const timers: number[] = [];
  const soon = () => {
    for (const ms of [60, 350]) timers.push(window.setTimeout(settle, ms));
  };
  const onFocusOut = (e: Event) => {
    if ((e.target as HTMLElement | null)?.matches?.(FIELDS)) soon();
  };
  const onVisible = () => { if (document.visibilityState === "visible") soon(); };
  const vv = window.visualViewport;
  let lastHeight = vv?.height ?? 0;
  const onViewport = () => {
    if (!vv || vv.scale > 1.01) return;  // pinch-zoomed: the visible area moving is you, leave it alone
    // The keyboard went away (the visible area grew back), or the page was left shifted under a closed keyboard.
    if (vv.height > lastHeight + 80 || (vv.offsetTop > 0 && !typing())) soon();
    lastHeight = vv.height;
  };
  document.addEventListener("focusout", onFocusOut);
  document.addEventListener("visibilitychange", onVisible);
  window.addEventListener("pageshow", soon);
  window.addEventListener("orientationchange", soon);
  vv?.addEventListener("resize", onViewport);
  vv?.addEventListener("scroll", onViewport);
  return () => {
    installed = false;
    timers.forEach((t) => window.clearTimeout(t));
    document.removeEventListener("focusout", onFocusOut);
    document.removeEventListener("visibilitychange", onVisible);
    window.removeEventListener("pageshow", soon);
    window.removeEventListener("orientationchange", soon);
    vv?.removeEventListener("resize", onViewport);
    vv?.removeEventListener("scroll", onViewport);
  };
}
