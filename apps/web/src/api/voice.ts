/**
 * Voice for the Siris screen, ported from SirisAI's HUD (app/web/static/hud.html):
 * a WAV recorder that stops itself after a pause, and a player that joins the
 * reply's MP3 sentences so iPhone doesn't pause between them.
 */

export type VoiceEvent =
  | { type: "transcript"; text: string }
  | { type: "speaker"; user_id: string; score: number }
  | { type: "sentence"; text: string; audio: string | null }
  | { type: "tool_start" | "tool_end"; name: string; status?: string }
  | { type: "final"; conversation_id: string | null; response: string | null; expects_reply?: boolean; confirmation_required?: unknown }
  | { type: "error"; detail: string };

/** Reads newline-delimited JSON from a streamed response body. */
export async function* readNdjson<T>(body: ReadableStream<Uint8Array>): AsyncGenerator<T> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline: number;
    while ((newline = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (line) yield JSON.parse(line) as T;
    }
  }
  const rest = buffer.trim();
  if (rest) yield JSON.parse(rest) as T;
}

/** Why the microphone can't be used here, or null when it can. */
export function micUnavailableReason(): string | null {
  if (typeof window === "undefined") return "No browser.";
  if (!window.isSecureContext) return "Voice needs SirisOS to be opened over HTTPS (browsers only allow the microphone on secure pages). You can still type.";
  if (!navigator.mediaDevices?.getUserMedia) return "This browser can't record audio.";
  return null;
}

export function encodeWav(chunks: Float32Array[], rate: number): Blob {
  const length = chunks.reduce((n, c) => n + c.length, 0);
  const view = new DataView(new ArrayBuffer(44 + length * 2));
  const str = (o: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i));
  };
  str(0, "RIFF");
  view.setUint32(4, 36 + length * 2, true);
  str(8, "WAVE");
  str(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  str(36, "data");
  view.setUint32(40, length * 2, true);
  let o = 44;
  for (const c of chunks)
    for (const s of c) {
      view.setInt16(o, Math.max(-1, Math.min(1, s)) * 0x7fff, true);
      o += 2;
    }
  return new Blob([view], { type: "audio/wav" });
}

export interface Recording {
  analyser: AnalyserNode;
  /** Resolves with the WAV once speech ends (1.2 s of quiet), 12 s pass, or stop() is called. */
  done: Promise<Blob>;
  stop: () => void;
}

export async function startRecording(): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
  const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new Ctx();
  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  const chunks: Float32Array[] = [];
  let silentFor = 0;
  let heard = false;
  let finished = false;
  let resolve!: (wav: Blob) => void;
  const done = new Promise<Blob>((r) => (resolve = r));

  const stop = () => {
    if (finished) return;
    finished = true;
    window.clearTimeout(timer);
    processor.disconnect();
    source.disconnect();
    stream.getTracks().forEach((t) => t.stop());
    const rate = ctx.sampleRate;
    ctx.close().finally(() => resolve(encodeWav(chunks, rate)));
  };
  processor.onaudioprocess = (e) => {
    const samples = new Float32Array(e.inputBuffer.getChannelData(0));
    chunks.push(samples);
    const rms = Math.sqrt(samples.reduce((a, s) => a + s * s, 0) / samples.length);
    if (rms > 0.02) {
      heard = true;
      silentFor = 0;
    } else if (heard) {
      silentFor += samples.length / ctx.sampleRate;
    }
    if (heard && silentFor > 1.2) stop();
  };
  source.connect(analyser);
  source.connect(processor);
  processor.connect(ctx.destination);
  const timer = window.setTimeout(stop, 12000);
  return { analyser, done, stop };
}

/**
 * Plays the reply's sentences in order. iOS Safari only lets an element play
 * later if it was first played inside a tap, so unlock() runs on the orb tap.
 */
export class ReplyPlayer {
  private audio = typeof Audio !== "undefined" ? new Audio() : null;
  private unlocked = false;
  private pending: Uint8Array[] = [];
  private waiters: (() => void)[] = [];
  speaking = false;
  onSpeaking: (speaking: boolean) => void = () => {};

  unlock() {
    if (this.unlocked || !this.audio) return;
    this.unlocked = true;
    this.audio.src = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
    this.audio.play().then(() => this.audio?.pause()).catch(() => {});
  }

  play(base64: string) {
    this.pending.push(Uint8Array.from(atob(base64), (c) => c.charCodeAt(0)));
    if (!this.speaking) this.next();
  }

  stop() {
    this.pending = [];
    if (this.speaking) this.audio?.pause();
    this.finish();
  }

  finished(): Promise<void> {
    return this.speaking ? new Promise((r) => this.waiters.push(r)) : Promise.resolve();
  }

  private finish() {
    this.speaking = false;
    this.onSpeaking(false);
    this.waiters.splice(0).forEach((r) => r());
  }

  private next() {
    if (!this.audio || this.pending.length === 0) return this.finish();
    this.speaking = true;
    this.onSpeaking(true);
    const url = URL.createObjectURL(new Blob(this.pending.splice(0) as BlobPart[], { type: "audio/mpeg" }));
    let done = false;
    const advance = () => {
      if (done) return;
      done = true;
      URL.revokeObjectURL(url);
      this.next();
    };
    this.audio.onended = this.audio.onerror = advance;
    this.audio.src = url;
    this.audio.play().catch(advance);
  }
}
