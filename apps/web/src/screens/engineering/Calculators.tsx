import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BookMarked, ChevronRight, Save, Trash2, X } from "lucide-react";
import { calculations, type Calculation, type StandardDocument } from "../../api/engineering";
import { CALCULATORS, CALCULATOR_BY_ID, fieldLabel, run, type Calculator } from "../../engineering/calculators";
import { Glass } from "../../components/Glass";
import { PageHead } from "../../components/PageHead";
import { Sheet } from "../../components/Sheet";
import { StandardPicker, standardLabel } from "./StandardSheets";

export function Calculators() {
  const [saved, setSaved] = useState<Calculation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    calculations.list().then(setSaved).catch((e) => setError(e.message));
  }, []);

  const groups = useMemo(() => {
    const out = new Map<string, Calculator[]>();
    for (const c of CALCULATORS) out.set(c.category, [...(out.get(c.category) ?? []), c]);
    return [...out.entries()];
  }, []);

  async function remove(id: string) {
    setSaved((s) => s?.filter((c) => c.id !== id) ?? null);
    await calculations.remove(id).catch(() => calculations.list().then(setSaved));
  }

  return (
    <>
      <PageHead back="/engineering" eyebrow="Deterministic, SI units" title="Calculators" />
      <div className="widget-grid">
        {groups.map(([category, items]) => (
          <Glass key={category} className="widget" style={{ minHeight: 0 }}>
            <div className="widget__head">{category}</div>
            <ul className="items">
              {items.map((c) => (
                <li key={c.id}>
                  <Link className="item" to={`/engineering/calculators/${c.id}`}>
                    <span className="item__text">
                      <div className="item__title">{c.title}</div>
                    </span>
                    <ChevronRight size={16} className="muted" aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          </Glass>
        ))}
      </div>

      <h2 className="section-title">Saved calculations</h2>
      {error && <div className="error-banner">{error}</div>}
      {saved?.length === 0 && <p className="muted" style={{ margin: "0 4px" }}>Nothing saved yet. Run a calculator and save the result.</p>}
      <div className="stack">
        {saved?.map((c) => (
          <SavedCalculation key={c.id} calculation={c} onDelete={() => remove(c.id)} />
        ))}
      </div>
    </>
  );
}

export function SavedCalculation({ calculation: c, onDelete }: { calculation: Calculation; onDelete?: () => void }) {
  return (
    <Glass className="widget" style={{ minHeight: 0 }} aria-label={c.title}>
      <div className="widget__head">
        <span style={{ color: "var(--ink)", fontSize: 15 }}>{c.title}</span>
        <span className="muted" style={{ marginLeft: "auto", fontSize: 12 }}>{CALCULATOR_BY_ID[c.calculator_id]?.title ?? c.calculator_id} · {new Date(c.created_at).toLocaleDateString()}</span>
        {onDelete && (
          <button className="icon-link" onClick={onDelete} aria-label={`Delete ${c.title}`}>
            <Trash2 size={16} />
          </button>
        )}
      </div>
      <div className="metrics">
        {c.results.map((r, i) => (
          <div key={i}>
            <div className="metric__value metric__value--long">{r.value}</div>
            <div className="metric__label">{r.label}</div>
          </div>
        ))}
      </div>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        {Object.entries(c.inputs).map(([k, v]) => `${k}: ${v}`).join(" · ")}
      </p>
      {c.cited_standard_label && (
        <span className="chip" style={{ alignSelf: "flex-start" }}>
          <BookMarked size={12} aria-hidden="true" /> {c.cited_standard_label}
        </span>
      )}
      {c.notes && <p style={{ margin: 0, fontSize: 14 }}>{c.notes}</p>}
    </Glass>
  );
}

export function CalculatorScreen() {
  const { id = "" } = useParams();
  const calculator = CALCULATOR_BY_ID[id];
  const [raw, setRaw] = useState<Record<string, string>>(() => Object.fromEntries((calculator?.fields ?? []).map((f) => [f.key, f.initial])));
  const [saving, setSaving] = useState(false);
  const [savedTitle, setSavedTitle] = useState<string | null>(null);

  const outcome = useMemo(() => {
    if (!calculator) return null;
    try {
      return { ok: true as const, ...run(calculator, raw) };
    } catch (err) {
      return { ok: false as const, error: err instanceof Error ? err.message : "Check the entered values." };
    }
  }, [calculator, raw]);

  if (!calculator) {
    return (
      <>
        <PageHead back="/engineering/calculators" title="Calculator not found" />
      </>
    );
  }

  return (
    <>
      <PageHead back="/engineering/calculators" eyebrow={calculator.category} title={calculator.title} />
      <p className="muted" style={{ margin: "-8px 4px 18px" }}>{calculator.note}</p>
      <div className="widget-grid">
        <Glass as="form" className="widget" onSubmit={(e: Event) => e.preventDefault()} aria-label="Inputs">
          <div className="widget__head">Inputs</div>
          {calculator.fields.map((f) => (
            <label key={f.key} className="calc-field">
              <span>{f.label}</span>
              <span className="calc-field__input">
                <input
                  className="field"
                  inputMode="decimal"
                  value={raw[f.key] ?? ""}
                  onChange={(e) => setRaw((r) => ({ ...r, [f.key]: e.target.value }))}
                  aria-label={fieldLabel(f)}
                />
                {f.unit && <span className="calc-field__unit">{f.unit}</span>}
              </span>
            </label>
          ))}
        </Glass>
        <Glass as="section" className="widget" aria-label="Results" aria-live="polite">
          <div className="widget__head">Results</div>
          {outcome?.ok ? (
            <div className="metrics" style={{ gridTemplateColumns: "1fr 1fr" }}>
              {outcome.results.map((r, i) => (
                <div key={i}>
                  <div className="metric__value metric__value--long">{r.value}</div>
                  <div className="metric__label">{r.label}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="warning-banner">{outcome?.error}. Check the entered values, geometry and units.</div>
          )}
          <span className="spacer" />
          {savedTitle && <p className="tone-good" style={{ margin: 0, fontSize: 14 }}>Saved “{savedTitle}”.</p>}
          <Glass as="button" variant="tint" shape="pill" interactive className="button" disabled={!outcome?.ok} onClick={() => setSaving(true)}>
            <Save aria-hidden="true" /> Save calculation
          </Glass>
        </Glass>
      </div>
      {saving && outcome?.ok && (
        <SaveSheet
          calculator={calculator}
          values={outcome.values}
          results={outcome.results}
          onClose={() => setSaving(false)}
          onSaved={(title) => {
            setSaving(false);
            setSavedTitle(title);
          }}
        />
      )}
    </>
  );
}

function SaveSheet({
  calculator,
  values,
  results,
  onClose,
  onSaved,
}: {
  calculator: Calculator;
  values: Record<string, number>;
  results: { label: string; value: string }[];
  onClose: () => void;
  onSaved: (title: string) => void;
}) {
  const [title, setTitle] = useState(calculator.title);
  const [notes, setNotes] = useState("");
  const [standard, setStandard] = useState<StandardDocument | null>(null);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const inputs = Object.fromEntries(calculator.fields.map((f) => [fieldLabel(f), values[f.key]]));
      await calculations.save({ calculator_id: calculator.id, title: title.trim(), inputs, results, notes: notes.trim(), cited_standard_id: standard?.id ?? null });
      onSaved(title.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save.");
    } finally {
      setBusy(false);
    }
  }

  if (picking) return <StandardPicker onClose={() => setPicking(false)} onPick={(d) => { setStandard(d); setPicking(false); }} />;

  return (
    <Sheet label="Save calculation" onClose={onClose}>
      <div className="stack">
        <h2 className="app-sheet__name">Save calculation</h2>
        <input className="field" value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Title" maxLength={160} />
        <textarea className="field" rows={3} placeholder="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} aria-label="Notes" maxLength={2000} />
        {standard ? (
          <span className="chip" style={{ alignSelf: "flex-start" }}>
            <BookMarked size={12} aria-hidden="true" /> {standardLabel(standard)}
            <button className="icon-link" onClick={() => setStandard(null)} aria-label="Remove citation"><X size={12} /></button>
          </span>
        ) : (
          <Glass as="button" shape="pill" interactive className="button button--small" style={{ alignSelf: "flex-start" }} onClick={() => setPicking(true)}>
            <BookMarked aria-hidden="true" /> Cite a standard
          </Glass>
        )}
        {error && <div className="error-banner">{error}</div>}
        <Glass as="button" variant="tint" shape="pill" interactive className="button" disabled={busy || !title.trim()} onClick={save}>
          {busy ? "Saving…" : "Save"}
        </Glass>
      </div>
    </Sheet>
  );
}
