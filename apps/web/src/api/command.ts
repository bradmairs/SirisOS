import { api, json, request } from "./client";

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

/**
 * Read text aloud in SirisAI's voice (9.53, the briefing card's "Read it to
 * me"), falling back to the device's own voice when SirisAI has none or can't
 * be reached. Resolves when it starts; call the returned stop() to end it.
 */
// A tiny silent WAV, played during the tap so iOS lets the real audio start after the fetch.
const SILENCE = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

export async function readAloud(text: string, onEnd: () => void): Promise<() => void> {
  // Everything up to the first await runs inside the tap: unlock audio and speech now.
  let audio: HTMLAudioElement | null = null;
  try {
    audio = new Audio(SILENCE);
    void audio.play()?.catch(() => {});
  } catch { audio = null; }
  try { window.speechSynthesis?.speak(new SpeechSynthesisUtterance("")); } catch { /* no voice here */ }
  try {
    if (!audio) throw new Error("no audio");
    const response = await request("/api/v1/assistant/voice/speak", json({ text: text.slice(0, 6000) }));
    const url = URL.createObjectURL(await response.blob());
    audio.src = url;
    const done = () => { URL.revokeObjectURL(url); onEnd(); };
    audio.onended = done;
    audio.onerror = done;
    await audio.play();
    const playing = audio;
    return () => { playing.pause(); done(); };
  } catch {
    const synth = typeof window !== "undefined" ? window.speechSynthesis : undefined;
    if (!synth || typeof SpeechSynthesisUtterance === "undefined") { onEnd(); return () => {}; }
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = navigator.language || "en-AU";
    u.onend = onEnd;
    synth.speak(u);
    return () => { synth.cancel(); onEnd(); };
  }
}
