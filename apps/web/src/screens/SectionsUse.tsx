import { useEffect, useState } from "react";
import { BarChart3, Eye, EyeOff } from "lucide-react";
import { useResource } from "../api/resource";
import { usage as homeUsage, type Usage } from "../api/assist";
import { SECTIONS } from "../components/Sections";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";

const day = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/** Sections you use (11.11): how many days in the last four weeks you opened each section and its tabs, and a switch
 * to take one out of the side menu. Hidden ones are still in search, and their addresses still work. */
export function SectionsUseScreen() {
  const res = useResource<Usage>("home:usage", () => homeUsage.get(), { staleMs: 60_000, persist: true });
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { document.title = "Sections you use · SirisOS"; }, []);
  const u = res.data;
  const opened = u?.sections ?? {};
  const hidden = new Set(u?.menu_hidden ?? []);
  const rows = SECTIONS.flatMap((g) => g.sections).filter((s) => s.id !== "home").map((s) => {
    const tabs = s.tabs.map((t) => ({ ...t, days: opened[t.to] ?? 0 }));
    return { ...s, tabs, days: Math.max(0, ...tabs.map((t) => t.days)) };
  }).sort((a, b) => b.days - a.days);
  const since = u?.counting_since;
  const young = !since || (Date.now() - new Date(`${since}T12:00:00`).getTime()) / 86_400_000 < 21;
  const toggle = async (id: string) => {
    setMsg(null);
    const next = hidden.has(id) ? [...hidden].filter((x) => x !== id) : [...hidden, id];
    try { res.mutate?.(await homeUsage.setMenuHidden(next)); } catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't save that."); }
  };
  return (
    <>
      <PageHead eyebrow={since ? `Counting since ${day(since)}` : "Counting from now"} title="Sections you use" />
      <div className="stack" style={{ marginTop: 16 }}>
        {young && <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          {since ? `Only ${Math.max(1, Math.round((Date.now() - new Date(`${since}T12:00:00`).getTime()) / 86_400_000))} days counted so far` : "Nothing counted yet"}: about a month gives a fair picture before hiding much.</p>}
        <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Sections">
          <header className="widget__head"><BarChart3 aria-hidden="true" /><span>Days opened, last four weeks</span></header>
          <ul className="items">
            {rows.map((s) => (
              <li key={s.id} className={`item sections-use${hidden.has(s.id) ? " sections-use--hidden" : ""}`}>
                <s.Icon size={18} aria-hidden="true" className={s.days ? "" : "muted"} />
                <span className="item__text">
                  <span className="item__title">{s.label} <span className="muted">· {s.days ? `${s.days} day${s.days === 1 ? "" : "s"}` : "not opened"}</span></span>
                  {s.tabs.length > 1 && <span className="item__subtitle">{s.tabs.map((t) => `${t.label} ${t.days}`).join(" · ")}</span>}
                  <span className="sections-use__bar" aria-hidden="true"><span style={{ width: `${Math.min(100, (s.days / 28) * 100)}%` }} /></span>
                </span>
                <button type="button" className="chip chip--button" aria-pressed={!hidden.has(s.id)} onClick={() => void toggle(s.id)}
                  aria-label={`${hidden.has(s.id) ? "Show" : "Hide"} ${s.label} in the menu`}>
                  {hidden.has(s.id) ? <><EyeOff size={12} aria-hidden="true" /> Hidden</> : <><Eye size={12} aria-hidden="true" /> In menu</>}</button>
              </li>
            ))}
          </ul>
          <p className="muted" style={{ margin: 0, fontSize: 12 }}>A hidden section is still in search, its address still works, and it shows in the menu while you're in it.</p>
          {msg && <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
        </Glass>
      </div>
    </>
  );
}
