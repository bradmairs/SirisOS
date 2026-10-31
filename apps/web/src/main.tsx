import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { registerServiceWorker } from "./api/push";
import "./glass/glass.css";
import "./app.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

registerServiceWorker();

// iOS leaves the page scrolled up after the keyboard closes, so fixed bars
// (the dock) float mid-screen until the next scroll. Nudge it back.
document.addEventListener("focusout", (event) => {
  const target = event.target as HTMLElement | null;
  if (!target || !target.matches("input, textarea, select, [contenteditable]")) return;
  setTimeout(() => {
    if (!document.activeElement?.matches("input, textarea, select, [contenteditable]")) {
      window.scrollTo(window.scrollX, window.scrollY);
    }
  }, 50);
});
