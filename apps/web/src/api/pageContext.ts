import { useEffect } from "react";

/**
 * What the screen on show is about (7.5), for "Ask Siris about this page": a screen
 * registers a title and a short plain-text summary of what's on it; the ask button
 * hands that to SirisAI with the question, so "what should I focus on?" means here.
 */
export interface PageContext { title: string; summary: string; path: string }

let current: PageContext | null = null;
let handoff: PageContext | null = null;
const MAX = 1500;

export function usePageContext(title: string, summary: string | null | undefined) {
  useEffect(() => {
    const mine: PageContext = { title, summary: (summary ?? "").slice(0, MAX), path: window.location.pathname };
    current = mine;
    return () => { if (current === mine) current = null; };
  }, [title, summary]);
}

export function pageContext(): PageContext | null {
  return current && current.path === window.location.pathname ? current : null;
}

/** Keep the page's context for the Assistant to pick up after navigating there. */
export function handOff(ctx: PageContext) { handoff = ctx; }

export function takeHandoff(): PageContext | null {
  const h = handoff;
  handoff = null;
  return h;
}

/** The prompt SirisAI gets: the question, then where it was asked and what's on that page. */
export function withContext(question: string, ctx: PageContext | null): string {
  if (!ctx) return question;
  return `${question}\n\n(Asked from SirisOS's ${ctx.title} page.${ctx.summary ? ` What's on it now:\n${ctx.summary}` : ""})`;
}
