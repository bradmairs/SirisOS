import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { BookOpen, Droplets, RotateCcw, Trash2 } from "lucide-react";
import { hydro, type EvidenceResponse, type HydroHistory } from "../../api/engineering";
import { Glass } from "../../components/Glass";
import { PageHead } from "../../components/PageHead";
import { StandardPageSheet } from "./StandardSheets";

export function Hydro() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<EvidenceResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HydroHistory[]>([]);
  const [page, setPage] = useState<{ id: string; page: number } | null>(null);

  const loadHistory = () => hydro.history().then(setHistory).catch(() => undefined);
  useEffect(() => {
    loadHistory();
  }, []);

  // Search everything re-asks a past question with ?q=.
  const [params, setParams] = useSearchParams();
  useEffect(() => {
    const wanted = params.get("q");
    if (wanted) {
      setParams({}, { replace: true });
      ask(wanted);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  async function ask(q: string) {
    if (q.trim().length < 2) return;
    setQuestion(q);
    setBusy(true);
    setError(null);
    try {
      setAnswer(await hydro.ask(q.trim()));
      loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "SirisHydro is unavailable.");
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    ask(question);
  }

  async function remove(id: string) {
    setHistory((h) => h.filter((x) => x.id !== id));
    await hydro.remove(id).catch(loadHistory);
  }

  return (
    <>
      <PageHead back="/engineering" eyebrow="Evidence from your standards library" title="SirisHydro" />
      <Glass as="form" shape="pill" className="ask-bar" onSubmit={submit} role="search">
        <Droplets aria-hidden="true" />
        <input className="ask-bar__input" placeholder="e.g. minimum cover for a DN300 sewer" value={question} onChange={(e) => setQuestion(e.target.value)} aria-label="Engineering question" />
        <Glass as="button" type="submit" variant="tint" shape="pill" interactive className="button button--small" disabled={busy || question.trim().length < 2}>
          {busy ? "Searching…" : "Ask"}
        </Glass>
      </Glass>

      {error && <div className="error-banner" role="alert" style={{ marginTop: 16 }}>{error}</div>}

      {answer && (
        <div className="stack" style={{ marginTop: 22 }}>
          {answer.synthesized_answer && (
            <Glass className="widget" style={{ minHeight: 0 }} aria-label="Answer">
              <div className="widget__head">Answer <span className="chip" style={{ marginLeft: "auto" }}>Check the citations</span></div>
              <div className="bubble__text">{answer.synthesized_answer}</div>
            </Glass>
          )}
          <p className={answer.sufficient_evidence ? "muted" : "warning-banner"} style={{ margin: "0 4px" }}>{answer.guidance}</p>
          {answer.evidence.map((e) => (
            <Glass key={`${e.document_id}-${e.page}`} className="widget" style={{ minHeight: 0 }}>
              <div className="widget__head">
                <BookOpen aria-hidden="true" style={{ color: "#2dd4bf" }} />
                <span style={{ color: "var(--ink)" }}>{e.citation}</span>
              </div>
              <p style={{ margin: 0 }} className="excerpt">{e.excerpt}</p>
              <div className="row">
                <span className="muted" style={{ fontSize: 13 }}>{e.authority}</span>
                <span className="spacer" />
                <Glass as="button" shape="pill" interactive className="button button--small" onClick={() => setPage({ id: e.document_id, page: e.page })}>
                  View page {e.page}
                </Glass>
              </div>
            </Glass>
          ))}
        </div>
      )}

      {history.length > 0 && (
        <>
          <h2 className="section-title">History</h2>
          <Glass className="widget" style={{ minHeight: 0 }}>
            <ul className="items">
              {history.map((h) => (
                <li key={h.id} className="item">
                  <span className={`item__dot ${h.sufficient_evidence ? "dot-good" : "dot-warning"}`} aria-hidden="true" />
                  <span className="item__text">
                    <div className="item__title">{h.question}</div>
                    <div className="item__subtitle">
                      {new Date(h.created_at).toLocaleString()} · {h.citations.length} citation{h.citations.length === 1 ? "" : "s"}
                    </div>
                  </span>
                  <button className="icon-link" onClick={() => ask(h.question)} aria-label={`Ask again: ${h.question}`}>
                    <RotateCcw size={16} />
                  </button>
                  <button className="icon-link" onClick={() => remove(h.id)} aria-label={`Delete: ${h.question}`}>
                    <Trash2 size={16} />
                  </button>
                </li>
              ))}
            </ul>
          </Glass>
        </>
      )}
      {page && <StandardPageSheet documentId={page.id} page={page.page} onClose={() => setPage(null)} />}
    </>
  );
}
