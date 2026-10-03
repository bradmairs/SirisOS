import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Check, Pencil, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { links as api, newId, type LinkGroup, type LinkItem, type LinkStatus, type LinksDocument } from "../api/links";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";

const STATUS_REFRESH_MS = 60_000;

/** The launchpad for every self-hosted app: SirisOS's replacement for Homarr. */
export function Links() {
  const [doc, setDoc] = useState<LinksDocument | null>(null);
  const [status, setStatus] = useState<Record<string, LinkStatus>>({});
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<{ link: LinkItem; group: string; isNew: boolean } | null>(null);

  const loadStatus = useCallback(() => {
    api.status().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    api.get().then(setDoc).catch((err) => setError(err instanceof Error ? err.message : "Couldn't load links."));
    loadStatus();
    const timer = window.setInterval(() => document.visibilityState === "visible" && loadStatus(), STATUS_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [loadStatus]);

  const groups = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!doc) return [];
    if (!term) return doc.groups;
    return doc.groups
      .map((g) => ({ ...g, links: g.links.filter((l) => `${l.name} ${l.url} ${l.note ?? ""} ${g.name}`.toLowerCase().includes(term)) }))
      .filter((g) => g.links.length > 0);
  }, [doc, q]);

  const total = doc?.groups.reduce((n, g) => n + g.links.length, 0) ?? 0;
  const up = Object.values(status).filter((s) => s.up).length;

  async function persist(next: LinksDocument) {
    setDoc(next);
    try {
      setDoc(await api.save(next));
      setError(null);
      loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save links.");
    }
  }

  function saveLink(link: LinkItem, groupName: string) {
    if (!doc) return;
    const name = groupName.trim() || "Other";
    let found = false;
    const groupsOut: LinkGroup[] = doc.groups.map((g) => ({ ...g, links: g.links.filter((l) => l.id !== link.id) }));
    for (const g of groupsOut) {
      if (g.name.toLowerCase() === name.toLowerCase()) {
        const original = doc.groups.find((og) => og.id === g.id)?.links.findIndex((l) => l.id === link.id) ?? -1;
        if (original >= 0) g.links.splice(original, 0, link);
        else g.links.push(link);
        found = true;
      }
    }
    if (!found) groupsOut.push({ id: newId(), name, links: [link] });
    persist({ ...doc, groups: groupsOut.filter((g) => g.links.length > 0) });
    setForm(null);
  }

  function removeLink(id: string) {
    if (!doc) return;
    persist({ ...doc, groups: doc.groups.map((g) => ({ ...g, links: g.links.filter((l) => l.id !== id) })).filter((g) => g.links.length > 0) });
    setForm(null);
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">Homelab</p>
          <h1 className="page-head__title">Links</h1>
        </div>
        <div className="row">
          <Glass as="button" shape="pill" interactive className="button button--icon" onClick={loadStatus} aria-label="Check status">
            <RefreshCw aria-hidden="true" />
          </Glass>
          <Glass
            as="button"
            shape="pill"
            variant={editing ? "tint" : "regular"}
            interactive
            className="button button--icon"
            onClick={() => setEditing((e) => !e)}
            aria-label={editing ? "Done editing" : "Edit links"}
            aria-pressed={editing}
          >
            {editing ? <Check aria-hidden="true" /> : <Pencil aria-hidden="true" />}
          </Glass>
        </div>
      </header>

      <Glass as="label" shape="pill" className="ask-bar" htmlFor="links-search">
        <Search aria-hidden="true" />
        <input id="links-search" className="ask-bar__input" placeholder="Find an app" value={q} onChange={(e) => setQ(e.target.value)} />
      </Glass>

      {error && <div className="error-banner" role="alert" style={{ marginTop: 16 }}>{error}</div>}

      {doc && (
        <p className="muted links-summary">
          {total} links{Object.keys(status).length > 0 && ` · ${up} up`}
          {editing && " · tap a link to edit it"}
        </p>
      )}

      {doc === null && !error ? (
        <div className="links-grid" style={{ marginTop: 22 }}>
          {Array.from({ length: 8 }, (_, i) => <div key={i} className="skeleton" style={{ height: 64, borderRadius: 18 }} />)}
        </div>
      ) : (
        groups.map((g) => (
          <section key={g.id} aria-label={g.name}>
            <h2 className="section-title">{g.name}</h2>
            <div className="links-grid">
              {g.links.map((l) => (
                <LinkTile key={l.id} link={l} status={status[l.id]} editing={editing} onEdit={() => setForm({ link: l, group: g.name, isNew: false })} />
              ))}
            </div>
          </section>
        ))
      )}

      {doc && groups.length === 0 && <p className="muted" style={{ marginTop: 24 }}>{q ? "No apps match." : "No links yet."}</p>}

      {editing && doc && (
        <Glass
          as="button"
          shape="pill"
          interactive
          className="button links-add"
          onClick={() => setForm({ link: { id: newId(), name: "", url: "https://", icon: "", note: "" }, group: doc.groups[0]?.name ?? "Other", isNew: true })}
        >
          <Plus aria-hidden="true" /> Add link
        </Glass>
      )}

      {form && doc && (
        <LinkForm
          initial={form}
          groups={doc.groups.map((g) => g.name)}
          onCancel={() => setForm(null)}
          onSave={saveLink}
          onDelete={form.isNew ? undefined : () => removeLink(form.link.id)}
        />
      )}
    </>
  );
}

function host(url: string) {
  try {
    const u = new URL(url);
    return u.port ? `${u.hostname}:${u.port}` : u.hostname;
  } catch {
    return url;
  }
}

function LinkTile({ link, status, editing, onEdit }: { link: LinkItem; status?: LinkStatus; editing: boolean; onEdit: () => void }) {
  const [broken, setBroken] = useState(false);
  const state = status === undefined ? "unknown" : status.up ? "up" : "down";
  const label = `${link.name}: ${state === "unknown" ? "checking" : state}`;
  const body = (
    <>
      <span className="link-tile__icon" aria-hidden="true">
        {link.icon && !broken ? <img src={link.icon} alt="" loading="lazy" onError={() => setBroken(true)} /> : <span>{link.name.charAt(0).toUpperCase()}</span>}
      </span>
      <span className="link-tile__text">
        <span className="link-tile__name">{link.name}</span>
        <span className="link-tile__host">{link.note ? `${link.note} · ${host(link.url)}` : host(link.url)}</span>
      </span>
      <span className={`link-tile__dot link-tile__dot--${state}`} title={status?.up ? `Up${status.ms != null ? ` · ${status.ms} ms` : ""}` : status ? "Not responding" : "Checking"} />
    </>
  );
  return editing ? (
    <Glass as="button" type="button" interactive className="link-tile link-tile--editing" onClick={onEdit} aria-label={`Edit ${link.name}`}>
      {body}
    </Glass>
  ) : (
    <Glass as="a" interactive className="link-tile" href={link.url} target="_blank" rel="noreferrer" aria-label={label}>
      {body}
    </Glass>
  );
}

function LinkForm({
  initial,
  groups,
  onCancel,
  onSave,
  onDelete,
}: {
  initial: { link: LinkItem; group: string; isNew: boolean };
  groups: string[];
  onCancel: () => void;
  onSave: (link: LinkItem, group: string) => void;
  onDelete?: () => void;
}) {
  const [link, setLink] = useState(initial.link);
  const [group, setGroup] = useState(initial.group);
  const valid = link.name.trim() && /^https?:\/\/[^\s/]+/i.test(link.url.trim());

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    onSave({ ...link, name: link.name.trim(), url: link.url.trim(), icon: link.icon?.trim() || null, note: link.note?.trim() ?? "" }, group);
  }

  return (
    <Sheet label={initial.isNew ? "Add link" : `Edit ${initial.link.name}`} onClose={onCancel}>
      <form className="stack" onSubmit={submit}>
        <h2 className="app-sheet__name">{initial.isNew ? "Add link" : "Edit link"}</h2>
        <label className="calc-field">
          Name
          <input className="field" value={link.name} onChange={(e) => setLink({ ...link, name: e.target.value })} required />
        </label>
        <label className="calc-field">
          Address
          <input className="field" type="url" value={link.url} onChange={(e) => setLink({ ...link, url: e.target.value })} required />
        </label>
        <label className="calc-field">
          Group
          <input className="field" list="link-groups" value={group} onChange={(e) => setGroup(e.target.value)} />
          <datalist id="link-groups">
            {groups.map((g) => <option key={g} value={g} />)}
          </datalist>
        </label>
        <label className="calc-field">
          Icon address (optional)
          <input className="field" value={link.icon?.startsWith("data:") ? "(saved image)" : link.icon ?? ""} disabled={!!link.icon?.startsWith("data:")} onChange={(e) => setLink({ ...link, icon: e.target.value })} />
        </label>
        <label className="calc-field">
          Note (optional)
          <input className="field" value={link.note ?? ""} onChange={(e) => setLink({ ...link, note: e.target.value })} placeholder="e.g. LAN or Remote" />
        </label>
        <div className="row">
          {onDelete && (
            <Glass as="button" type="button" shape="pill" interactive className="button button--small tone-critical" onClick={onDelete}>
              <Trash2 aria-hidden="true" /> Remove
            </Glass>
          )}
          <span className="spacer" />
          <Glass as="button" type="button" shape="pill" interactive className="button button--small" onClick={onCancel}>
            Cancel
          </Glass>
          <Glass as="button" type="submit" variant="tint" shape="pill" interactive className="button button--small" disabled={!valid}>
            Save
          </Glass>
        </div>
      </form>
    </Sheet>
  );
}
