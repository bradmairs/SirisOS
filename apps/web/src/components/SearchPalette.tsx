import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  Award,
  Brain,
  Calculator,
  Clock3,
  CornerDownLeft,
  Gauge,
  LayoutGrid,
  Link2,
  Loader2,
  Ruler,
  Search,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { search, type SearchGroup, type SearchHit } from "../api/search";
import { CALCULATORS } from "../engineering/calculators";
import { Glass } from "./Glass";
import { iconFor } from "./icons";
import { NAV } from "./Sidebar";

const DEBOUNCE_MS = 180;
const RECENT_KEY = "sirisos.search.recent";

const GROUP_ICONS: Record<string, LucideIcon> = {
  "layout-grid": LayoutGrid,
  brain: Brain,
  sparkles: Sparkles,
  gauge: Gauge,
  link: Link2,
  ruler: Ruler,
  calculator: Calculator,
  goto: CornerDownLeft,
  award: Award,
};

const SCREENS: { title: string; subtitle: string; url: string; words?: string }[] = [
  ...NAV.map((n) => ({ title: n.label, subtitle: "Screen", url: n.to, words: n.label === "Siris" ? "assistant chat ai" : "" })),
  { title: "Today's brief", subtitle: "Screen", url: "/brief", words: "daily morning news weather" },
  { title: "SirisHydro", subtitle: "Engineering", url: "/engineering/hydro", words: "evidence question standards" },
  { title: "Calculators", subtitle: "Engineering", url: "/engineering/calculators", words: "calc" },
  { title: "Standards Library", subtitle: "Engineering", url: "/engineering/standards", words: "pdf guidelines" },
  { title: "Projects", subtitle: "Engineering", url: "/engineering/projects", words: "" },
  { title: "CPD", subtitle: "Career", url: "/career?view=cpd", words: "engineers australia hours continuing professional development" },
  { title: "Chartered pathway", subtitle: "Career", url: "/career?view=pathways", words: "cpeng chartership ner registration rpe victoria" },
  { title: "Competencies", subtitle: "Career", url: "/career?view=competencies", words: "stage 2 elements evidence" },
  { title: "Career goals", subtitle: "Career", url: "/career?view=goals", words: "next steps" },
];

export function words(q: string): string[] {
  return q.toLowerCase().trim().split(/\s+/).filter(Boolean);
}

/** Mirrors the server's scoring (app/search/service.py) so local and remote results interleave sensibly. */
export function score(query: string, title: string, ...rest: string[]): number {
  const q = query.toLowerCase().trim();
  const t = title.toLowerCase();
  const all = (texts: string[]) => {
    const hay = texts.join(" ").toLowerCase();
    return words(query).every((w) => hay.includes(w));
  };
  if (!q) return 0;
  if (t === q) return 4;
  if (t.startsWith(q)) return 3;
  if (new RegExp(`(^|[^a-z0-9])${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`).test(t)) return 2.5;
  if (t.includes(q)) return 2;
  if (all([title])) return 1.5;
  return all([title, ...rest]) ? 1 : 0;
}

function local(query: string): SearchGroup[] {
  const hit = (title: string, subtitle: string, url: string, kind: string, extra: string[] = []): SearchHit => ({
    title, subtitle, url, kind, external: false, app_id: null, score: score(query, title, subtitle, ...extra),
  });
  const screens = SCREENS.map((s) => hit(s.title, s.subtitle, s.url, "screen", [s.words ?? ""])).filter((h) => h.score > 0);
  const calcs = CALCULATORS.map((c) => hit(c.title, `Calculator · ${c.category}`, `/engineering/calculators/${c.id}`, "calculator")).filter((h) => h.score > 0);
  const group = (id: string, label: string, icon: string, hits: SearchHit[]): SearchGroup[] =>
    hits.length ? [{ id, label, icon, hits: hits.sort((a, b) => b.score - a.score).slice(0, 5), best: Math.max(...hits.map((h) => h.score)) }] : [];
  return [...group("goto", "Go to", "goto", screens), ...group("calculators", "Calculators", "calculator", calcs)];
}

function readRecent(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((v) => typeof v === "string").slice(0, 6) : [];
  } catch {
    return [];
  }
}

function remember(q: string) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify([q, ...readRecent().filter((r) => r.toLowerCase() !== q.toLowerCase())].slice(0, 6)));
  } catch {
    /* private mode: no history */
  }
}

function Highlight({ text, query }: { text: string; query: string }) {
  const ws = words(query).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!ws.length || !text) return <>{text}</>;
  const parts = text.split(new RegExp(`(${ws.join("|")})`, "ig"));
  return (
    <>
      {parts.map((p, i) => (i % 2 ? <mark key={i}>{p}</mark> : p))}
    </>
  );
}

function groupIcon(group: SearchGroup): LucideIcon {
  return GROUP_ICONS[group.icon] ?? iconFor(group.icon);
}

/**
 * Search everything (ADR 109): a Spotlight-style glass palette over the whole
 * shell. Screens and calculators match instantly in the browser; apps,
 * widgets, links, the Second Brain, Siris chats, APD PM, the Archive, the
 * Reviewer and the engineering library come from /api/v1/search.
 */
export function SearchPalette({ onClose, onOpenApp }: { onClose: () => void; onOpenApp: (appId: string) => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [remote, setRemote] = useState<{ q: string; groups: SearchGroup[]; failed: string[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const [recent] = useState(readRecent);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const q = query.trim();

  useEffect(() => {
    input.current?.focus();
    document.body.classList.add("no-scroll");
    return () => document.body.classList.remove("no-scroll");
  }, []);

  useEffect(() => {
    if (q.length < 2) {
      setRemote(null);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    const timer = window.setTimeout(() => {
      search
        .everything(q, controller.signal)
        .then((r) => {
          setRemote({ q, groups: r.groups, failed: r.failed });
          setError(null);
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setError(err instanceof Error ? err.message : "Search failed.");
        })
        .finally(() => !controller.signal.aborted && setLoading(false));
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [q]);

  const groups = useMemo(() => {
    if (q.length < 1) return [];
    const mine = local(q);
    const theirs = remote && remote.q === q ? remote.groups : [];
    const ask: SearchGroup = {
      id: "ask", label: "Ask Siris", icon: "sparkles", best: -1,
      hits: [{ title: `Ask Siris “${q}”`, subtitle: "Start a chat", url: `/assistant?q=${encodeURIComponent(q)}`, kind: "ask", external: false, app_id: null, score: 0 }],
    };
    // Stable sort: on a tie, instant local results stay ahead of the server's.
    return [...mine, ...theirs].sort((a, b) => b.best - a.best).concat(ask);
  }, [q, remote]);

  const flat = useMemo(() => groups.flatMap((g) => g.hits.map((h) => ({ group: g, hit: h }))), [groups]);
  useEffect(() => setActive(0), [q, remote]);
  useEffect(() => {
    list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView?.({ block: "nearest" });
  }, [active]);

  function open(h: SearchHit) {
    if (q) remember(q);
    onClose();
    if (h.kind === "app" && h.app_id) onOpenApp(h.app_id);
    else if (h.url && h.external) window.open(h.url, "_blank", "noopener,noreferrer");
    else if (h.url) navigate(h.url);
  }

  function onKeyDown(e: ReactKeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(flat.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter" && flat[active]) {
      e.preventDefault();
      open(flat[active].hit);
    }
  }

  const failed = remote && remote.q === q ? remote.failed : [];
  let index = -1;

  return (
    <div className="scrim search-scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <Glass variant="strong" shape="xl" className="search" role="dialog" aria-modal="true" aria-label="Search everything" onKeyDown={onKeyDown}>
        <div className="search__bar">
          {loading ? <Loader2 className="spin" aria-hidden="true" /> : <Search aria-hidden="true" />}
          <input
            ref={input}
            className="search__input"
            placeholder="Search apps, notes, chats, projects…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search everything"
            role="combobox"
            aria-expanded={flat.length > 0}
            aria-controls="search-results"
            aria-activedescendant={flat.length ? `search-hit-${active}` : undefined}
            autoComplete="off"
            spellCheck={false}
          />
          <button type="button" className="search__esc" onClick={onClose} aria-label="Close search">esc</button>
        </div>

        <div className="search__results" id="search-results" role="listbox" ref={list} aria-label="Results">
          {!q && (
            <Section title={recent.length ? "Recent" : "Try"} Icon={Clock3}>
              {(recent.length ? recent : ["pump station", "Home Assistant", "invoice"]).map((r) => (
                <button key={r} type="button" className="search__hit" onClick={() => setQuery(r)}>
                  <span className="search__hit-text">
                    <span className="search__hit-title">{r}</span>
                  </span>
                </button>
              ))}
            </Section>
          )}

          {groups.map((g) => (
            <Section key={g.id} title={g.label} Icon={groupIcon(g)}>
              {g.hits.map((h) => {
                index += 1;
                const i = index;
                return (
                  <div
                    key={`${g.id}-${i}`}
                    id={`search-hit-${i}`}
                    data-index={i}
                    role="option"
                    aria-selected={i === active}
                    className={`search__hit ${i === active ? "search__hit--active" : ""}`}
                    onMouseMove={() => i !== active && setActive(i)}
                    onClick={() => open(h)}
                  >
                    <span className="search__hit-text">
                      <span className="search__hit-title"><Highlight text={h.title} query={q} /></span>
                      {h.subtitle && <span className="search__hit-sub"><Highlight text={h.subtitle} query={q} /></span>}
                    </span>
                    {h.external ? <ArrowUpRight size={15} className="search__hit-go" aria-label="Opens the app" /> : i === active && <CornerDownLeft size={14} className="search__hit-go" aria-hidden="true" />}
                  </div>
                );
              })}
            </Section>
          ))}

          {q.length >= 2 && !loading && remote?.q === q && remote.groups.length === 0 && local(q).length === 0 && (
            <p className="muted search__note">Nothing found for “{q}” in SirisOS or its apps.</p>
          )}
          {error && <p className="search__note tone-critical">{error}</p>}
          {failed.length > 0 && <p className="muted search__note">Couldn't reach: {failed.join(", ")}.</p>}
        </div>

        <footer className="search__foot" aria-hidden="true">
          <span><kbd>↑</kbd><kbd>↓</kbd> move</span>
          <span><kbd>↵</kbd> open</span>
          <span><kbd>esc</kbd> close</span>
          <span className="spacer" />
          <span>Apps · Brain · Chats · Projects · Archive · Engineering</span>
        </footer>
      </Glass>
    </div>
  );
}

function Section({ title, Icon, children }: { title: string; Icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="search__group" aria-label={title}>
      <h3 className="search__group-title">
        <Icon size={14} aria-hidden="true" /> {title}
      </h3>
      {children}
    </section>
  );
}
