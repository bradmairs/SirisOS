import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BookMarked, Calculator as CalcIcon, ChevronRight, Plus, Star, Trash2 } from "lucide-react";
import {
  calculations,
  projects,
  type Calculation,
  type Project,
  type ProjectKind,
  type ProjectStatus,
  type Relationship,
  type StandardDocument,
} from "../../api/engineering";
import { Glass } from "../../components/Glass";
import { IconButton, PageHead } from "../../components/PageHead";
import { Sheet } from "../../components/Sheet";
import { SavedCalculation } from "./Calculators";
import { StandardPicker } from "./StandardSheets";

const KINDS: ProjectKind[] = ["engineering", "homelab", "travel", "fitness", "personal", "other"];
const STATUSES: ProjectStatus[] = ["active", "paused", "completed", "archived"];

export function Projects() {
  const [list, setList] = useState<Project[] | null>(null);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([projects.list(), projects.current()])
      .then(([all, current]) => {
        setList(all);
        setCurrentId(current.project?.id ?? null);
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  return (
    <>
      <PageHead
        back="/engineering"
        eyebrow="Calculations and standards, together"
        title="Projects"
        actions={
          <IconButton label="New project" onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" />
          </IconButton>
        }
      />
      <p className="muted" style={{ margin: "-6px 4px 18px", fontSize: 14 }}>
        Delivery work (tasks, registers, budgets) lives in Project Management. These projects group your engineering evidence.
      </p>
      {error && <div className="error-banner">{error}</div>}
      {list?.length === 0 && <p className="muted" style={{ margin: "0 4px" }}>No projects yet.</p>}
      <Glass className="widget" style={{ minHeight: 0, display: list?.length ? undefined : "none" }}>
        <ul className="items">
          {list?.map((p) => (
            <li key={p.id}>
              <Link className="item" to={`/engineering/projects/${p.id}`}>
                <span className={`item__dot ${p.status === "active" ? "dot-good" : ""}`} aria-hidden="true" />
                <span className="item__text">
                  <div className="item__title">
                    {p.name} {p.id === currentId && <Star size={13} className="tone-warning" aria-label="Current project" style={{ verticalAlign: "-1px" }} />}
                  </div>
                  <div className="item__subtitle">{p.kind} · {p.status}{p.tags.length ? ` · ${p.tags.join(", ")}` : ""}</div>
                </span>
                <ChevronRight size={16} className="muted" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      </Glass>
      {creating && (
        <CreateProject
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            load();
          }}
        />
      )}
    </>
  );
}

function CreateProject({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState<ProjectKind>("engineering");
  const [tags, setTags] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function create() {
    try {
      await projects.create({ name: name.trim(), description: description.trim(), kind, tags: tags.split(",").map((t) => t.trim()).filter(Boolean) });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the project.");
    }
  }
  return (
    <Sheet label="New project" onClose={onClose}>
      <div className="stack">
        <h2 className="app-sheet__name">New project</h2>
        <input className="field" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} aria-label="Name" maxLength={160} />
        <textarea className="field" rows={3} placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)} aria-label="Description" />
        <select className="field" value={kind} onChange={(e) => setKind(e.target.value as ProjectKind)} aria-label="Kind">
          {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <input className="field" placeholder="Tags, comma separated" value={tags} onChange={(e) => setTags(e.target.value)} aria-label="Tags" />
        {error && <div className="error-banner">{error}</div>}
        <Glass as="button" variant="tint" shape="pill" interactive className="button" disabled={!name.trim()} onClick={create}>Create</Glass>
      </div>
    </Sheet>
  );
}

export function ProjectScreen() {
  const { id = "" } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [isCurrent, setIsCurrent] = useState(false);
  const [links, setLinks] = useState<Relationship[]>([]);
  const [calcs, setCalcs] = useState<Calculation[]>([]);
  const [picker, setPicker] = useState<"calculation" | "standard" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([projects.get(id), projects.current(), projects.relationships(id), calculations.list()])
      .then(([p, current, rel, all]) => {
        setProject(p);
        setIsCurrent(current.project?.id === p.id);
        setLinks(rel);
        setCalcs(all);
      })
      .catch((e) => setError(e.message));
  }, [id]);
  useEffect(load, [load]);

  async function act(fn: () => Promise<unknown>) {
    try {
      await fn();
      setError(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  if (!project) return <><PageHead back="/engineering/projects" title={error ? "Project unavailable" : "Loading…"} />{error && <div className="error-banner">{error}</div>}</>;

  const linkedCalcs = links.filter((l) => l.target_type === "calculation");
  const linkedStandards = links.filter((l) => l.target_type === "engineering_standard");
  const calcById = new Map(calcs.map((c) => [c.id, c]));

  return (
    <>
      <PageHead
        back="/engineering/projects"
        eyebrow={`${project.kind} project`}
        title={project.name}
        actions={
          <IconButton label={isCurrent ? "Clear current project" : "Make current project"} onClick={() => act(() => projects.setCurrent(isCurrent ? null : project.id))}>
            <Star aria-hidden="true" className={isCurrent ? "tone-warning" : ""} fill={isCurrent ? "currentColor" : "none"} />
          </IconButton>
        }
      />
      {project.description && <p style={{ margin: "-6px 4px 14px" }}>{project.description}</p>}
      <div className="row" style={{ flexWrap: "wrap", margin: "0 4px 8px" }}>
        {STATUSES.map((s) => (
          <button key={s} className={`chip chip--button ${project.status === s ? "chip--active" : ""}`} onClick={() => act(() => projects.update(project.id, { status: s }))} aria-pressed={project.status === s}>
            {s}
          </button>
        ))}
      </div>
      {error && <div className="error-banner" role="alert">{error}</div>}

      <div className="row">
        <h2 className="section-title">Calculations</h2>
        <span className="spacer" />
        <Glass as="button" shape="pill" interactive className="button button--small" onClick={() => setPicker("calculation")}>
          <CalcIcon aria-hidden="true" /> Link
        </Glass>
      </div>
      <div className="stack">
        {linkedCalcs.length === 0 && <p className="muted" style={{ margin: "0 4px" }}>No calculations linked.</p>}
        {linkedCalcs.map((l) => {
          const c = calcById.get(l.target_id);
          return (
            <div key={l.id} className="linked">
              {c ? <SavedCalculation calculation={c} /> : <Glass className="widget" style={{ minHeight: 0 }}><span className="muted">{l.target_label} (deleted)</span></Glass>}
              <button className="icon-link linked__remove" onClick={() => act(() => projects.unlink(project.id, l.id))} aria-label={`Unlink ${l.target_label}`}>
                <Trash2 size={16} />
              </button>
            </div>
          );
        })}
      </div>

      <div className="row">
        <h2 className="section-title">Standards</h2>
        <span className="spacer" />
        <Glass as="button" shape="pill" interactive className="button button--small" onClick={() => setPicker("standard")}>
          <BookMarked aria-hidden="true" /> Reference
        </Glass>
      </div>
      <Glass className="widget" style={{ minHeight: 0 }}>
        {linkedStandards.length === 0 ? (
          <p className="muted">No standards referenced.</p>
        ) : (
          <ul className="items">
            {linkedStandards.map((l) => (
              <li key={l.id} className="item">
                <BookMarked size={16} style={{ color: "#2dd4bf" }} aria-hidden="true" />
                <span className="item__text"><div className="item__title">{l.target_label}</div></span>
                <button className="icon-link" onClick={() => act(() => projects.unlink(project.id, l.id))} aria-label={`Unlink ${l.target_label}`}>
                  <Trash2 size={16} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Glass>

      {picker === "standard" && (
        <StandardPicker
          onClose={() => setPicker(null)}
          onPick={(d: StandardDocument) => {
            setPicker(null);
            act(() => projects.link(project.id, { target_type: "engineering_standard", target_id: d.id, kind: "references" }));
          }}
        />
      )}
      {picker === "calculation" && (
        <Sheet label="Link a calculation" onClose={() => setPicker(null)}>
          <h2 className="app-sheet__name" style={{ marginBottom: 12 }}>Link a calculation</h2>
          {calcs.length === 0 && <p className="muted">No saved calculations yet.</p>}
          <ul className="items">
            {calcs
              .filter((c) => !linkedCalcs.some((l) => l.target_id === c.id))
              .map((c) => (
                <li key={c.id}>
                  <button
                    className="item item--button"
                    onClick={() => {
                      setPicker(null);
                      act(() => projects.link(project.id, { target_type: "calculation", target_id: c.id, kind: "contains" }));
                    }}
                  >
                    <span className="item__text">
                      <div className="item__title">{c.title}</div>
                      <div className="item__subtitle">{c.results.map((r) => r.value).slice(0, 2).join(" · ")}</div>
                    </span>
                  </button>
                </li>
              ))}
          </ul>
        </Sheet>
      )}
    </>
  );
}
