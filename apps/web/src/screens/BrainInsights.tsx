import { useState } from "react";
import { CalendarClock, Check, Hourglass, Link2, Sparkles, TrendingUp, Unlink, WandSparkles, X } from "lucide-react";
import { brain } from "../api/hub";
import { useResource } from "../api/resource";
import type { BrainInsights as Insights } from "../api/types";
import { Glass } from "../components/Glass";

const dayLabel = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Notes touched per day: one series, so no legend; the readout above it is the hover layer. */
function ActivityChart({ activity }: { activity: Insights["activity"] }) {
  const [active, setActive] = useState<number | null>(null);
  const peak = Math.max(1, ...activity.map((a) => a.notes));
  const total = activity.reduce((sum, a) => sum + a.notes, 0);
  const shown = active === null ? null : activity[active];
  return (
    <figure className="activity">
      <figcaption className="activity__readout" aria-live="polite">
        {shown
          ? `${dayLabel(shown.date)} · ${plural(shown.notes, "note")}`
          : `Last ${activity.length} days · ${plural(total, "note update")}`}
      </figcaption>
      <div className="activity__bars" aria-hidden="true" onPointerLeave={() => setActive(null)}>
        {activity.map((a, i) => (
          <div key={a.date} className={`activity__slot${active === i ? " activity__slot--active" : ""}`} onPointerEnter={() => setActive(i)}>
            {a.notes > 0 ? (
              <span className="activity__bar" style={{ height: `${Math.max(6, (a.notes / peak) * 100)}%` }} />
            ) : (
              <span className="activity__tick" />
            )}
          </div>
        ))}
      </div>
      <div className="activity__axis" aria-hidden="true">
        <span>{dayLabel(activity[0].date)}</span>
        <span>Today</span>
      </div>
      <table className="sr-only">
        <caption>Notes learned or updated per day</caption>
        <tbody>
          {activity.map((a) => (
            <tr key={a.date}>
              <th scope="row">{a.date}</th>
              <td>{a.notes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

function List({ items }: { items: { key: string; title: string; subtitle: string; tone?: "warning" | "critical" }[] }) {
  return (
    <ul className="items insights__list">
      {items.map((item) => (
        <li key={item.key} className="item">
          <span className={`item__dot${item.tone ? ` dot-${item.tone}` : ""}`} style={item.tone ? undefined : { background: "var(--brain)" }} aria-hidden="true" />
          <span className="item__text">
            <div className="item__title">{item.title}</div>
            <div className="item__subtitle">{item.subtitle}</div>
          </span>
        </li>
      ))}
    </ul>
  );
}

type Pair = Insights["suggested_links"][number];

/** "Could be linked": link the two notes, or say they aren't related. Either way the
 *  suggestion goes, and the list refreshes so the next best one moves up. */
function SuggestedLinks({ pairs, done, onDone }: { pairs: Pair[]; done: string | null; onDone: (pair: Pair, text: string) => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function act(pair: Pair, kind: "link" | "unrelate") {
    const key = `${pair.a}|${pair.b}`;
    setBusy(key);
    setErrors((e) => ({ ...e, [key]: "" }));
    try {
      if (kind === "link") await brain.link(pair.a, pair.b);
      else await brain.notRelated(pair.a, pair.b);
      onDone(pair, kind === "link" ? `Linked ${pair.a} and ${pair.b}` : `Won't suggest ${pair.a} and ${pair.b} again`);
    } catch (err) {
      setErrors((e) => ({ ...e, [key]: err instanceof Error ? err.message : "That didn't work." }));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      {done && (
        <p className="tone-good suggest__done" role="status">
          <Check size={14} aria-hidden="true" /> {done}
        </p>
      )}
      {pairs.length === 0 && <p className="muted" style={{ margin: 0 }}>No more suggestions for now.</p>}
      <ul className="items insights__list">
        {pairs.map((p) => {
          const key = `${p.a}|${p.b}`;
          return (
            <li key={key} className="item suggest">
              <span className="item__dot" style={{ background: "var(--brain)" }} aria-hidden="true" />
              <span className="item__text">
                <div className="item__title">{p.a} ↔ {p.b}</div>
                <div className="item__subtitle">{errors[key] ? <span className="tone-critical">{errors[key]}</span> : p.why}</div>
              </span>
              <span className="suggest__actions">
                <button type="button" className="chip chip--button suggest__link" disabled={busy !== null}
                  onClick={() => act(p, "link")} aria-label={`Link ${p.a} and ${p.b}`}>
                  <Link2 size={13} aria-hidden="true" /> {busy === key ? "…" : "Link"}
                </button>
                <button type="button" className="icon-link" disabled={busy !== null}
                  onClick={() => act(p, "unrelate")} aria-label={`${p.a} and ${p.b} aren't related`} title="Not related">
                  <X size={15} aria-hidden="true" />
                </button>
              </span>
            </li>
          );
        })}
      </ul>
    </>
  );
}

type Thresholds = NonNullable<Insights["link_thresholds"]>;

/** How auto-linking is set, in a sentence: "Siris links pairs that are 80% alike or more…". */
export function thresholdSentence(t: Thresholds | undefined): string {
  if (!t) return "";
  if (t.auto_min === null) {
    return t.basis === "auto-linking turned off"
      ? "Auto-linking is turned off; every pair waits for you."
      : "Without meaning-based similarity, Siris only suggests links.";
  }
  const pct = Math.round(t.auto_min * 100);
  const why =
    t.basis === "calibrated"
      ? `tuned from your ${t.decisions.linked + t.decisions.not_related} link decisions`
      : t.basis === "raised above a rejected pair"
        ? "raised above a pair you said wasn't related"
        : "the starting point; it tunes itself as you decide on suggestions";
  return `Siris links notes that are ${pct}% alike or more by itself (${why}).`;
}


/** Links Siris made on its own: glance over them, and undo any that are wrong. Undoing
 *  unlinks both notes and stops Siris from ever linking them again. */
function AutoLinks({ data, onChanged }: { data: Insights; onChanged: (text: string) => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pairs = data.auto_linked ?? [];
  const pending = data.pending_auto_links ?? 0;

  async function run(key: string, fn: () => Promise<string>) {
    setBusy(key);
    setError(null);
    try {
      onChanged(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <p className="muted suggest__hint">{thresholdSentence(data.link_thresholds)}</p>
      {pending > 0 && (
        <div className="row suggest__pending">
          <span className="item__text">{plural(pending, "confident link")} waiting for tonight's tidy.</span>
          <button type="button" className="chip chip--button suggest__link" disabled={busy !== null}
            onClick={() => run("all", async () => {
              const r = await brain.autolink();
              return `Linked ${plural(r.linked.length, "pair")} of notes${r.deferred ? `, ${r.deferred} more next time` : ""}`;
            })}>
            <WandSparkles size={13} aria-hidden="true" /> {busy === "all" ? "…" : "Link now"}
          </button>
        </div>
      )}
      {error && <p className="tone-critical" style={{ margin: 0 }}>{error}</p>}
      {pairs.length === 0 ? (
        pending === 0 && <p className="muted" style={{ margin: 0 }}>Nothing linked automatically in the last two weeks.</p>
      ) : (
        <ul className="items insights__list">
          {pairs.map((p) => {
            const key = `${p.a}|${p.b}`;
            return (
              <li key={key} className="item suggest">
                <span className="item__dot" style={{ background: "var(--brain)" }} aria-hidden="true" />
                <span className="item__text">
                  <div className="item__title">{p.a} ↔ {p.b}</div>
                  <div className="item__subtitle">{p.confidence ? `${p.confidence}% match · ` : ""}{dayLabel(p.date)}</div>
                </span>
                <span className="suggest__actions">
                  <button type="button" className="chip chip--button" disabled={busy !== null}
                    onClick={() => run(key, async () => {
                      await brain.unlink(p.a, p.b);
                      return `Unlinked ${p.a} and ${p.b}; Siris won't link them again`;
                    })}
                    aria-label={`Unlink ${p.a} and ${p.b}`}>
                    <Unlink size={13} aria-hidden="true" /> {busy === key ? "…" : "Unlink"}
                  </button>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}

export function BrainInsights() {
  // Insights scan the whole vault, so keep the last result for a few minutes.
  const res = useResource<Insights>("brain:insights", () => brain.insights(), { staleMs: 300_000 });
  const data = res.data ?? null;
  const { mutate, reload } = res;
  const [linkDone, setLinkDone] = useState<string | null>(null);
  const error = data ? null : res.error;

  if (error) {
    return (
      <Glass className="widget" style={{ marginTop: 14 }}>
        <div className="widget__head">Insights</div>
        <p className="muted" style={{ margin: 0 }}>{error}</p>
      </Glass>
    );
  }
  if (!data) return <div className="skeleton" style={{ height: 120, marginTop: 14 }} aria-label="Loading insights" />;

  const s = data.summary;
  const trend = s.this_week - s.previous_week;
  const upcoming = [
    ...data.overdue_tasks.map((t) => ({
      key: `task-${t.note}-${t.task}`, title: t.task, tone: "critical" as const,
      subtitle: `${t.note} · ${t.days_late === 1 ? "1 day" : `${t.days_late} days`} late`,
    })),
    ...data.deadlines.map((d) => ({
      key: `due-${d.title}`, title: d.title, tone: d.days_left < 0 ? ("critical" as const) : d.days_left <= 7 ? ("warning" as const) : undefined,
      subtitle: d.days_left < 0 ? `Was due ${dayLabel(d.due)}` : d.days_left === 0 ? "Due today" : `Due ${dayLabel(d.due)} · in ${plural(d.days_left, "day")}`,
    })),
  ];

  return (
    <section aria-labelledby="insights-title">
      <h2 id="insights-title" className="section-title">Insights</h2>
      <div className="widget-grid">
        <Glass className="widget">
          <div className="widget__head">
            <Sparkles style={{ color: "var(--brain)" }} aria-hidden="true" /> What the brain noticed
          </div>
          <ul className="insights__highlights">
            {data.highlights.map((h) => <li key={h}>{h}</li>)}
          </ul>
        </Glass>

        <Glass className="widget">
          <div className="metrics">
            <div>
              <div className="metric__value">{s.this_week}</div>
              <div className="metric__label">
                This week{s.previous_week || trend ? ` · ${trend >= 0 ? "+" : "−"}${Math.abs(trend)} vs last` : ""}
              </div>
            </div>
            <div>
              <div className="metric__value">{s.streak_days}</div>
              <div className="metric__label">Day streak</div>
            </div>
            <div>
              <div className="metric__value">{s.notes}</div>
              <div className="metric__label">Notes · {s.links_per_note} links each</div>
            </div>
            <div>
              <div className="metric__value">{s.open_tasks}</div>
              <div className="metric__label">Open tasks</div>
            </div>
          </div>
          {data.activity.length > 0 && <ActivityChart activity={data.activity} />}
        </Glass>

        {upcoming.length > 0 && (
          <Glass className="widget">
            <div className="widget__head"><CalendarClock aria-hidden="true" /> Coming up</div>
            <List items={upcoming} />
          </Glass>
        )}

        {(data.stale_projects.length > 0 || (data.inbox.count > 0 && data.inbox.oldest)) && (
          <Glass className="widget">
            <div className="widget__head"><Hourglass aria-hidden="true" /> Going quiet</div>
            <List
              items={[
                ...data.stale_projects.map((p) => ({ key: p.title, title: p.title, subtitle: `Untouched for ${p.days_idle} days` })),
                ...(data.inbox.count > 0 && data.inbox.oldest
                  ? [{ key: "inbox", title: `Inbox: ${plural(data.inbox.count, "item")}`, subtitle: `Oldest from ${dayLabel(data.inbox.oldest)}` }]
                  : []),
              ]}
            />
          </Glass>
        )}

        {(data.link_thresholds || (data.auto_linked?.length ?? 0) > 0) && (
          <Glass className="widget">
            <div className="widget__head"><WandSparkles style={{ color: "var(--brain)" }} aria-hidden="true" /> Linked automatically</div>
            <AutoLinks
              data={data}
              onChanged={(text) => {
                setLinkDone(text);
                reload(true).catch(() => undefined);
              }}
            />
          </Glass>
        )}

        {(data.suggested_links.length > 0 || linkDone) && (
          <Glass className="widget">
            <div className="widget__head"><Link2 aria-hidden="true" /> Could be linked: your call</div>
            <SuggestedLinks
              pairs={data.suggested_links}
              done={linkDone}
              onDone={(pair, text) => {
                setLinkDone(text);
                mutate({ ...data, suggested_links: data.suggested_links.filter((p) => p !== pair) });
                reload(true).catch(() => undefined);
              }}
            />
          </Glass>
        )}

        {data.topics.length > 0 && (
          <Glass className="widget">
            <div className="widget__head"><TrendingUp aria-hidden="true" /> Topics, last two weeks</div>
            <div className="insights__topics">
              {data.topics.map((t) => (
                <span key={t.tag} className="chip">
                  #{t.tag} <span className="muted">{t.notes}{t.notes > t.previous ? ` · +${t.notes - t.previous}` : ""}</span>
                </span>
              ))}
            </div>
          </Glass>
        )}
      </div>
    </section>
  );
}
