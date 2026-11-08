import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { life, type Doc } from "../api/life";

type Loaded = { name: string; url: string; type: string; text?: string };

const isEmail = (name: string) => name === "email.html" || name === "email.txt";

/** A kept receipt (8.1; the receipt itself first since 8.2). SirisAI marks which file is the receipt: the invoice PDF
 * when the email only says it's attached, a photo of it, or the email when the receipt is written in it. The email is
 * shown in a sandbox with nothing able to run or load. */
export function ReceiptView({ id, onRemoved }: { id: number; onRemoved?: () => void }) {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [files, setFiles] = useState<Loaded[]>([]);
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
        const text = isEmail(name) ? await blob.text() : undefined;
        const url = URL.createObjectURL(blob);
        made.push(url);
        setFiles((f) => [...f, { name, url, type: blob.type, text }]);
      }
    })().catch((e) => { if (live) setError(e instanceof Error ? e.message : String(e)); });
    return () => { live = false; made.forEach((u) => URL.revokeObjectURL(u)); };
  }, [id]);

  if (error) return <p className="tone-critical" role="alert" style={{ margin: 0 }}>{error}</p>;
  if (!doc) return <div className="skeleton" style={{ height: 120 }} aria-busy="true" />;
  const mainName = doc.receipt_file ?? (doc.files ?? [])[0];
  const main = files.find((f) => f.name === mainName);
  const email = files.find((f) => isEmail(f.name));
  const others = files.filter((f) => f !== main && f !== email);
  return (
    <div className="stack" style={{ gap: 8 }}>
      <p style={{ margin: 0 }}>{doc.summary}</p>
      {!main && (doc.files ?? []).length > 0 && <div className="skeleton" style={{ height: 200 }} aria-busy="true" />}
      {main && <Shown file={main} title={`Receipt: ${doc.title}`} />}
      {main && !isEmail(main.name) && (
        <a className="button button--small" style={{ alignSelf: "flex-start" }} href={main.url} target="_blank" rel="noreferrer" download={main.name}>Open {main.name}</a>
      )}
      {others.length > 0 && (
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
          {others.map((l) => <a key={l.name} className="button button--small" href={l.url} target="_blank" rel="noreferrer" download={l.name}>{l.name}</a>)}
        </div>
      )}
      {email && main && main !== email && (
        <details>
          <summary className="muted" style={{ cursor: "pointer" }}>The email it came with</summary>
          <Shown file={email} title={`Email: ${doc.title}`} />
        </details>
      )}
      {!(doc.files ?? []).length && doc.text && <pre className="receipt-text">{doc.text}</pre>}
      {onRemoved && (
        <button type="button" className="button button--small" style={{ alignSelf: "flex-start" }}
          onClick={async () => { if (window.confirm("Remove this receipt? It stays in your email, but won't be kept here again.")) { await life.deleteDocument(id); onRemoved(); } }}>
          <Trash2 size={14} aria-hidden="true" /> Remove
        </button>
      )}
    </div>
  );
}

function Shown({ file, title }: { file: Loaded; title: string }) {
  if (file.name === "email.html") return <iframe title={title} sandbox="" srcDoc={file.text} className="receipt-frame" />;
  if (file.name === "email.txt") return <pre className="receipt-text">{file.text}</pre>;
  if (file.type.startsWith("image/") || /\.(png|jpe?g|gif|webp|heic)$/i.test(file.name)) return <img src={file.url} alt={title} className="receipt-image" />;
  // A PDF from the receipt: the browser's own viewer shows it. "Open" beside it, for phones that only show the first page.
  return <iframe title={title} src={file.url} className="receipt-frame" />;
}
