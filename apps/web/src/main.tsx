import { installViewportFix } from "./api/viewport";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { registerServiceWorker } from "./api/push";
import { startOutbox } from "./api/outbox";
import { keepStorage, loadStore } from "./api/store";
import { inPrepFrame } from "./api/prepare";
import "./glass/glass.css";
import "./app.css";

// 11.4: what's kept on this phone (IndexedDB) is read in before the first render, so offline screens have it at once.
loadStore().finally(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
  if (!inPrepFrame()) {
    startOutbox();
    void keepStorage();
  }
});

registerServiceWorker();

// 9.62: fixed bars back in place after the keyboard closes or you come back to the app (api/viewport.ts).
installViewportFix();
