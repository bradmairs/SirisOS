import { useId, useMemo, useRef, useState, type ReactNode } from "react";

/** Small SVG charts (7.7) drawn to one spec: thin marks with rounded data
 * ends, 2px surface gaps between touching marks, hairline grids, text in ink
 * colours (never the series colour), a legend wherever there's more than one
 * series, and a hover/focus tooltip on every mark. No chart library. */

export interface Datum { key: string; label: string; value: number; color: string }

interface Tip { x: number; y: number; lines: ReactNode[] }

function useTip() {
  const box = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<Tip | null>(null);
  function show(e: { clientX: number; clientY: number }, lines: ReactNode[]) {
    const r = box.current?.getBoundingClientRect();
    if (!r) return;
    setTip({ x: e.clientX - r.left, y: e.clientY - r.top, lines });
  }
  function showAt(el: Element, lines: ReactNode[]) {
    const r = box.current?.getBoundingClientRect();
    const m = el.getBoundingClientRect();
    if (!r) return;
    setTip({ x: m.left - r.left + m.width / 2, y: m.top - r.top, lines });
  }
  const node = tip && (
    <div className="chart-tip" role="status" style={{ left: tip.x, top: tip.y }}>
      {tip.lines.map((l, i) => <div key={i}>{l}</div>)}
    </div>
  );
  return { box, show, showAt, hide: () => setTip(null), node };
}

export function Legend({ items }: { items: { label: string; color: string; value?: string }[] }) {
  return (
    <ul className="chart-legend">
      {items.map((i) => (
        <li key={i.label}>
          <span className="chart-swatch" style={{ background: i.color }} aria-hidden="true" />
          <span>{i.label}</span>
          {i.value && <span className="chart-legend__value">{i.value}</span>}
        </li>
      ))}
    </ul>
  );
}

function arc(cx: number, cy: number, r: number, start: number, end: number): string {
  const p = (a: number) => [cx + r * Math.cos(a - Math.PI / 2), cy + r * Math.sin(a - Math.PI / 2)];
  const [x1, y1] = p(start);
  const [x2, y2] = p(end);
  return `M ${x1} ${y1} A ${r} ${r} 0 ${end - start > Math.PI ? 1 : 0} 1 ${x2} ${y2}`;
}

/** Parts of a whole as a ring, with the headline in the middle. */
export function Donut({ data, format, center, centerLabel, size = 200 }: {
  data: Datum[]; format: (v: number) => string; center: string; centerLabel: string; size?: number;
}) {
  const tip = useTip();
  const total = data.reduce((t, d) => t + Math.max(0, d.value), 0);
  const r = size / 2 - 14;
  const gap = data.filter((d) => d.value > 0).length > 1 ? 2 / r : 0; // a 2px gap between segments
  let at = 0;
  return (
    <div className="chart" ref={tip.box}>
      <svg viewBox={`0 0 ${size} ${size}`} width="100%" style={{ maxWidth: size }} role="img" aria-label={`${centerLabel}: ${center}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--chart-grid)" strokeWidth={18} />
        {total > 0 && data.map((d) => {
          if (d.value <= 0) return null;
          const start = at;
          at += (d.value / total) * Math.PI * 2;
          const end = Math.max(start + 0.001, at - gap);
          const share = Math.round((100 * d.value) / total);
          const lines = [<strong key="l">{d.label}</strong>, `${format(d.value)} · ${share}%`];
          return (
            <path key={d.key} d={end - start >= Math.PI * 2 - 0.01 ? arc(size / 2, size / 2, r, 0, Math.PI * 1.9999) : arc(size / 2, size / 2, r, start, end)}
              fill="none" stroke={d.color} strokeWidth={18} strokeLinecap="butt" tabIndex={0} aria-label={`${d.label}: ${format(d.value)}, ${share}%`}
              onPointerMove={(e) => tip.show(e, lines)} onPointerLeave={tip.hide} onFocus={(e) => tip.showAt(e.currentTarget, lines)} onBlur={tip.hide}
              className="chart-mark" />
          );
        })}
        <text x="50%" y="47%" textAnchor="middle" className="chart-hero">{center}</text>
        <text x="50%" y="59%" textAnchor="middle" className="chart-sub">{centerLabel}</text>
      </svg>
      {tip.node}
    </div>
  );
}

/** One bar for the whole of income, split by where it goes. Overspending shows past the end. */
export function ShareBar({ data, whole, format }: { data: Datum[]; whole: number; format: (v: number) => string }) {
  const tip = useTip();
  const used = data.reduce((t, d) => t + Math.max(0, d.value), 0);
  const scale = Math.max(whole, used) || 1;
  let x = 0;
  return (
    <div className="chart" ref={tip.box}>
      <svg viewBox="0 0 400 36" width="100%" preserveAspectRatio="none" role="img" aria-label="Where income goes">
        {data.map((d, i) => {
          if (d.value <= 0) return null;
          const w = (d.value / scale) * 400;
          const left = x;
          x += w;
          const lines = [<strong key="l">{d.label}</strong>, `${format(d.value)} · ${Math.round((100 * d.value) / (whole || 1))}% of income`];
          const last = i === data.length - 1 || data.slice(i + 1).every((n) => n.value <= 0);
          return (
            <rect key={d.key} x={left} y={6} width={Math.max(1, w - (last ? 0 : 2))} height={24} rx={last ? 4 : 0} fill={d.color} tabIndex={0}
              aria-label={`${d.label}: ${format(d.value)}`} className="chart-mark"
              onPointerMove={(e) => tip.show(e, lines)} onPointerLeave={tip.hide} onFocus={(e) => tip.showAt(e.currentTarget, lines)} onBlur={tip.hide} />
          );
        })}
        {used > whole && whole > 0 && <line x1={(whole / scale) * 400} x2={(whole / scale) * 400} y1={0} y2={36} stroke="var(--chart-ink)" strokeWidth={2} />}
      </svg>
      {tip.node}
    </div>
  );
}

/** Share of income against a target, one row each (the 50/30/20 guide). */
export function TargetBars({ rows, format }: { rows: { key: string; label: string; share: number; target: number; color: string; amount: number }[]; format: (v: number) => string }) {
  const tip = useTip();
  const max = Math.max(1, ...rows.map((r) => Math.max(r.share, r.target) * 1.1));
  return (
    <div className="chart" ref={tip.box}>
      {rows.map((r) => {
        const pct = (v: number) => `${(100 * v) / max}%`;
        const lines = [<strong key="l">{r.label}</strong>, `${Math.round(r.share * 100)}% of income (${format(r.amount)})`, `Guide: ${Math.round(r.target * 100)}%`];
        return (
          <div key={r.key} className="target-row">
            <div className="target-row__label"><span>{r.label}</span><span>{Math.round(r.share * 100)}% <span className="muted">of {Math.round(r.target * 100)}%</span></span></div>
            <div className="target-row__track" tabIndex={0} aria-label={`${r.label}: ${Math.round(r.share * 100)}% of income; guide ${Math.round(r.target * 100)}%`}
              onPointerMove={(e) => tip.show(e, lines)} onPointerLeave={tip.hide} onFocus={(e) => tip.showAt(e.currentTarget, lines)} onBlur={tip.hide}>
              <div className="target-row__bar" style={{ width: pct(r.share), background: r.color }} />
              <div className="target-row__target" style={{ left: pct(r.target) }} aria-hidden="true" />
            </div>
          </div>
        );
      })}
      {tip.node}
    </div>
  );
}

/** Ranked horizontal bars with the value at the tip. */
export function RankBars({ data, format }: { data: Datum[]; format: (v: number) => string }) {
  const tip = useTip();
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="chart" ref={tip.box}>
      <ul className="rank-bars">
        {data.map((d) => {
          const lines = [<strong key="l">{d.label}</strong>, format(d.value)];
          return (
            <li key={d.key} tabIndex={0} aria-label={`${d.label}: ${format(d.value)}`}
              onPointerMove={(e) => tip.show(e, lines)} onPointerLeave={tip.hide} onFocus={(e) => tip.showAt(e.currentTarget, lines)} onBlur={tip.hide}>
              <span className="rank-bars__label">{d.label}</span>
              <span className="rank-bars__track">
                <span className="rank-bars__bar" style={{ width: `${Math.max(1.5, (100 * d.value) / max)}%`, background: d.color }} />
                <span className="rank-bars__value">{format(d.value)}</span>
              </span>
            </li>
          );
        })}
      </ul>
      {tip.node}
    </div>
  );
}

export interface Series { key: string; label: string; color: string; values: (number | null)[]; area?: boolean }

function niceTicks(max: number, min = 0): number[] {
  const span = Math.max(1, max - min);
  const step0 = span / 4;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) ?? step0;
  const out: number[] = [];
  for (let v = Math.floor(min / step) * step; v <= max + step * 0.001; v += step) out.push(Math.round(v * 100) / 100);
  if (out[out.length - 1] < max) out.push(out[out.length - 1] + step);
  return out;
}

/** Lines over time on one axis, with a crosshair tooltip and end labels. */
export function LineChart({ series, labels, format, height = 200, markers = [] }: {
  series: Series[]; labels: string[]; format: (v: number) => string; height?: number;
  markers?: { index: number; label: string }[];
}) {
  const tip = useTip();
  const clip = useId();
  const [hover, setHover] = useState<number | null>(null);
  const W = 520, H = height, L = 52, R = 86, T = 12, B = 26;
  const values = series.flatMap((s) => s.values.filter((v): v is number => v != null));
  const lo = Math.min(0, ...values);
  const ticks = useMemo(() => niceTicks(Math.max(1, ...values), lo), [values.join(","), lo]); // eslint-disable-line react-hooks/exhaustive-deps
  const top = ticks[ticks.length - 1], bottom = ticks[0];
  const x = (i: number) => L + (labels.length <= 1 ? 0 : (i * (W - L - R)) / (labels.length - 1));
  const y = (v: number) => T + (H - T - B) * (1 - (v - bottom) / (top - bottom || 1));
  const every = Math.max(1, Math.ceil(labels.length / 6));

  function move(e: React.PointerEvent<SVGRectElement>) {
    const r = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const i = Math.max(0, Math.min(labels.length - 1, Math.round(((px - L) / (W - L - R)) * (labels.length - 1))));
    setHover(i);
    tip.show(e, [<strong key="l">{labels[i]}</strong>, ...series.filter((s) => s.values[i] != null).map((s) => (
      <span key={s.key}><span className="chart-swatch" style={{ background: s.color }} /> {s.label}: {format(s.values[i] as number)}</span>
    ))]);
  }

  return (
    <div className="chart" ref={tip.box}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={series.map((s) => s.label).join(", ")}>
        <defs><clipPath id={clip}><rect x={L} y={0} width={W - L - R + 1} height={H} /></clipPath></defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="var(--chart-grid)" strokeWidth={1} />
            <text x={L - 8} y={y(t) + 4} textAnchor="end" className="chart-axis">{format(t)}</text>
          </g>
        ))}
        {labels.map((l, i) => (i % every === 0 || i === labels.length - 1) && (
          <text key={i} x={x(i)} y={H - 8} textAnchor="middle" className="chart-axis">{l}</text>
        ))}
        {series.map((s) => {
          const pts = s.values.map((v, i) => (v == null ? null : [x(i), y(v)] as const)).filter(Boolean) as (readonly [number, number])[];
          if (!pts.length) return null;
          const d = pts.map(([px, py], i) => `${i ? "L" : "M"} ${px} ${py}`).join(" ");
          const end = pts[pts.length - 1];
          const lastValue = [...s.values].reverse().find((v) => v != null) as number;
          return (
            <g key={s.key} clipPath={`url(#${clip})`} style={{ overflow: "visible" }}>
              {s.area && <path d={`${d} L ${end[0]} ${y(Math.max(bottom, 0))} L ${pts[0][0]} ${y(Math.max(bottom, 0))} Z`} fill={s.color} opacity={0.1} />}
              <path d={d} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
              <circle cx={end[0]} cy={end[1]} r={4} fill={s.color} stroke="var(--chart-surface)" strokeWidth={2} />
              <text x={W - R + 8} y={end[1] + 4} className="chart-endlabel" clipPath="none">{series.length > 1 ? s.label : format(lastValue)}</text>
            </g>
          );
        })}
        {markers.map((m) => (
          <g key={m.label}>
            <line x1={x(m.index)} x2={x(m.index)} y1={T} y2={H - B} stroke="var(--chart-grid-strong)" strokeWidth={1} />
            <text x={x(m.index) + 4} y={T + 10} className="chart-axis">{m.label}</text>
          </g>
        ))}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} stroke="var(--chart-ink)" strokeWidth={1} opacity={0.5} />}
        {hover != null && series.map((s) => s.values[hover] != null && (
          <circle key={s.key} cx={x(hover)} cy={y(s.values[hover] as number)} r={4} fill={s.color} stroke="var(--chart-surface)" strokeWidth={2} />
        ))}
        <rect x={L} y={0} width={W - L - R} height={H} fill="transparent" onPointerMove={move} onPointerLeave={() => { setHover(null); tip.hide(); }} />
      </svg>
      {tip.node}
    </div>
  );
}
