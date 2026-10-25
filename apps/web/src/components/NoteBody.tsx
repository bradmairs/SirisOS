import { Fragment, type ReactNode } from "react";

/**
 * A Second Brain note's Markdown as React elements (never raw HTML): headings, paragraphs,
 * bullet, numbered and task lists, quotes, code, simple tables, **bold**, *italic*, `code`,
 * [[wiki links]] (which open that note through `onOpen`) and [links](https://...).
 * Embedded files (![[photo.jpg]]) show as a mention: they live in the vault.
 */
export function NoteBody({ text, onOpen }: { text: string; onOpen?: (title: string) => void }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  const key = () => out.length;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (line.startsWith("```")) {
      const code: string[] = [];
      for (i++; i < lines.length && !lines[i].startsWith("```"); i++) code.push(lines[i]);
      i++;
      out.push(<pre key={key()} className="note__code">{code.join("\n")}</pre>);
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      const level = Math.min(6, heading[1].length + 2);
      const H = `h${level}` as "h3";
      out.push(<H key={key()} className="note__heading">{inline(heading[2], onOpen)}</H>);
      i++;
      continue;
    }
    if (/^\s*>/.test(line)) {
      const quote: string[] = [];
      for (; i < lines.length && /^\s*>/.test(lines[i]); i++) quote.push(lines[i].replace(/^\s*>\s?/, ""));
      out.push(<blockquote key={key()} className="note__quote">{inline(quote.join(" "), onOpen)}</blockquote>);
      continue;
    }
    if (/^\s*\|/.test(line)) {
      const rows: string[][] = [];
      for (; i < lines.length && /^\s*\|/.test(lines[i]); i++) {
        const cells = lines[i].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        if (!cells.every((c) => /^:?-{2,}:?$/.test(c))) rows.push(cells);
      }
      out.push(
        <div key={key()} className="note__table-wrap">
          <table className="note__table"><tbody>
            {rows.map((r, ri) => <tr key={ri}>{r.map((c, ci) => (ri === 0 ? <th key={ci}>{inline(c, onOpen)}</th> : <td key={ci}>{inline(c, onOpen)}</td>))}</tr>)}
          </tbody></table>
        </div>,
      );
      continue;
    }
    if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const items: ReactNode[] = [];
      for (; i < lines.length && /^\s*([-*+]|\d+[.)])\s+/.test(lines[i]); i++) {
        const item = lines[i].replace(/^\s*([-*+]|\d+[.)])\s+/, "");
        const task = /^\[([ xX])\]\s*(.*)$/.exec(item);
        const nested = /^\s{2,}/.test(lines[i]);
        items.push(
          <li key={i} className={`${task ? "note__task" : ""}${nested ? " note__nested" : ""}`.trim() || undefined}>
            {task ? <><input type="checkbox" checked={task[1] !== " "} readOnly tabIndex={-1} aria-label={task[1] !== " " ? "Done" : "Not done"} /> {inline(task[2], onOpen)}</> : inline(item, onOpen)}
          </li>,
        );
      }
      out.push(ordered ? <ol key={key()} className="note__list">{items}</ol> : <ul key={key()} className="note__list">{items}</ul>);
      continue;
    }
    const para: string[] = [];
    for (; i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|\s*>|\s*\||\s*([-*+]|\d+[.)])\s+)/.test(lines[i]); i++) para.push(lines[i].trim());
    out.push(<p key={key()} className="note__p">{inline(para.join(" "), onOpen)}</p>);
  }
  return <div className="note">{out}</div>;
}

const TOKEN = /(!\[\[[^\]]+\]\]|\[\[[^\]]+\]\]|\[[^\]]+\]\((?:https?:\/\/|mailto:)[^)\s]+\)|`[^`]+`|\*\*[^*]+\*\*|\*[^*\s][^*]*\*|_[^_\s][^_]*_)/;

function inline(text: string, onOpen?: (title: string) => void): ReactNode {
  return text.split(TOKEN).map((part, i) => {
    if (!part) return null;
    if (part.startsWith("![[")) return <span key={i} className="muted">📎 {part.slice(3, -2).split("|")[0].split("/").pop()}</span>;
    if (part.startsWith("[[")) {
      const [target, shown] = part.slice(2, -2).split("|");
      const title = target.split("#")[0].trim();
      const label = (shown ?? target).trim();
      return onOpen ? <button key={i} type="button" className="note__link" onClick={() => onOpen(title)}>{label}</button> : <Fragment key={i}>{label}</Fragment>;
    }
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part);
    if (link) return <a key={i} href={link[2]} target="_blank" rel="noreferrer noopener">{link[1]}</a>;
    if (part.startsWith("`")) return <code key={i}>{part.slice(1, -1)}</code>;
    if (part.startsWith("**")) return <strong key={i}>{inline(part.slice(2, -2), onOpen)}</strong>;
    if (part.startsWith("*") || part.startsWith("_")) return <em key={i}>{inline(part.slice(1, -1), onOpen)}</em>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}
