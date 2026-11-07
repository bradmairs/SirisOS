import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { life, type Doc } from "../api/life";

/** A kept receipt: the email as it came, and its attachments. The email is shown in a sandbox with nothing able to run or load. */
export function ReceiptView({ id, onRemoved }: { id: number; onRemoved?: () => void }) {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [html, setHtml] = useState<string | null>(null);
  const [plain, setPlain] = useState<string | null>(null);
  const [links, setLinks] = useState<{ name: string; url: string }[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const made: string[] = [];
    (async () => {
      const d = await life.document(id);
      if (!live) return;
      setDoc(d);
      for (const name of d.files ?? []) {
        const blob = await life.documentFile(id, name);
        if (!live) return;
        if (name === "email.html") setHtml(await blob.text());
        else if (name === "email.txt") setPlain(await blob.text());
        else {
          const url = URL.createObjectURL(blob);
          made.push(url);
          setLinks((l) => [...l, { name, url }]);
        }
      }
    })().catch((e) => { if (live) setError(e instanceof Error ? e.message : String(e)); });
    return () => { live = false; made.forEach((u) => URL.revokeObjectURL(u)); };
  }, [id]);

  if (error) return <p className="tone-critical" role="alert" style={{ margin: 0 }}>{error}</p>;
  if (!doc) return <div className="skeleton" style={{ height: 120 }} aria-busy="true" />;
  const noOriginal = !(doc.files ?? []).length;
  return (
    <div className="stack" style={{ gap: 8 }}>
      <p style={{ margin: 0 }}>{doc.summary}</p>
      {links.length > 0 && (
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
          {links.map((l) => <a key={l.name} className="button button--small" href={l.url} target="_blank" rel="noreferrer" download={l.name}>{l.name}</a>)}
        </div>
      )}
      {html !== null && <iframe title={`Receipt: ${doc.title}`} sandbox="" srcDoc={html} className="receipt-frame" />}
      {plain !== null && <pre className="receipt-text">{plain}</pre>}
      {noOriginal && doc.text && <pre className="receipt-text">{doc.text}</pre>}
      {onRemoved && (
        <button type="button" className="button button--small" style={{ alignSelf: "flex-start" }}
          onClick={async () => { if (window.confirm("Remove this receipt? It stays in your email, but won't be kept here again.")) { await life.deleteDocument(id); onRemoved(); } }}>
          <Trash2 size={14} aria-hidden="true" /> Remove
        </button>
      )}
    </div>
  );
}
