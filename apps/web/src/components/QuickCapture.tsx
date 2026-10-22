import { dueLabel, isTaskText, tasks } from "../api/tasks";
import { useEffect, useRef, useState } from "react";
import { Camera, Check, Mic, Square, X } from "lucide-react";
import { brain } from "../api/hub";
import { micUnavailableReason, startRecording, type Recording } from "../api/voice";
import { Sheet } from "./Sheet";

const MAX_SIDE = 2048;

/** A photo as a JPEG data URL no wider or taller than 2048 px (phone photos are 12 MP+). */
export async function shrinkPhoto(file: File): Promise<string> {
  const original = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
  try {
    // A format the browser can't draw (or one that never loads) is sent as it is.
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image();
      const timer = window.setTimeout(() => reject(new Error("timeout")), 1500);
      el.onload = () => {
        window.clearTimeout(timer);
        resolve(el);
      };
      el.onerror = (e) => {
        window.clearTimeout(timer);
        reject(e);
      };
      el.src = original;
    });
    const scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
    if (!img.naturalWidth || (scale === 1 && file.type === "image/jpeg")) return original;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.naturalWidth * scale);
    canvas.height = Math.round(img.naturalHeight * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) return original;
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.85);
  } catch {
    return original;
  }
}

/** Quick capture from anywhere: a note, a photo or a voice memo, into the
 * Siris' inbox (filed properly later by the nightly sort). */
export function QuickCapture({ onClose }: { onClose: () => void }) {
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<string | null>(null);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [busy, setBusy] = useState<"photo" | "memo" | "save" | null>(null);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const [saved, setSaved] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const micProblem = micUnavailableReason();

  useEffect(() => {
    box.current?.focus();
    return () => recording?.stop();
  }, [recording]);

  async function pickPhoto(file: File | undefined) {
    if (!file) return;
    setBusy("photo");
    try {
      setPhoto(await shrinkPhoto(file));
    } catch {
      setNote({ ok: false, text: "Couldn't read that photo." });
    } finally {
      setBusy(null);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function memo() {
    if (recording) {
      recording.stop();
      return;
    }
    setNote(null);
    try {
      const rec = await startRecording({ stopOnSilence: false, maxSeconds: 240, sampleRate: 16000 });
      setRecording(rec);
      const wav = await rec.done;
      setRecording(null);
      setBusy("memo");
      const { text: heard } = await brain.transcribe(wav);
      setText((t) => (t.trim() ? `${t.trim()}\n\n${heard}` : heard));
    } catch (e) {
      setRecording(null);
      setNote({ ok: false, text: e instanceof Error ? e.message : "Couldn't record." });
    } finally {
      setBusy(null);
    }
  }

  async function save() {
    const value = text.trim();
    if (!value && !photo) return;
    setBusy("save");
    setNote(null);
    try {
      if (!photo && isTaskText(value)) {
        const made = await tasks.add({ text: value });
        setSaved(true);
        setNote({ ok: true, text: `Added to your tasks: “${made.title}”${made.due ? `, ${dueLabel({ due: made.due, time: made.time, group: "later" })}` : ""}.` });
        window.setTimeout(onClose, 900);
        return;
      }
      const isUrl = /^https?:\/\/\S+$/.test(value);
      const result = await brain.capture({ ...(isUrl ? { url: value } : value ? { text: value } : {}), ...(photo ? { image: photo } : {}) });
      setSaved(true);
      setNote({ ok: true, text: `Saved to Siris' inbox as “${result.title}”.` });
      window.setTimeout(onClose, 900);
    } catch (e) {
      setNote({ ok: false, text: e instanceof Error ? e.message : "Couldn't save." });
    } finally {
      setBusy(null);
    }
  }

  return (
    <Sheet label="Quick capture" onClose={onClose}>
      <h2 className="sheet__title">Quick capture</h2>
      <textarea ref={box} className="field capture__text" rows={5} placeholder="A thought, a link, or “remind me to…”" value={text} onChange={(e) => setText(e.target.value)} aria-label="Capture text"
        onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && save()} />
      {photo && (
        <div className="capture__photo">
          <img src={photo} alt="Photo to capture" />
          <button type="button" className="icon-link" onClick={() => setPhoto(null)} aria-label="Remove photo"><X size={16} aria-hidden="true" /></button>
        </div>
      )}
      <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 10 }}>
        <input ref={fileInput} type="file" accept="image/*" capture="environment" hidden onChange={(e) => pickPhoto(e.target.files?.[0])} aria-label="Photo file" />
        <button type="button" className="button button--small" onClick={() => fileInput.current?.click()} disabled={!!busy || saved}>
          <Camera size={15} aria-hidden="true" /> {busy === "photo" ? "Reading…" : photo ? "Retake" : "Photo"}
        </button>
        <button type="button" className={`button button--small ${recording ? "capture__rec" : ""}`} onClick={memo} disabled={!!micProblem || (!!busy && !recording) || saved}
          title={micProblem ?? undefined} aria-label={recording ? "Stop recording" : "Voice memo"}>
          {recording ? <Square size={14} aria-hidden="true" /> : <Mic size={15} aria-hidden="true" />} {recording ? "Stop" : busy === "memo" ? "Transcribing…" : "Voice memo"}
        </button>
        <button type="button" className="button button--small button--primary" style={{ marginLeft: "auto" }} onClick={save} disabled={!!busy || saved || (!text.trim() && !photo)}>
          <Check size={15} aria-hidden="true" /> {busy === "save" ? "Saving…" : "Save"}
        </button>
      </div>
      {note && <p className={note.ok ? "tone-good" : "tone-critical"} role="status" style={{ margin: "10px 0 0", fontSize: 14 }}>{note.text}</p>}
    </Sheet>
  );
}
