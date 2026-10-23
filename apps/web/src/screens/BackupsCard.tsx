import { useState } from "react";
import { Archive, Download, RotateCcw, Save } from "lucide-react";
import { useResource } from "../api/resource";
import { backups, type Backup } from "../api/backups";
import { Glass } from "../components/Glass";
import { useShowMore } from "../components/ShowMore";

const KIND: Record<Backup["kind"], string> = { nightly: "Nightly", manual: "Made by hand", "before-restore": "Before a restore" };

function size(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function stamp(iso: string) {
  return new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

/** SirisOS's own data, backed up every night, with one-tap restore (3.7). */
export function BackupsCard() {
  const { data, reload } = useResource("backups", () => backups.list(), { staleMs: 60_000 });
  const [busy, setBusy] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [note, setNote] = useState<{ tone: "good" | "critical"; text: string } | null>(null);
  const { shown, toggle } = useShowMore(data?.backups ?? []);
  if (!data) return null;

  async function run(key: string, work: () => Promise<string>) {
    setBusy(key);
    setNote(null);
    try {
      setNote({ tone: "good", text: await work() });
      await reload(true);
    } catch (e) {
      setNote({ tone: "critical", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(null);
      setConfirm(null);
    }
  }

  const hour = new Date(2000, 0, 1, data.nightly_hour).toLocaleTimeString(undefined, { hour: "numeric" });
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="SirisOS backups">
      <header className="widget__head"><Archive aria-hidden="true" /><span>SirisOS backups</span>
        <button type="button" className="button button--small" style={{ marginLeft: "auto" }} disabled={busy !== null}
          onClick={() => run("now", async () => `Backed up ${(await backups.create()).files} files.`)}>
          <Save size={14} aria-hidden="true" /> {busy === "now" ? "Backing up…" : "Back up now"}
        </button>
      </header>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>
        Tasks, journal, reviews, career and CPD, Home layout, links, keys and settings: {data.enabled ? `every night after ${hour}` : "nightly backups are off"}, to <code>{data.folder}</code>.
      </p>
      {data.error && <p className="tone-critical" role="alert" style={{ margin: 0 }}>The last backup failed: {data.error}</p>}
      {!data.error && data.stale && data.newest && <p className="tone-warning" style={{ margin: 0 }}>The newest backup is over a day old.</p>}
      {data.backups.length === 0 ? (
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>None yet.</p>
      ) : (
        <ul className="items">
          {shown.map((b) => (
            <li key={b.name} className="item">
              <span className="item__text">
                <div className="item__title">{stamp(b.created)}</div>
                <div className="item__subtitle">{KIND[b.kind]} · {size(b.bytes)}</div>
              </span>
              {confirm === b.name ? (
                <span className="row" style={{ gap: 6 }}>
                  <button type="button" className="button button--small button--primary" disabled={busy !== null}
                    onClick={() => run(b.name, async () => { const r = await backups.restore(b.name); return `Put back ${r.restored} files. What was there before is saved as a "Before a restore" backup.`; })}>
                    {busy === b.name ? "Restoring…" : "Restore"}
                  </button>
                  <button type="button" className="button button--small" onClick={() => setConfirm(null)}>Cancel</button>
                </span>
              ) : (
                <span className="row" style={{ gap: 2 }}>
                  <button type="button" className="icon-link" aria-label={`Download the backup from ${stamp(b.created)}`} onClick={() => backups.download(b.name).catch(() => undefined)}><Download size={15} aria-hidden="true" /></button>
                  <button type="button" className="icon-link" aria-label={`Restore the backup from ${stamp(b.created)}`} onClick={() => setConfirm(b.name)}><RotateCcw size={15} aria-hidden="true" /></button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {toggle}
      {confirm && <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>Restoring puts every file in that backup back. Anything changed since is saved first, so you can undo it.</p>}
      {note && <p className={`tone-${note.tone}`} role="status" style={{ margin: 0, fontSize: 14 }}>{note.text}</p>}
    </Glass>
  );
}
