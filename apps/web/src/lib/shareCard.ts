/**
 * 12.5: a picture of a walk to send to people: its shape, name, numbers and climb, on a plain background. No map
 * tiles, and the route comes without the ends near home (the GPX with hide_home), so it doesn't show where you live.
 */

export interface CardWalk { name: string; place: string; when: string; kind: "walk" | "hike"; stats: [string, string][]; heights: number[] }

export function gpxPoints(gpx: string): [number, number][] {
  const out: [number, number][] = [];
  const re = /<trkpt lat="(-?[\d.]+)" lon="(-?[\d.]+)"/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(gpx))) out.push([Number(m[1]), Number(m[2])]);
  return out;
}

/** The route fitted into a w×h box, north up, kept in proportion. */
export function fit(points: [number, number][], w: number, h: number): [number, number][] {
  if (points.length < 2) return [];
  const lat0 = points.reduce((a, p) => a + p[0], 0) / points.length;
  const k = Math.cos((lat0 * Math.PI) / 180);
  const xs = points.map((p) => p[1] * k), ys = points.map((p) => p[0]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const s = Math.min(w / (maxX - minX || 1e-9), h / (maxY - minY || 1e-9));
  const ox = (w - (maxX - minX) * s) / 2, oy = (h - (maxY - minY) * s) / 2;
  return points.map((_, i) => [ox + (xs[i] - minX) * s, oy + (maxY - ys[i]) * s]);
}

export async function drawCard(walk: CardWalk, route: [number, number][]): Promise<Blob> {
  const W = 1080, H = 1350, colour = walk.kind === "hike" ? "#f97316" : "#38bdf8";
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  const g = c.getContext("2d")!;
  const bg = g.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#0b1220"); bg.addColorStop(1, "#12233b");
  g.fillStyle = bg; g.fillRect(0, 0, W, H);
  const font = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
  g.fillStyle = "#fff"; g.font = `700 64px ${font}`;
  let title = walk.name;
  while (g.measureText(title).width > W - 160 && title.length > 4) title = `${title.slice(0, -2)}…`;
  g.fillText(title, 80, 150);
  g.fillStyle = "rgba(255,255,255,0.7)"; g.font = `400 36px ${font}`;
  g.fillText([walk.place, walk.when].filter(Boolean).join(" · "), 80, 210);
  // the route
  const pts = fit(route, W - 260, 600).map(([x, y]) => [x + 130, y + 270] as [number, number]);
  if (pts.length > 1) {
    g.lineJoin = g.lineCap = "round";
    for (const [width, style] of [[22, "rgba(0,0,0,0.35)"], [12, colour]] as const) {
      g.strokeStyle = style; g.lineWidth = width; g.beginPath();
      pts.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)));
      g.stroke();
    }
    for (const [[x, y], fill] of [[pts[0], "#22c55e"], [pts[pts.length - 1], "#ef4444"]] as const) {
      g.fillStyle = fill; g.strokeStyle = "#fff"; g.lineWidth = 5; g.beginPath(); g.arc(x, y, 14, 0, Math.PI * 2); g.fill(); g.stroke();
    }
  }
  // the numbers
  walk.stats.slice(0, 4).forEach(([value, label], i) => {
    const x = 80 + (i % 2) * 470, y = 970 + Math.floor(i / 2) * 120;
    g.fillStyle = "#fff"; g.font = `700 56px ${font}`; g.fillText(value, x, y);
    g.fillStyle = "rgba(255,255,255,0.6)"; g.font = `400 30px ${font}`; g.fillText(label, x, y + 40);
  });
  // the climb
  if (walk.heights.length > 1) {
    const lo = Math.min(...walk.heights), hi = Math.max(...walk.heights), span = Math.max(hi - lo, 40);
    const x = (i: number) => 80 + (i / (walk.heights.length - 1)) * (W - 160), y = (m: number) => 1290 - ((m - lo) / span) * 70;
    g.beginPath(); g.moveTo(80, 1290);
    walk.heights.forEach((m, i) => g.lineTo(x(i), y(m)));
    g.lineTo(W - 80, 1290); g.closePath();
    g.fillStyle = `${colour}55`; g.fill();
  }
  g.fillStyle = "rgba(255,255,255,0.5)"; g.font = `600 26px ${font}`; g.textAlign = "right";
  g.fillText("SirisTrails", W - 80, 1330);
  const blob = await new Promise<Blob | null>((ok) => c.toBlob(ok, "image/png"));
  if (!blob) throw new Error("Couldn't draw the card.");
  return blob;
}

/** The share sheet when there is one (iPhone), else a download. */
export async function shareOrSave(blob: Blob, filename: string, title: string): Promise<void> {
  const file = new File([blob], filename, { type: blob.type });
  const nav = navigator as Navigator & { canShare?: (d: ShareData) => boolean };
  if (nav.share && nav.canShare?.({ files: [file] })) {
    try { await nav.share({ files: [file], title }); return; } catch (e) { if (e instanceof Error && e.name === "AbortError") return; }
  }
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement("a"), { href: url, download: filename }).click();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
