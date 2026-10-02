import { useEffect, useState } from "react";
import { ExternalLink, Search } from "lucide-react";
import { standards, type StandardDocument, type StandardPage } from "../../api/engineering";
import { Glass } from "../../components/Glass";
import { Sheet } from "../../components/Sheet";

export function standardLabel(d: StandardDocument): string {
  return [d.reference || d.title, d.edition].filter(Boolean).join(" · ") + (d.revision > 1 ? ` · rev. ${d.revision}` : "");
}

/** One indexed page of a standard, with a link to the PDF at that page. */
export function StandardPageSheet({ documentId, page, onClose }: { documentId: string; page: number; onClose: () => void }) {
  const [data, setData] = useState<StandardPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    standards.page(documentId, page).then(setData).catch((e) => setError(e.message));
  }, [documentId, page]);
  return (
    <Sheet label="Standard page" onClose={onClose}>
      {error && <div className="error-banner">{error}</div>}
      {!data && !error && <div className="skeleton" style={{ height: 120 }} />}
      {data && (
        <div className="stack">
          <div>
            <p className="page-head__eyebrow" style={{ margin: 0 }}>{data.document.authority}</p>
            <h2 className="app-sheet__name">{data.document.title}</h2>
            <p className="muted" style={{ margin: "4px 0 0" }}>{data.citation}</p>
          </div>
          <pre className="page-text">{data.text || "This page has no extracted text."}</pre>
          <Glass as="button" variant="tint" shape="pill" interactive className="button" onClick={() => standards.openFile(documentId, page)}>
            Open PDF at page {page} <ExternalLink aria-hidden="true" />
          </Glass>
        </div>
      )}
    </Sheet>
  );
}

/** Pick an active standard to cite. */
export function StandardPicker({ onPick, onClose }: { onPick: (d: StandardDocument) => void; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [docs, setDocs] = useState<StandardDocument[] | null>(null);
  useEffect(() => {
    const t = window.setTimeout(() => {
      standards
        .search({ query: q.trim() || undefined })
        .then((hits) => {
          const seen = new Set<string>();
          setDocs(hits.map((h) => h.document).filter((d) => !seen.has(d.id) && seen.add(d.id)));
        })
        .catch(() => setDocs([]));
    }, 250);
    return () => window.clearTimeout(t);
  }, [q]);
  return (
    <Sheet label="Cite a standard" onClose={onClose}>
      <h2 className="app-sheet__name" style={{ marginBottom: 12 }}>Cite a standard</h2>
      <Glass as="label" shape="pill" className="ask-bar" style={{ height: 48 }}>
        <Search aria-hidden="true" />
        <input className="ask-bar__input" placeholder="Search the library" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search standards" autoFocus />
      </Glass>
      <ul className="items" style={{ marginTop: 12 }}>
        {docs?.length === 0 && <p className="muted">No standards found.</p>}
        {docs?.map((d) => (
          <li key={d.id}>
            <button className="item item--button" onClick={() => onPick(d)}>
              <span className="item__text">
                <div className="item__title">{d.title}</div>
                <div className="item__subtitle">{d.authority} · {standardLabel(d)}</div>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}
