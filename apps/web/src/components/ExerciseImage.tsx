import { useEffect, useState } from "react";
import { gym } from "../api/gym";

/**
 * An exercise's picture (9.7). The library's has two frames, the start and the end of the movement, so it plays them
 * in turn (or shows them side by side when you've asked for less motion). Fetched with your sign-in and kept for the
 * session, so a workout doesn't fetch the same picture twice.
 */
const cache = new Map<string, Promise<string>>();

export function clearExerciseImage(id: string) {
  for (const k of [...cache.keys()]) if (k.startsWith(`${id}:`)) cache.delete(k);
}

function load(id: string, frame: number, version: string): Promise<string> {
  const key = `${id}:${frame}:${version}`;
  let p = cache.get(key);
  if (!p) {
    p = gym.imageUrl(id, frame);
    p.catch(() => cache.delete(key));
    cache.set(key, p);
  }
  return p;
}

function reducedMotion(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function ExerciseImage({ id, name, frames = 2, size = "large", version = "" }: {
  id: string; name: string; frames?: number; size?: "thumb" | "large"; version?: string;
}) {
  const [urls, setUrls] = useState<string[]>([]);
  const [failed, setFailed] = useState(false);
  const [shown, setShown] = useState(0);
  const count = size === "thumb" ? 1 : Math.max(1, Math.min(2, frames));
  useEffect(() => {
    let alive = true;
    setFailed(false);
    Promise.all(Array.from({ length: count }, (_, i) => load(id, i, version)))
      .then((u) => { if (alive) setUrls(u); })
      .catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; };
  }, [id, count, version]);
  const still = reducedMotion();
  useEffect(() => {
    if (urls.length < 2 || still) return;
    const t = window.setInterval(() => setShown((n) => (n + 1) % urls.length), 1200);
    return () => window.clearInterval(t);
  }, [urls.length, still]);
  if (failed) return null;
  if (!urls.length) return <div className={`gym-image gym-image--${size} skeleton`} aria-hidden="true" />;
  if (urls.length > 1 && still) {
    return (
      <div className={`gym-image gym-image--${size} gym-image--pair`}>
        <img src={urls[0]} alt={`${name}: start`} /><img src={urls[1]} alt={`${name}: end`} />
      </div>
    );
  }
  return (
    <div className={`gym-image gym-image--${size}`}>
      <img src={urls[shown] ?? urls[0]} alt={urls.length > 1 ? `${name}: ${shown ? "end" : "start"} of the movement` : name} />
    </div>
  );
}
