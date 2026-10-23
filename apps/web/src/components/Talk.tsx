import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Mic, Square, Volume2, VolumeX } from "lucide-react";
import { brain } from "../api/hub";
import { command, speak, type CommandResult } from "../api/command";
import { micUnavailableReason, startRecording, type Recording } from "../api/voice";
import { Sheet } from "./Sheet";

type Phase = "listening" | "thinking" | "done" | "idle";

const MUTE_KEY = "sirisos.talk.muted";
const EXAMPLES = ["Add a task to call the plumber Friday", "What's on tomorrow?", "Log 1.5 hours CPD for the stormwater webinar", "Note: the levels are in the shared drive"];

function muted(): boolean {
  try { return localStorage.getItem(MUTE_KEY) === "1"; } catch { return false; }
}

/** Push to talk (4.3): opens listening, stops on a pause, does what was said and says what it did. */
export function Talk({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const blocked = micUnavailableReason();
  const [phase, setPhase] = useState<Phase>(blocked ? "idle" : "listening");
  const [heard, setHeard] = useState<string | null>(null);
  const [result, setResult] = useState<CommandResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [quiet, setQuiet] = useState(muted);
  const recording = useRef<Recording | null>(null);

  const run = useCallback(async (said: string) => {
    setHeard(said);
    setPhase("thinking");
    setError(null);
    try {
      const r = await command.run(said);
      setResult(r);
      if (!muted()) speak(r.reply);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPhase("done");
    }
  }, []);

  const listen = useCallback(async () => {
    setResult(null);
    setHeard(null);
    setError(null);
    setPhase("listening");
    try {
      const rec = await startRecording({ sampleRate: 16000 });
      recording.current = rec;
      const wav = await rec.done;
      recording.current = null;
      setPhase("thinking");
      const said = (await brain.transcribe(wav)).text.trim();
      if (!said) {
        setError("I didn't catch that. Try again, or type it.");
        setPhase("done");
        return;
      }
      await run(said);
    } catch (e) {
      setError(e instanceof DOMException && e.name === "NotAllowedError" ? "The microphone is blocked for SirisOS. You can type instead." : e instanceof Error ? e.message : String(e));
      setPhase("done");
    }
  }, [run]);

  useEffect(() => {
    if (!blocked) listen();
    return () => { recording.current?.stop(); window.speechSynthesis?.cancel(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    recording.current?.stop();
    run(text.trim());
    setText("");
  }
  function toggleQuiet() {
    const next = !quiet;
    setQuiet(next);
    try { localStorage.setItem(MUTE_KEY, next ? "1" : "0"); } catch { /* fine */ }
    if (next) window.speechSynthesis?.cancel();
  }

  return (
    <Sheet label="Talk to SirisOS" onClose={onClose}>
      <div className="talk">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 className="sheet__title" style={{ margin: 0 }}>Talk to SirisOS</h2>
          <button type="button" className="icon-link" onClick={toggleQuiet} aria-pressed={!quiet} aria-label={quiet ? "Read replies aloud" : "Don't read replies aloud"}>
            {quiet ? <VolumeX size={18} aria-hidden="true" /> : <Volume2 size={18} aria-hidden="true" />}
          </button>
        </div>
        <button type="button" className={`talk__orb talk__orb--${phase}`} disabled={!!blocked || phase === "thinking"}
          aria-label={phase === "listening" ? "Stop listening" : "Speak"} onClick={() => (phase === "listening" ? recording.current?.stop() : listen())}>
          {phase === "listening" ? <Square size={26} aria-hidden="true" /> : <Mic size={30} aria-hidden="true" />}
        </button>
        <p className="talk__status muted" role="status">
          {phase === "listening" ? "Listening… stop talking when you're done" : phase === "thinking" ? "On it…" : blocked ?? (result ? "Tap to say something else" : "Tap and speak")}
        </p>
        {heard && <p className="talk__heard">“{heard}”</p>}
        {result && (
          <div className="talk__reply">
            <p style={{ margin: 0 }}>{result.reply}</p>
            {result.link && <button type="button" className="button button--small" onClick={() => { onClose(); navigate(result.link!); }}>Open <ArrowRight size={14} aria-hidden="true" /></button>}
          </div>
        )}
        {error && <p className="tone-critical" role="alert" style={{ margin: 0 }}>{error}</p>}
        <form className="row" style={{ gap: 6 }} onSubmit={submit}>
          <input className="field" value={text} onChange={(e) => setText(e.target.value)} placeholder="Or type it" aria-label="Say it in words" />
          <button type="submit" className="button button--small button--primary" disabled={!text.trim() || phase === "thinking"} aria-label="Send">
            <ArrowRight size={15} aria-hidden="true" />
          </button>
        </form>
        {!result && !heard && (
          <ul className="talk__examples muted" aria-label="Things to try">
            {EXAMPLES.map((x) => <li key={x}>“{x}”</li>)}
          </ul>
        )}
      </div>
    </Sheet>
  );
}
