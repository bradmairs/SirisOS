import { useId } from "react";

/**
 * The SirisOS mark: an ice-blue S inside a HUD ring, glowing softly on black.
 *
 * Two S's are kept (docs/brand.md):
 * - "bolt" (current): a faceted lightning-bolt S, white to deep blue.
 * - "classic": the original curved S, kept to switch back.
 * `scripts/use-logo.sh bolt|classic` switches LOGO_STYLE here and the
 * matching public/siris-mark.svg and siris-icon.png (favicon, home-screen icon).
 */
export type LogoStyle = "bolt" | "classic";
export const LOGO_STYLE: LogoStyle = "bolt";

export function LogoMark({ size = 40, title = "SirisOS", variant = LOGO_STYLE }: { size?: number; title?: string; variant?: LogoStyle }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg className="logo-mark" width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={title} data-logo={variant}>
      <defs>
        <linearGradient id={`${id}s`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#c9f4ff" />
          <stop offset="0.45" stopColor="#5fd3ff" />
          <stop offset="1" stopColor="#1b7fb3" />
        </linearGradient>
        <linearGradient id={`${id}b`} gradientUnits="userSpaceOnUse" x1="27" y1="16" x2="37" y2="48">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="0.3" stopColor="#c9f4ff" />
          <stop offset="0.68" stopColor="#5fd3ff" />
          <stop offset="1" stopColor="#1b7fb3" />
        </linearGradient>
        <radialGradient id={`${id}c`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#5fd3ff" stopOpacity="0.22" />
          <stop offset="1" stopColor="#5fd3ff" stopOpacity="0" />
        </radialGradient>
        <filter id={`${id}g`} filterUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">
          <feGaussianBlur stdDeviation="1.4" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <circle cx="32" cy="32" r="22" fill={`url(#${id}c)`} />
      <circle cx="32" cy="32" r="24" fill="none" stroke="#5fd3ff" strokeOpacity="0.18" strokeWidth="0.8" />
      <g fill="none" stroke="#5fd3ff" strokeWidth="1.6" strokeLinecap="round" strokeOpacity="0.85" filter={`url(#${id}g)`}>
        <path className="logo-mark__arc" d="M 32 8 A 24 24 0 0 1 52.8 20" />
        <path className="logo-mark__arc" d="M 32 56 A 24 24 0 0 1 11.2 44" />
      </g>
      <circle cx="52.8" cy="20" r="1.5" fill="#c9f4ff" filter={`url(#${id}g)`} />
      <circle cx="11.2" cy="44" r="1.5" fill="#c9f4ff" filter={`url(#${id}g)`} />
      {variant === "bolt" ? (
        <>
          {/* A faceted lightning-bolt S: glass-white at the top to deep blue, darker lower faces, bright top edges. */}
          <path
            d="M 46 16.5 L 25 19 L 19 31.5 L 37.5 35.2 L 35.4 40.6 L 17 47.5 L 40 44.8 L 44 32.5 L 26.8 29.2 L 29 23.6 Z"
            fill={`url(#${id}b)`}
            stroke="#ffffff"
            strokeOpacity="0.35"
            strokeWidth="0.4"
            strokeLinejoin="miter"
            filter={`url(#${id}g)`}
          />
          <path d="M 25 19 L 19 31.5 L 26.8 29.2 L 29 23.6 Z" fill="#1b7fb3" fillOpacity="0.32" />
          <path d="M 37.5 35.2 L 44 32.5 L 40 44.8 L 17 47.5 L 35.4 40.6 Z" fill="#1b7fb3" fillOpacity="0.42" />
          <path d="M 45 16.8 L 25.6 19.2 L 20.2 30.6" fill="none" stroke="#ffffff" strokeOpacity="0.85" strokeWidth="0.7" strokeLinejoin="miter" />
          <path d="M 27.5 29.8 L 43 32.8" fill="none" stroke="#ffffff" strokeOpacity="0.55" strokeWidth="0.6" />
        </>
      ) : (
        <path
          d="M 39.5 22.5 A 7.5 7.5 0 1 0 32 32 A 7.5 7.5 0 1 1 24.5 41.5"
          fill="none"
          stroke={`url(#${id}s)`}
          strokeWidth="3"
          strokeLinecap="round"
          filter={`url(#${id}g)`}
        />
      )}
    </svg>
  );
}

/** Mark plus the SIRISOS wordmark, as used at the top of the sidebar. */
export function Logo({ size = 40 }: { size?: number }) {
  return (
    <span className="logo">
      <LogoMark size={size} />
      <span className="logo__word">
        SIRIS<b>OS</b>
      </span>
    </span>
  );
}
