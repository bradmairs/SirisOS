import { api, json } from "./client";

export interface CommandResult {
  intent: "task" | "cpd" | "calendar" | "note" | "ask";
  /** One or two sentences, said aloud. */
  reply: string;
  link: string | null;
}

/** Talk to SirisOS (4.3): one sentence does the thing. */
export const command = { run: (text: string) => api<CommandResult>("/api/v1/command", json({ text })) };

/** Say it aloud with the device's own voice (no-op where there isn't one). */
export function speak(text: string): void {
  try {
    const synth = window.speechSynthesis;
    if (!synth || typeof SpeechSynthesisUtterance === "undefined") return;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = navigator.language || "en-AU";
    synth.speak(u);
  } catch {
    /* no voice here */
  }
}
