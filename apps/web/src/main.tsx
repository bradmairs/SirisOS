import { installViewportFix } from "./api/viewport";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { registerServiceWorker } from "./api/push";
import { startOutbox } from "./api/outbox";
import "./glass/glass.css";
import "./app.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

registerServiceWorker();
startOutbox();

// 9.62: fixed bars back in place after the keyboard closes or you come back to the app (api/viewport.ts).
installViewportFix();
