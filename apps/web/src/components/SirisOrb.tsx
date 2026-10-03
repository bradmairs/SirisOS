import { useEffect, useRef } from "react";

export type OrbState = "idle" | "listening" | "thinking" | "speaking";

/**
 * The Siris orb from SirisAI's HUD: an ice-blue sphere that breathes when idle,
 * draws the microphone as a ring while listening, spins its hue while thinking
 * and pulses while speaking.
 */
export function SirisOrb({
  state,
  analyser,
  size = 220,
  onClick,
  label,
}: {
  state: OrbState;
  analyser?: AnalyserNode | null;
  size?: number;
  onClick: () => void;
  label: string;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvas.current;
    if (!el || !analyser || state !== "listening") return;
    const ctx = el.getContext("2d");
    if (!ctx) return;
    const data = new Uint8Array(analyser.frequencyBinCount);
    let frame = 0;
    const draw = () => {
      analyser.getByteTimeDomainData(data);
      ctx.clearRect(0, 0, el.width, el.height);
      ctx.strokeStyle = "rgba(138, 245, 200, 0.9)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      const cx = el.width / 2;
      const cy = el.height / 2;
      const base = el.width * 0.39;
      for (let i = 0; i <= data.length; i++) {
        const v = (data[i % data.length] - 128) / 128;
        const angle = (i / data.length) * Math.PI * 2;
        const r = base + v * 60;
        const x = cx + Math.cos(angle) * r;
        const y = cy + Math.sin(angle) * r;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      frame = requestAnimationFrame(draw);
    };
    draw();
    return () => {
      cancelAnimationFrame(frame);
      ctx.clearRect(0, 0, el.width, el.height);
    };
  }, [analyser, state]);

  return (
    <div className="orb-wrap" style={{ width: size, height: size }}>
      <span className="orb-ring orb-ring--outer" aria-hidden="true" />
      <span className="orb-ring orb-ring--inner" aria-hidden="true" />
      <canvas ref={canvas} className="orb-wave" width={400} height={400} aria-hidden="true" />
      <button type="button" className={`orb orb--${state}`} onClick={onClick} aria-label={label} aria-pressed={state === "listening"} />
    </div>
  );
}
