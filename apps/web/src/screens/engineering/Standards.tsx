import { useCallback, useEffect, useState } from "react";
import { Archive, ArchiveRestore, ExternalLink, FileUp, RefreshCcw, Search } from "lucide-react";
import { standards, type StandardDocument, type StandardHit } from "../../api/engineering";
import { Glass } from "../../components/Glass";
import { IconButton, PageHead } from "../../components/PageHead";
import { Sheet } from "../../components/Sheet";
import { StandardPageSheet, standardLabel } from "./StandardSheets";

export function Standards() {
  const [query, setQuery] = useState("");
  const [archived, setArchived] = useState(false);
  const [hits, setHits] = useState<StandardHit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<{ id: string; page: number } | null>(null);
  const [upload, setUpload] = useState<{ replace?: StandardDocument } | null>(null);

  const load = useCallback(async () => {
    try {
      setHits(await standards.search({ query: query.trim() || undefined, includeArchived: archived }));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Library unavailable.");
    }
  }, [query, archived]);

  useEffect(() => {
    const t = window.setTimeout(load, 250);
    return () => window.clearTimeout(t);
  }, [load]);

  async function toggleArchive(d: StandardDocument) {
    try {
      await (d.active ? standards.archive(d.id) : standards.restore(d.id));
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't update the standard.");
    }
  }

  return (
    <>
      <PageHead
        back="/engineering"
        eyebrow="Private library"
        title="Standards"
        actions={
          <IconButton label="Upload a standard" onClick={() => setUpload({})}>
            <FileUp aria-hidden="true" />
          </IconButton>
        }
      />
      <Glass as="label" shape="pill" className="ask-bar">
        <Search aria-hidden="true" />
        <input className="ask-bar__input" placeholder="Search titles and page text" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search standards" />
      </Glass>
      <label className="row muted" style={{ margin: "12px 6px 0", fontSize: 14, gap: 8 }}>
        <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} /> Include archived and superseded
      </label>
      {error && <div className="error-banner" role="alert" style={{ marginTop: 16 }}>{error}</div>}

      <div className="stack" style={{ marginTop: 18 }}>
        {hits?.length === 0 && <p className="muted" style={{ margin: "0 4px" }}>{query ? "No matches." : "The library is empty. Upload a PDF to start."}</p>}
        {hits?.map((h, i) => {
          const d = h.document;
          return (
            <Glass key={`${d.id}-${h.page ?? "doc"}-${i}`} className="widget" style={{ minHeight: 0, opacity: d.active ? 1 : 0.7 }}>
              <div className="widget__head">
                <span style={{ color: "var(--ink)", fontSize: 15 }}>{d.title}</span>
                {!d.active && <span className="chip">{d.superseded_by_id ? "Superseded" : "Archived"}</span>}
                <span className="muted" style={{ marginLeft: "auto", fontSize: 12 }}>{d.authority}</span>
              </div>
              <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                {standardLabel(d)} · {d.pages} pages · {d.indexed ? (d.extraction_method === "ocr" ? "indexed (OCR)" : "indexed") : "not indexed"}
                {d.ocr_error ? ` · OCR failed: ${d.ocr_error}` : ""}
              </p>
              {h.snippet && <p className="excerpt" style={{ margin: 0 }}>{h.snippet}</p>}
              <div className="row" style={{ flexWrap: "wrap" }}>
                {h.page && (
                  <Glass as="button" shape="pill" interactive className="button button--small" onClick={() => setPage({ id: d.id, page: h.page! })}>
                    {h.citation ?? `Page ${h.page}`}
                  </Glass>
                )}
                <span className="spacer" />
                <button className="icon-link" onClick={() => standards.openFile(d.id, h.page ?? undefined)} aria-label={`Open ${d.title} PDF`}>
                  <ExternalLink size={16} />
                </button>
                {d.active && (
                  <button className="icon-link" onClick={() => setUpload({ replace: d })} aria-label={`Upload new revision of ${d.title}`}>
                    <RefreshCcw size={16} />
                  </button>
                )}
                {!d.superseded_by_id && (
                  <button className="icon-link" onClick={() => toggleArchive(d)} aria-label={`${d.active ? "Archive" : "Restore"} ${d.title}`}>
                    {d.active ? <Archive size={16} /> : <ArchiveRestore size={16} />}
                  </button>
                )}
              </div>
            </Glass>
          );
        })}
      </div>
      {page && <StandardPageSheet documentId={page.id} page={page.page} onClose={() => setPage(null)} />}
      {upload && (
        <UploadSheet
          replace={upload.replace}
          onClose={() => setUpload(null)}
          onDone={() => {
            setUpload(null);
            load();
          }}
        />
      )}
    </>
  );
}

function UploadSheet({ replace, onClose, onDone }: { replace?: StandardDocument; onClose: () => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState(replace?.title ?? "");
  const [authority, setAuthority] = useState(replace?.authority ?? "");
  const [reference, setReference] = useState(replace?.reference ?? "");
  const [edition, setEdition] = useState(replace?.edition ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await standards.upload(file, { title: title.trim(), authority: authority.trim(), reference: reference.trim(), edition: edition.trim() }, replace?.id);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet label={replace ? "New revision" : "Upload a standard"} onClose={onClose}>
      <div className="stack">
        <h2 className="app-sheet__name">{replace ? `New revision of ${replace.title}` : "Upload a standard"}</h2>
        <input className="field file-field" type="file" accept="application/pdf,.pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} aria-label="PDF file" />
        <input className="field" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Title" />
        <input className="field" placeholder="Authority (e.g. Melbourne Water)" value={authority} onChange={(e) => setAuthority(e.target.value)} aria-label="Authority" />
        <div className="row">
          <input className="field" placeholder="Reference" value={reference} onChange={(e) => setReference(e.target.value)} aria-label="Reference" />
          <input className="field" placeholder="Edition" value={edition} onChange={(e) => setEdition(e.target.value)} aria-label="Edition" />
        </div>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>Scanned PDFs are OCR'd on upload, which can take a few minutes.</p>
        {error && <div className="error-banner">{error}</div>}
        <Glass as="button" variant="tint" shape="pill" interactive className="button" disabled={busy || !file || (!replace && (!title.trim() || !authority.trim()))} onClick={submit}>
          {busy ? "Uploading and indexing…" : "Upload"}
        </Glass>
      </div>
    </Sheet>
  );
}
