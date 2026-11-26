import { useEffect, useMemo, useState } from "react";
import { BookOpen, Check, Copy, Pencil, Plus, Search, Trash2, TriangleAlert } from "lucide-react";
import { useResource } from "../api/resource";
import { handbook, type HandbookEntry } from "../api/handbook";
import { HANDBOOK, type Command } from "../data/handbook";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";

/** The Server handbook (11.9): Linux, Docker and server commands worth keeping, to search and copy, and your own. */
export function HandbookScreen() {
  const res = useResource<{ entries: HandbookEntry[] }>("handbook", () => handbook.list(), { staleMs: 60_000, persist: true });
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [adding, setAdding] = useState(false);
  useEffect(() => { document.title = "Handbook · SirisOS"; }, []);
  const mine = res.data?.entries ?? [];
  const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const hit = (c: { cmd: string; what: string }) => words.every((w) => `${c.cmd} ${c.what}`.toLowerCase().includes(w));
  const sections = useMemo(() => {
    const own = Object.entries(mine.reduce<Record<string, HandbookEntry[]>>((g, e) => ({ ...g, [e.section || "Mine"]: [...(g[e.section || "Mine"] ?? []), e] }), {}));
    return [
      ...own.map(([title, entries]) => ({ title, about: "Yours, kept on the server.", mine: true, commands: entries as (Command & Partial<HandbookEntry>)[] })),
      ...HANDBOOK.map((s) => ({ ...s, mine: false, commands: s.commands as (Command & Partial<HandbookEntry>)[] })),
    ];
  }, [mine]);
  const shown = sections.map((s) => ({ ...s, commands: s.commands.filter(hit) })).filter((s) => s.commands.length);
  const toggle = (t: string) => setOpen((o) => { const n = new Set(o); if (n.has(t)) n.delete(t); else n.add(t); return n; });
  return (
    <>
      <PageHead eyebrow={`${HANDBOOK.reduce((n, s) => n + s.commands.length, 0) + mine.length} commands`} title="Handbook" />
      <div className="stack" style={{ marginTop: 16 }}>
        <label className="row handbook-search" style={{ gap: 8 }}>
          <Search size={16} aria-hidden="true" />
          <input className="field" type="search" placeholder="Search: disk, logs, restart, gpu…" aria-label="Search the handbook" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <button type="button" className="chip chip--button" onClick={() => setAdding(!adding)} aria-expanded={adding}><Plus size={12} aria-hidden="true" /> Add your own</button>
          <span className="muted" style={{ fontSize: 12 }}>Words in &lt;angle brackets&gt; are yours to fill in.</span>
        </div>
        {adding && <EntryForm onDone={(next) => { if (next) res.mutate?.({ entries: next }); setAdding(false); }} />}
        {!shown.length && <p className="muted">Nothing matches "{q}".</p>}
        {shown.map((s) => {
          const isOpen = words.length > 0 || open.has(s.title);
          return (
            <Glass key={s.title} as="section" className="widget" style={{ minHeight: 0 }} aria-label={s.title}>
              <button type="button" className="widget__head handbook-head" aria-expanded={isOpen} onClick={() => toggle(s.title)}>
                <BookOpen aria-hidden="true" /><span>{s.title}</span><span className="widget__source">{s.commands.length}</span></button>
              {isOpen && (
                <>
                  <p className="muted" style={{ margin: 0, fontSize: 13 }}>{s.about}</p>
                  <ul className="items handbook-list">
                    {s.commands.map((c) => <CommandRow key={c.id ?? c.cmd} c={c} mine={s.mine} onChanged={(next) => res.mutate?.({ entries: next })} />)}
                  </ul>
                </>
              )}
            </Glass>
          );
        })}
      </div>
    </>
  );
}

function CommandRow({ c, mine, onChanged }: { c: Command & Partial<HandbookEntry>; mine: boolean; onChanged: (e: HandbookEntry[]) => void }) {
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(c.cmd); setCopied(true); window.setTimeout(() => setCopied(false), 1500); } catch { /* no clipboard: long-press the text */ }
  };
  if (editing && c.id) return <li className="item"><EntryForm entry={c as HandbookEntry} onDone={(next) => { if (next) onChanged(next); setEditing(false); }} /></li>;
  return (
    <li className="item handbook-row">
      <span className="item__text">
        <code className="handbook-cmd">{c.cmd}</code>
        <span className="item__subtitle" style={{ whiteSpace: "normal" }}>
          {c.danger && <><TriangleAlert size={12} className="tone-warning" aria-label="Careful" /> </>}{c.what}</span>
      </span>
      <span className="row" style={{ gap: 4 }}>
        <button type="button" className="icon-link" aria-label={`Copy ${c.cmd}`} onClick={copy}>{copied ? <Check size={16} className="tone-good" aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}</button>
        {mine && c.id && (
          <>
            <button type="button" className="icon-link" aria-label={`Edit ${c.cmd}`} onClick={() => setEditing(true)}><Pencil size={14} aria-hidden="true" /></button>
            <button type="button" className="icon-link" aria-label={`Delete ${c.cmd}`}
              onClick={async () => { if (window.confirm(`Take "${c.cmd}" out of the handbook?`)) onChanged((await handbook.remove(c.id!)).entries); }}><Trash2 size={14} aria-hidden="true" /></button>
          </>
        )}
      </span>
    </li>
  );
}

function EntryForm({ entry, onDone }: { entry?: HandbookEntry; onDone: (entries: HandbookEntry[] | null) => void }) {
  const [cmd, setCmd] = useState(entry?.cmd ?? "");
  const [what, setWhat] = useState(entry?.what ?? "");
  const [section, setSection] = useState(entry?.section ?? "Mine");
  const [msg, setMsg] = useState<string | null>(null);
  const save = async () => {
    setMsg(null);
    try {
      onDone((entry ? await handbook.change(entry.id, { cmd: cmd.trim(), what: what.trim(), section: section.trim() || "Mine" })
        : await handbook.add({ cmd: cmd.trim(), what: what.trim(), section: section.trim() || "Mine" })).entries);
    } catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't save it."); }
  };
  return (
    <form className="stack" style={{ gap: 6, width: "100%" }} aria-label={entry ? "Edit command" : "Add a command"} onSubmit={(e) => { e.preventDefault(); if (cmd.trim()) void save(); }}>
      <textarea className="field handbook-cmd" rows={2} placeholder="The command" aria-label="Command" value={cmd} onChange={(e) => setCmd(e.target.value)} />
      <input className="field" placeholder="What it does" aria-label="What it does" value={what} maxLength={300} onChange={(e) => setWhat(e.target.value)} />
      <input className="field" placeholder="Section (Mine)" aria-label="Section" value={section} maxLength={40} onChange={(e) => setSection(e.target.value)} />
      {msg && <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
      <span className="row" style={{ gap: 8 }}>
        <button type="submit" className="button button--primary button--small" disabled={!cmd.trim()}>Save</button>
        <button type="button" className="button button--small" onClick={() => onDone(null)}>Cancel</button>
      </span>
    </form>
  );
}
