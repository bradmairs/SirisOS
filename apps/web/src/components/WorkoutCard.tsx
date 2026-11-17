import { useEffect, useState } from "react";
import { Share2 } from "lucide-react";
import { useResource } from "../api/resource";
import { gym, type GymRecord, type SetLog, type Summary, type Watch } from "../api/gym";

/**
 * A finished-workout card (9.6): an image of the session (what you lifted, volume, new bests and the Watch's heart
 * rate) to save or share. It's drawn on the phone; nothing leaves SirisOS unless you share it.
 */

export interface CardData {
  title: string;
  date: string;
  stats: { value: string; label: string }[];
  lifts: { name: string; best: string }[];
  more: number;
  records: string[];
  heart: string | null;
}

interface SessionLike {
  title: string;
  started_at: string;
  summary: Summary;
  records: GymRecord[];
  entries: { name: string; exercise: string; sets: SetLog[]; assisted?: boolean; per_side?: boolean }[];
  watch?: Watch | null;
}

const MAX_LIFTS = 6;

function bestSet(sets: SetLog[], unit: string, assisted = false, perSide = false): string | null {
  const work = sets.filter((x) => x.done && x.type !== "warmup");
  if (!work.length) return null;
  const weighted = work.filter((x) => x.weight);
  if (assisted) {  // 9.6: the weight is help, so the best set is the one with least
    const least = work.reduce((a, b) => ((b.weight ?? 0) < (a.weight ?? 0) ? b : a));
    return `${work.length} × ${least.reps ?? "–"} · ${least.weight ? `${least.weight} ${unit} help` : "no help"}`;
  }
  if (weighted.length) {
    const top = weighted.reduce((a, b) => ((b.weight ?? 0) > (a.weight ?? 0) || ((b.weight ?? 0) === (a.weight ?? 0) && (b.reps ?? 0) > (a.reps ?? 0)) ? b : a));
    return `${work.length} × ${top.reps ?? "–"} · top ${top.weight} ${unit}${perSide ? " a side" : ""}`;
  }
  const secs = work.filter((x) => x.seconds);
  if (secs.length) return `${work.length} × ${Math.max(...secs.map((x) => x.seconds ?? 0))} s`;
  const km = work.reduce((n, x) => n + (x.km ?? 0), 0);
  if (km) return `${Math.round(km * 10) / 10} km`;
  return `${work.length} × ${Math.max(...work.map((x) => x.reps ?? 0))} reps`;
}

/** What goes on the card, from a saved workout. */
export function cardData(s: SessionLike, unit = "kg"): CardData {
  const day = new Date(s.started_at);
  const lifts = s.entries.map((e) => ({ name: e.name, best: bestSet(e.sets, unit, e.assisted, e.per_side) })).filter((l): l is { name: string; best: string } => !!l.best);
  const volume = s.summary.volume >= 10_000 ? `${(s.summary.volume / 1000).toFixed(1)} t` : `${Math.round(s.summary.volume).toLocaleString()} ${unit}`;
  const w = s.watch;
  const heart = w && (w.avg_hr || w.kj)
    ? [w.avg_hr && `${Math.round(w.avg_hr)} bpm average`, w.max_hr && `${Math.round(w.max_hr)} max`, w.kj && `${Math.round(w.kj).toLocaleString()} kJ`].filter(Boolean).join(" · ")
    : null;
  return {
    title: s.title,
    date: day.toLocaleDateString("en-AU", { weekday: "long", day: "numeric", month: "long", year: "numeric" }),
    stats: [
      ...(s.summary.minutes ? [{ value: String(s.summary.minutes), label: "minutes" }] : []),
      { value: String(s.summary.sets), label: "sets" },
      { value: volume, label: "lifted" },
    ],
    lifts: lifts.slice(0, MAX_LIFTS),
    more: Math.max(0, lifts.length - MAX_LIFTS),
    records: (s.records ?? []).map((r) => r.text).slice(0, 4),
    heart,
  };
}

const W = 1080, H = 1350, PAD = 80;

function fit(ctx: CanvasRenderingContext2D, text: string, max: number): string {
  if (ctx.measureText(text).width <= max) return text;
  let t = text;
  while (t.length > 1 && ctx.measureText(`${t}…`).width > max) t = t.slice(0, -1);
  return `${t.trimEnd()}…`;
}

/** The card as a PNG (1080 × 1350, a phone-friendly portrait). Null where there's no canvas. */
export async function drawCard(d: CardData): Promise<Blob | null> {
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext?.("2d");
  if (!ctx) return null;
  const font = (size: number, weight = 400) => `${weight} ${size}px -apple-system, "SF Pro Display", "Segoe UI", Roboto, sans-serif`;
  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#0b1220");
  bg.addColorStop(1, "#06223a");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = "rgba(94, 200, 255, 0.10)";
  ctx.beginPath();
  ctx.arc(W - 120, 140, 260, 0, Math.PI * 2);
  ctx.fill();

  let y = PAD + 30;
  ctx.fillStyle = "#7dd3fc";
  ctx.font = font(30, 600);
  ctx.fillText("SIRISGYM", PAD, y);
  y += 78;
  ctx.fillStyle = "#ffffff";
  ctx.font = font(68, 700);
  ctx.fillText(fit(ctx, d.title, W - 2 * PAD), PAD, y);
  y += 52;
  ctx.fillStyle = "#94a3b8";
  ctx.font = font(32);
  ctx.fillText(d.date, PAD, y);

  y += 100;
  const col = (W - 2 * PAD) / d.stats.length;
  d.stats.forEach((s, i) => {
    ctx.fillStyle = "#ffffff";
    ctx.font = font(64, 700);
    ctx.fillText(fit(ctx, s.value, col - 20), PAD + i * col, y);
    ctx.fillStyle = "#94a3b8";
    ctx.font = font(28);
    ctx.fillText(s.label, PAD + i * col, y + 42);
  });

  y += 110;
  ctx.strokeStyle = "rgba(148, 163, 184, 0.25)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(PAD, y);
  ctx.lineTo(W - PAD, y);
  ctx.stroke();
  y += 62;
  for (const l of d.lifts) {
    ctx.fillStyle = "#e2e8f0";
    ctx.font = font(36, 600);
    ctx.fillText(fit(ctx, l.name, 520), PAD, y);
    ctx.fillStyle = "#94a3b8";
    ctx.font = font(32);
    const best = fit(ctx, l.best, W - 2 * PAD - 540);
    ctx.fillText(best, W - PAD - ctx.measureText(best).width, y);
    y += 62;
  }
  if (d.more) {
    ctx.fillStyle = "#94a3b8";
    ctx.font = font(30);
    ctx.fillText(`and ${d.more} more`, PAD, y);
    y += 56;
  }
  if (d.records.length) {
    y += 20;
    ctx.fillStyle = "#fbbf24";
    ctx.font = font(30, 600);
    ctx.fillText("NEW BESTS", PAD, y);
    y += 50;
    ctx.font = font(32);
    for (const r of d.records) {
      if (y > H - 170) break;
      ctx.fillStyle = "#fde68a";
      ctx.fillText(fit(ctx, `★ ${r}`, W - 2 * PAD), PAD, y);
      y += 50;
    }
  }
  if (d.heart) {
    ctx.fillStyle = "#fca5a5";
    ctx.font = font(32);
    ctx.fillText(fit(ctx, `♥ ${d.heart}`, W - 2 * PAD), PAD, H - PAD - 10);
  }
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/png"));
}

function fileName(d: CardData): string {
  return `${d.title.replace(/[^\w -]+/g, "").trim().replace(/\s+/g, "-").toLowerCase() || "workout"}.png`;
}

/** Share (or save) a saved workout's card. The image is made as soon as the workout loads, so the tap can share it at once (iOS wants that). */
export function ShareWorkout({ id, unit = "kg" }: { id: string; unit?: string }) {
  const res = useResource(`gym:session:${id}`, () => gym.session(id), {});
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [said, setSaid] = useState<string | null>(null);

  useEffect(() => {
    if (!res.data || !Array.isArray(res.data.entries) || !res.data.summary) return;
    let gone = false;
    let made: string | null = null;
    const d = cardData(res.data, unit);
    void drawCard(d).then((blob) => {
      if (gone || !blob) return;
      made = URL.createObjectURL(blob);
      setFile(new File([blob], fileName(d), { type: "image/png" }));
      setUrl(made);
    });
    return () => { gone = true; if (made) URL.revokeObjectURL(made); };
  }, [res.data, unit]);

  if (!url || !file) return null;
  const share = async () => {
    setSaid(null);
    const nav = navigator as Navigator & { canShare?: (d: ShareData) => boolean };
    if (nav.share && nav.canShare?.({ files: [file] })) {
      try { await nav.share({ files: [file], title: res.data?.title }); } catch { /* closed the share sheet */ }
      return;
    }
    const a = document.createElement("a");
    a.href = url;
    a.download = file.name;
    a.click();
    setSaid("Saved to your downloads.");
  };
  return (
    <div className="stack" style={{ gap: 6 }}>
      <img src={url} alt={`Workout card: ${res.data?.title ?? "workout"}`} style={{ width: 120, borderRadius: 10, border: "1px solid var(--line, rgba(148,163,184,.25))" }} />
      <button type="button" className="button button--small" style={{ alignSelf: "flex-start" }} onClick={share}>
        <Share2 size={14} aria-hidden="true" /> Share workout card
      </button>
      {said && <span className="muted" role="status" style={{ fontSize: 12 }}>{said}</span>}
    </div>
  );
}
