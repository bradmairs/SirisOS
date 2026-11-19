import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChefHat, ExternalLink, ShoppingCart, Trash2, UtensilsCrossed } from "lucide-react";
import { Glass } from "../components/Glass";
import { useResource } from "../api/resource";
import { meals, type MealWeek, type Recipe, type Shopping } from "../api/meals";

/**
 * Meals (10.2): the week's dinners, from your Mealie recipes when Mealie is set up (and in Mealie's own meal plan),
 * and the shopping for them onto your Home Assistant list.
 */

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const DAY = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });

function Picker({ week, date, start, onDone, onCancel }: { week: MealWeek; date: string; start: string; onDone: (w: MealWeek) => void; onCancel: () => void }) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Recipe[]>([]);
  const [title, setTitle] = useState("");
  const [ingredients, setIngredients] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mealie = week.mealie.configured && !week.mealie.error;

  useEffect(() => {
    if (!mealie) return;
    let live = true;
    const t = window.setTimeout(() => {
      meals.recipes(q).then((r) => live && setFound(r.recipes)).catch((e) => live && setError(e instanceof Error ? e.message : String(e)));
    }, 250);
    return () => { live = false; window.clearTimeout(t); };
  }, [q, mealie]);

  const pick = async (d: { title: string; slug?: string | null; recipe_id?: string | null; ingredients?: string[] }) => {
    setError(null);
    try { onDone(await meals.plan(date, d, start)); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  return (
    <div className="meal-picker stack" style={{ gap: 8 }}>
      {week.often.length > 0 && (
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }} aria-label="Dinners you have often">
          {week.often.map((o) => (
            <button key={o.title} type="button" className="chip chip--button" onClick={() => void pick({ title: o.title, slug: o.slug, recipe_id: o.recipe_id })}>{o.title}</button>
          ))}
        </div>
      )}
      {mealie && (
        <>
          <input className="field" placeholder="Search your Mealie recipes" aria-label="Search your Mealie recipes" value={q} onChange={(e) => setQ(e.target.value)} />
          <ul className="items" aria-label="Recipes">
            {found.slice(0, 8).map((r) => (
              <li key={r.slug} className="item">
                <button type="button" className="item__text link-button" style={{ textAlign: "left" }} onClick={() => void pick({ title: r.name, slug: r.slug, recipe_id: r.id })}>
                  <span className="item__title">{r.name}</span>{r.time && <span className="item__subtitle">{r.time}</span>}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <form className="stack" style={{ gap: 6 }} onSubmit={(e) => {
        e.preventDefault();
        if (title.trim()) void pick({ title: title.trim(), ingredients: ingredients.split(/[,\n]/).map((s) => s.trim()).filter(Boolean) });
      }}>
        <input className="field" placeholder={mealie ? "Or something else (e.g. leftovers)" : "What's for dinner?"} aria-label="Dinner" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} />
        <input className="field" placeholder="Ingredients to buy, with commas (optional)" aria-label="Ingredients" value={ingredients} onChange={(e) => setIngredients(e.target.value)} />
        <div className="row" style={{ gap: 6 }}>
          <button type="submit" className="button button--small" disabled={!title.trim()}>Plan it</button>
          <button type="button" className="button button--small button--ghost" onClick={onCancel}>Cancel</button>
        </div>
      </form>
      {error && <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>{error}</p>}
    </div>
  );
}

function ShoppingCard({ start }: { start: string }) {
  const [s, setS] = useState<Shopping | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [list, setList] = useState<string>("");
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [staples, setStaples] = useState("");

  const load = async () => {
    setBusy(true);
    setNote(null);
    try {
      const out = await meals.shopping(start);
      setS(out);
      setChosen(new Set(out.items.filter((i) => i.need).map((i) => i.key)));
      setList(out.list ?? "");
      setStaples(out.staples.join(", "));
    } catch (e) { setNote(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  const add = async () => {
    if (!s || !list) return;
    const items = s.items.filter((i) => chosen.has(i.key)).map((i) => i.name.charAt(0).toUpperCase() + i.name.slice(1));
    setBusy(true);
    try {
      const out = await meals.addToList(items, list);
      await load();
      setNote(`Added ${out.added} to ${s.lists.find((l) => l.entity_id === list)?.name ?? "the list"}.`);
    } catch (e) { setNote(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };

  return (
    <Glass as="section" className="widget" aria-label="Shopping for the week">
      <header className="widget__head"><ShoppingCart aria-hidden="true" /><span>Shopping for the week</span></header>
      {!s ? (
        <button type="button" className="button button--small" style={{ alignSelf: "flex-start" }} disabled={busy} onClick={() => void load()}>
          {busy ? "Working it out…" : "What do I need?"}
        </button>
      ) : (
        <>
          {s.items.length === 0 && <p className="muted" style={{ margin: 0 }}>No ingredients yet: plan some dinners from Mealie, or add ingredients to your own.</p>}
          <ul className="stack" style={{ gap: 4, padding: 0, listStyle: "none" }}>
            {s.items.map((i) => (
              <li key={i.key}>
                <label className="row" style={{ gap: 8, alignItems: "flex-start" }}>
                  <input type="checkbox" checked={chosen.has(i.key)} onChange={() => {
                    const next = new Set(chosen);
                    if (next.has(i.key)) next.delete(i.key); else next.add(i.key);
                    setChosen(next);
                  }} />
                  <span className="stack" style={{ gap: 0 }}>
                    <span>{i.lines.join("; ")}</span>
                    <span className="muted" style={{ fontSize: 12 }}>
                      For {i.for.join(", ")}{i.staple ? " · you always have this" : ""}{i.on_list ? " · already on the list" : ""}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {s.no_ingredients.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>No ingredients for {s.no_ingredients.join(", ")}.</p>}
          {s.lists.length ? (
            <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
              <select className="field" aria-label="Home Assistant list" value={list} onChange={(e) => setList(e.target.value)} style={{ width: "auto", maxWidth: "100%" }}>
                {s.lists.map((l) => <option key={l.entity_id} value={l.entity_id}>{l.name}</option>)}
              </select>
              <button type="button" className="button button--small" disabled={busy || !chosen.size} onClick={() => void add()}>Add {chosen.size} to the list</button>
            </div>
          ) : <p className="muted" style={{ margin: 0, fontSize: 13 }}>No Home Assistant to-do lists found (through SirisAI).</p>}
          <details>
            <summary className="muted" style={{ fontSize: 13, cursor: "pointer" }}>Things you always have</summary>
            <form className="row" style={{ gap: 6, marginTop: 6 }} onSubmit={async (e) => { e.preventDefault(); await meals.staples(staples.split(",")); await load(); }}>
              <input className="field" aria-label="Things you always have" value={staples} onChange={(e) => setStaples(e.target.value)} style={{ flex: 1, minWidth: 0 }} />
              <button type="submit" className="button button--small">Save</button>
            </form>
          </details>
        </>
      )}
      {note && <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>{note}</p>}
    </Glass>
  );
}

export function MealsScreen() {
  const [start] = useState(() => iso(new Date()));
  const res = useResource(`meals:week:${start}`, () => meals.week(start), {});
  const [picking, setPicking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { document.title = "Meals · SirisOS"; }, []);
  const w = res.data && Array.isArray(res.data.days) ? res.data : undefined;

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">The week's dinners</p>
          <h1 className="page-head__title">Meals</h1>
        </div>
      </header>
      {w && (w.mealie.error
        ? <p className="tone-warning" role="status" style={{ margin: 0 }}>Mealie: {w.mealie.error}</p>
        : !w.mealie.configured && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Connect Mealie (SIRISOS_MEALIE_URL and SIRISOS_MEALIE_TOKEN) to plan from your recipes and its meal plan.</p>)}
      <Glass as="section" className="widget" aria-label="Dinners this week">
        <header className="widget__head"><UtensilsCrossed aria-hidden="true" /><span>Dinners</span>
          {w?.mealie.configured && !w.mealie.error && <span className="widget__source"><ChefHat size={14} aria-hidden="true" /> Mealie</span>}
        </header>
        {!w ? <div aria-busy="true" style={{ minHeight: 120 }} /> : (
          <ul className="stack" style={{ gap: 10, padding: 0, listStyle: "none" }}>
            {w.days.map((d) => (
              <li key={d.date} className="meal-day">
                <div className="row" style={{ justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                  <span className="muted" style={{ fontSize: 13 }}>{d.date === start ? "Tonight" : DAY(d.date)}</span>
                  {d.dinner && (
                    <span className="row" style={{ gap: 4 }}>
                      <button type="button" className="link-button brief-link" style={{ fontSize: 13 }} onClick={() => setPicking(d.date)}>Change</button>
                      <button type="button" className="icon-link" aria-label={`Remove ${d.dinner.title}`} onClick={async () => {
                        try { res.mutate(await meals.unplan(d.date, start)); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
                      }}><Trash2 size={14} aria-hidden="true" /></button>
                    </span>
                  )}
                </div>
                {d.dinner ? (
                  <div className="row" style={{ gap: 6 }}>
                    <strong>{d.dinner.title}</strong>
                    {d.dinner.url && <a href={d.dinner.url} target="_blank" rel="noreferrer" className="icon-link" aria-label={`${d.dinner.title} in Mealie`}><ExternalLink size={14} aria-hidden="true" /></a>}
                  </div>
                ) : picking !== d.date && (
                  <button type="button" className="button button--small button--ghost" style={{ alignSelf: "flex-start" }} onClick={() => setPicking(d.date)}>Plan dinner</button>
                )}
                {picking === d.date && (
                  <Picker week={w} date={d.date} start={start} onCancel={() => setPicking(null)} onDone={(next) => { res.mutate(next); setPicking(null); }} />
                )}
              </li>
            ))}
          </ul>
        )}
        {error && <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>{error}</p>}
      </Glass>
      <ShoppingCard start={start} />
    </div>
  );
}

/** Home (10.2): tonight's dinner, from midday, when one's planned. */
export function TonightCard() {
  const res = useResource("meals:tonight", () => meals.tonight(), { staleMs: 30 * 60_000, persist: true });
  const dinner = res.data?.dinner;
  if (!dinner || new Date().getHours() < 12) return null;
  return (
    <Glass as="section" className="widget" aria-label="Dinner tonight">
      <header className="widget__head"><UtensilsCrossed aria-hidden="true" /><span>Dinner tonight</span><Link to="/meals" className="widget__source">Meals</Link></header>
      <p style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>{dinner.title}</p>
    </Glass>
  );
}
