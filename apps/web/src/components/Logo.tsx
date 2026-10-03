import { useId } from "react";

/**
 * The SirisOS mark: an ice-blue "S" inside a HUD ring, glowing softly on black.
 * public/siris-mark.svg and siris-icon.png are the same drawing on a black tile.
 */
export function LogoMark({ size = 40, title = "SirisOS" }: { size?: number; title?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg className="logo-mark" width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={title}>
      <defs>
        <linearGradient id={`${id}s`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#c9f4ff" />
          <stop offset="0.45" stopColor="#5fd3ff" />
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
      <path
        d="M 39.5 22.5 A 7.5 7.5 0 1 0 32 32 A 7.5 7.5 0 1 1 24.5 41.5"
        fill="none"
        stroke={`url(#${id}s)`}
        strokeWidth="3"
        strokeLinecap="round"
        filter={`url(#${id}g)`}
      />
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
