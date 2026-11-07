import { useEffect, useState } from "react";
import { Check, PenLine, SkipForward } from "lucide-react";
import { ApiError } from "../api/client";
import { brain } from "../api/hub";
import type { HandwritingPage } from "../api/types";
import { Glass } from "../components/Glass";

/**
 * Handwriting to check (7.6): one handwritten OneNote page at a time, the page beside the machine's
 * reading of it, the likeliest misreadings first. "It's right" or a correction takes it off the list;
 * a correction replaces the transcription in Siris with Brad's own reading.
 */
export function HandwritingPanel() {
  const [queue, setQueue] = useState<HandwritingPage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let live = true;
    brain
      .handwriting(30)
      .then((pages) => live && setQueue(pages))
      .catch((err) => {
        if (!live) return;
        if (err instanceof ApiError && err.status === 404) setUnavailable(true);   // a SirisAI from before 4.9
        else setError(err instanceof Error ? err.message : "Couldn't load the handwriting to check.");
      });
    return () => {
      live = false;
    };
  }, []);

  const page = queue?.[0];
  if (unavailable) return null;
  const next = (message: string | null) => {
    setDone(message);
    setQueue((q) => (q ?? []).slice(1));
  };

  return (
    <Glass className="widget handwriting" aria-label="Handwriting to check">
      <div className="widget__head">
        <PenLine aria-hidden="true" /> Handwriting to check
        {queue && queue.length > 0 && <span className="muted handwriting__count">{queue.length}{queue.length === 30 ? "+" : ""} left</span>}
      </div>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        Your handwritten OneNote pages, read by the vision model. Check the reading against the page, the shakiest first.
      </p>
      {done && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{done}</p>}
      {error && <p className="tone-critical" style={{ margin: 0 }}>{error}</p>}
      {queue === null && !error ? (
        <div className="skeleton" style={{ height: 120 }} />
      ) : !page ? (
        !error && <p className="muted" style={{ margin: 0 }}>Nothing left to check.</p>
      ) : (
        <HandwritingCard key={page.title} page={page} onDone={next} />
      )}
    </Glass>
  );
}

function HandwritingCard({ page, onDone }: { page: HandwritingPage; onDone: (message: string | null) => void }) {
  const [images, setImages] = useState<string[]>([]);
  const [imageError, setImageError] = useState<string | null>(null);
  const [text, setText] = useState(page.text);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const urls: string[] = [];
    (async () => {
      try {
        const first = await brain.handwritingImage(page.title, 1);
        urls.push(URL.createObjectURL(first.blob));
        for (let n = 2; n <= Math.min(first.parts, 8); n++) {
          urls.push(URL.createObjectURL((await brain.handwritingImage(page.title, n)).blob));
        }
        if (live) setImages([...urls]);
      } catch (err) {
        if (live) setImageError(err instanceof Error ? err.message : "Couldn't draw the page.");
      }
    })();
    return () => {
      live = false;
      urls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [page.title]);

  async function check(corrected: boolean) {
    setBusy(true);
    setError(null);
    try {
      await brain.handwritingCheck(page.title, corrected ? text.trim() : "");
      onDone(corrected ? `Saved your reading of “${page.title}”.` : `“${page.title}” marked right.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
      setBusy(false);
    }
  }

  const changed = text.trim() !== page.text.trim();
  return (
    <div className="stack handwriting__card">
      <div className="item__title">{page.title}</div>
      {page.odd_words.length > 0 && (
        <div className="row handwriting__odd" aria-label="Words that look misread">
          {page.odd_words.slice(0, 8).map((w) => (
            <span key={w} className="chip">{w}</span>
          ))}
        </div>
      )}
      <div className="handwriting__pair">
        <div className="handwriting__page">
          {images.length > 0 ? (
            images.map((src, i) => <img key={src} src={src} alt={`${page.title}, part ${i + 1} of the handwritten page`} />)
          ) : imageError ? (
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>{imageError}</p>
          ) : (
            <div className="skeleton" style={{ height: 160 }} />
          )}
        </div>
        <textarea
          className="field handwriting__text"
          rows={12}
          aria-label="What the page says"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="row">
        {changed ? (
          <Glass as="button" type="button" shape="pill" interactive className="button button--small" onClick={() => check(true)} disabled={busy || !text.trim()}>
            <PenLine aria-hidden="true" /> {busy ? "Saving…" : "Save my reading"}
          </Glass>
        ) : (
          <Glass as="button" type="button" shape="pill" interactive className="button button--small" onClick={() => check(false)} disabled={busy}>
            <Check aria-hidden="true" /> {busy ? "Saving…" : "It's right"}
          </Glass>
        )}
        <button type="button" className="chip chip--button" onClick={() => onDone(null)} disabled={busy}>
          <SkipForward size={13} aria-hidden="true" /> Skip
        </button>
      </div>
    </div>
  );
}
