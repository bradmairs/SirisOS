import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Footprints, MapPinned, Mountain, Trash2, Upload } from "lucide-react";
import { useResource } from "../api/resource";
import { trails, type TrailsImport, type Walk, type WalkDetail } from "../api/trails";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";
import { Sheet } from "../components/Sheet";
import { undoable } from "../components/Undo";

/** SirisTrails (11.22): every walk of an hour or more and every hike, from Apple Health, on a map. */

const HIKE = "#f97316", WALK = "#38bdf8";
const hm = (min: number | null) => (min == null ? "–" : `${Math.floor(min / 60)}h ${String(Math.round(min % 60)).padStart(2, "0")}m`);
const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
const n = (v: number | null | undefined, unit: string, digits = 0) => (v == null ? "–" : `${v.toLocaleString(undefined, { maximumFractionDigits: digits })} ${unit}`);

function baseLayers() {
  const topo = L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", { maxZoom: 17, attribution: "© OpenTopoMap, © OpenStreetMap contributors" });
  const street = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" });
  const sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, attribution: "Imagery © Esri" });
  return { Topographic: topo, Street: street, Satellite: sat };
}

/** A Leaflet map in a div: `draw` adds the lines and returns the bounds to show. */
function useMap(draw: (map: L.Map, layer: L.LayerGroup) => L.LatLngBounds | null, deps: unknown[]) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  useEffect(() => {
    if (!el.current || map.current) return;
    const layers = baseLayers();
    map.current = L.map(el.current, { worldCopyJump: true, layers: [layers.Topographic] });
    L.control.layers(layers).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    return () => { map.current?.remove(); map.current = null; };
  }, []);
  useEffect(() => {
    if (!map.current || !layer.current) return;
    layer.current.clearLayers();
    const bounds = draw(map.current, layer.current);
    if (bounds?.isValid()) map.current.fitBounds(bounds, { padding: [24, 24], maxZoom: 15 });
    else map.current.setView([-37.8, 145], 4);
    setTimeout(() => map.current?.invalidateSize(), 60);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return el;
}

export function TrailsScreen() {
  useEffect(() => { document.title = "SirisTrails · SirisOS"; }, []);
  const [year, setYear] = useState<number | undefined>(undefined);
  const res = useResource(`trails:${year ?? "all"}`, () => trails.list(year), { staleMs: 60_000 });
  const [open, setOpen] = useState<string | null>(null);
  const [gone, setGone] = useState<Set<string>>(new Set());
  const d = res.data;
  const walks = useMemo(() => (d?.walks ?? []).filter((w) => !gone.has(w.id)), [d, gone]);
  const reload = () => void res.reload(true);

  return (
    <>
      <PageHead eyebrow={d ? `${d.count} walk${d.count === 1 ? "" : "s"} and hikes` : "Walks and hikes"} title="SirisTrails" />
      {res.error && !d && <div className="error-banner" role="alert">{res.error}</div>}
      <div className="stack" style={{ marginTop: 16 }}>
        {d && d.years.length > 1 && (
          <div className="row career-views" role="tablist" aria-label="Year" style={{ flexWrap: "wrap" }}>
            <button type="button" role="tab" aria-selected={!year} className={`chip chip--button ${!year ? "chip--active" : ""}`} onClick={() => setYear(undefined)}>All</button>
            {d.years.map((y) => <button key={y} type="button" role="tab" aria-selected={year === y} className={`chip chip--button ${year === y ? "chip--active" : ""}`} onClick={() => setYear(y)}>{y}</button>)}
          </div>
        )}
        {d && (
          <Glass as="section" className="widget" aria-label="Totals">
            <div className="metrics">
              <div><div className="metric__value">{d.count}</div><div className="metric__label">walks and hikes</div></div>
              <div><div className="metric__value">{n(d.km, "km", 1)}</div><div className="metric__label">walked</div></div>
              <div><div className="metric__value">{n(d.hours, "h")}</div><div className="metric__label">on foot</div></div>
              <div><div className="metric__value">{n(d.ascent_m, "m")}</div><div className="metric__label">climbed</div></div>
              <div><div className="metric__value">{n(d.highest_m, "m")}</div><div className="metric__label">highest point</div></div>
              <div><div className="metric__value">{n(d.longest_km, "km", 1)}</div><div className="metric__label">longest</div></div>
            </div>
          </Glass>
        )}
        <OverviewMap walks={walks} onPick={setOpen} />
        {d && walks.length === 0 && <GettingStarted />}
        {walks.length > 0 && (
          <Glass as="section" className="widget" aria-label="Walks">
            <header className="widget__head"><Footprints aria-hidden="true" /><span>Walks and hikes</span></header>
            <ul className="items">
              {walks.map((w) => (
                <li key={w.id}>
                  <button type="button" className="item item--button" onClick={() => setOpen(w.id)}>
                    <span className="trail-dot" style={{ background: w.kind === "hike" ? HIKE : WALK }} aria-hidden="true" />
                    <span className="item__text">
                      <span className="item__title">{w.name}</span>
                      <span className="item__subtitle">{day(w.start)} · {n(w.km, "km", 1)} · {hm(w.minutes)}{w.ascent_m ? ` · ↑${w.ascent_m} m` : ""}{w.kind === "hike" ? " · hike" : ""}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Glass>
        )}
        <ImportCard onDone={reload} />
      </div>
      {open && (
        <WalkSheet id={open} onClose={() => setOpen(null)} onChanged={reload}
          onDelete={(w) => { setOpen(null); undoable({ text: `Deleted ${w.name}`, run: async () => { await trails.remove(w.id); reload(); },
            hide: () => setGone((g) => new Set(g).add(w.id)), restore: () => setGone((g) => { const s = new Set(g); s.delete(w.id); return s; }) }); }} />
      )}
    </>
  );
}

function OverviewMap({ walks, onPick }: { walks: Walk[]; onPick: (id: string) => void }) {
  const el = useMap((_, layer) => {
    const bounds = L.latLngBounds([]);
    for (const w of walks) {
      if (w.line.length < 2) continue;
      const line = L.polyline(w.line, { color: w.kind === "hike" ? HIKE : WALK, weight: 4, opacity: 0.9 })
        .bindTooltip(`${w.name} · ${n(w.km, "km", 1)}`).on("click", () => onPick(w.id));
      line.addTo(layer);
      L.circleMarker(w.start_point, { radius: 4, color: "#fff", weight: 1, fillColor: w.kind === "hike" ? HIKE : WALK, fillOpacity: 1 }).addTo(layer);
      bounds.extend(line.getBounds());
    }
    return bounds;
  }, [walks]);
  return (
    <Glass as="section" className="widget" style={{ padding: 0, overflow: "hidden" }} aria-label="Map of walks">
      <div ref={el} className="trail-map" role="application" aria-label="Map" />
      <div className="row muted" style={{ gap: 14, fontSize: 12, padding: "8px 14px" }}>
        <span><span className="trail-dot" style={{ background: HIKE }} /> Hikes</span><span><span className="trail-dot" style={{ background: WALK }} /> Walks of an hour or more</span>
      </div>
    </Glass>
  );
}

function Profile({ profile }: { profile: [number, number][] }) {
  if (profile.length < 2) return null;
  const W = 600, H = 140, maxX = profile[profile.length - 1][0] || 1;
  const eles = profile.map((p) => p[1]);
  const lo = Math.min(...eles), hi = Math.max(...eles), span = Math.max(hi - lo, 10);
  const pts = profile.map(([x, e]) => `${(x / maxX) * W},${H - ((e - lo) / span) * (H - 10) - 5}`).join(" ");
  return (
    <figure style={{ margin: 0 }} aria-label="Elevation profile">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" role="img" aria-label={`Elevation from ${Math.round(lo)} m to ${Math.round(hi)} m`}>
        <polygon points={`0,${H} ${pts} ${W},${H}`} fill="color-mix(in srgb, #f97316 25%, transparent)" />
        <polyline points={pts} fill="none" stroke="#f97316" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
      <figcaption className="muted row" style={{ fontSize: 12, justifyContent: "space-between" }}><span>{Math.round(lo)} m</span><span>{maxX.toFixed(1)} km</span><span>{Math.round(hi)} m</span></figcaption>
    </figure>
  );
}

function WalkSheet({ id, onClose, onChanged, onDelete }: { id: string; onClose: () => void; onChanged: () => void; onDelete: (w: Walk) => void }) {
  const [w, setW] = useState<WalkDetail | null>(null);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  useEffect(() => { void trails.get(id).then((x) => { setW(x); setName(x.name); setNote(x.note); }); }, [id]);
  const el = useMap((_, layer) => {
    if (!w || w.route.length < 2) return null;
    const line = L.polyline(w.route, { color: w.kind === "hike" ? HIKE : WALK, weight: 5 }).addTo(layer);
    L.circleMarker(w.route[0], { radius: 6, color: "#fff", fillColor: "#22c55e", fillOpacity: 1 }).bindTooltip("Start").addTo(layer);
    L.circleMarker(w.route[w.route.length - 1], { radius: 6, color: "#fff", fillColor: "#ef4444", fillOpacity: 1 }).bindTooltip("Finish").addTo(layer);
    return line.getBounds();
  }, [w]);
  async function save() {
    if (!w) return;
    await trails.change(w.id, { name, note });
    onChanged();
  }
  return (
    <Sheet label={w?.name ?? "Walk"} onClose={() => { void save(); onClose(); }}>
      <div className="stack">
        <input className="field app-sheet__name" value={name} onChange={(e) => setName(e.target.value)} aria-label="Name" />
        {w && <p className="muted" style={{ margin: 0 }}>{day(w.start)} · {w.kind === "hike" ? "Hike" : "Walk"} · from {w.source === "apple_health_export" ? "the Apple Health export" : "Health Auto Export"}</p>}
        <div ref={el} className="trail-map trail-map--small" role="application" aria-label="Route" />
        {w && (
          <>
            <div className="metrics">
              <div><div className="metric__value">{n(w.km, "km", 2)}</div><div className="metric__label">distance</div></div>
              <div><div className="metric__value">{hm(w.minutes)}</div><div className="metric__label">time{w.moving_minutes ? ` (${hm(w.moving_minutes)} moving)` : ""}</div></div>
              <div><div className="metric__value">{w.pace_min_per_km ? `${Math.floor(w.pace_min_per_km)}:${String(Math.round((w.pace_min_per_km % 1) * 60)).padStart(2, "0")}/km` : "–"}</div><div className="metric__label">pace</div></div>
              <div><div className="metric__value">{n(w.ascent_m, "m")}</div><div className="metric__label">ascent (↓{n(w.descent_m, "m")})</div></div>
              <div><div className="metric__value">{n(w.highest_m, "m")}</div><div className="metric__label">highest</div></div>
              <div><div className="metric__value">{w.avg_hr ? `${w.avg_hr} bpm` : "–"}</div><div className="metric__label">heart rate{w.max_hr ? ` (max ${w.max_hr})` : ""}</div></div>
              <div><div className="metric__value">{n(w.kcal, "kcal")}</div><div className="metric__label">energy</div></div>
            </div>
            <Profile profile={w.profile} />
            <textarea className="field" rows={3} placeholder="Notes: the track, the weather, who came" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Notes" />
            <div className="row">
              <button type="button" className="button button--small button--primary" onClick={() => { void save(); onClose(); }}>Done</button>
              <span className="spacer" />
              <button type="button" className="button button--small" onClick={() => onDelete(w)}><Trash2 size={14} aria-hidden="true" /> Delete</button>
            </div>
          </>
        )}
      </div>
    </Sheet>
  );
}

function GettingStarted() {
  return (
    <Glass as="section" className="widget" aria-label="Getting started">
      <header className="widget__head"><Mountain aria-hidden="true" /><span>Bring in your walks</span></header>
      <ol style={{ margin: 0, paddingLeft: 18, fontSize: 14, display: "grid", gap: 6 }}>
        <li><b>Every walk so far:</b> on your iPhone, Health → your picture → <i>Export All Health Data</i>, then upload the export.zip below.</li>
        <li><b>New ones as they happen:</b> in Health Auto Export, add a REST API automation for <i>Workouts</i> with <i>Include Route Data</i> on, posting to the same address and key as your health data (Fitness → Apple Health).</li>
      </ol>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Kept: every hike, and every outdoor walk of an hour or more, with its GPS route.</p>
    </Glass>
  );
}

function ImportCard({ onDone }: { onDone: () => void }) {
  const [s, setS] = useState<TrailsImport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  useEffect(() => { void trails.importStatus().then(setS).catch(() => undefined); }, []);
  useEffect(() => {
    if (!s?.running) return;
    const t = window.setInterval(async () => {
      const next = await trails.importStatus().catch(() => null);
      if (next) { setS(next); if (!next.running) onDone(); }
    }, 3000);
    return () => window.clearInterval(t);
  }, [s?.running, onDone]);
  async function upload(file: File) {
    setBusy(true); setError(null);
    try { await trails.uploadExport(file); setS({ running: true }); } catch (e) { setError(e instanceof Error ? e.message : "Upload failed."); } finally { setBusy(false); }
  }
  return (
    <Glass as="section" className="widget" aria-label="Import from Apple Health">
      <header className="widget__head"><MapPinned aria-hidden="true" /><span>From the Apple Health export</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>Upload export.zip (Health → your picture → Export All Health Data) to bring in every walk and hike with a route. Ones already here aren't doubled, and ones you've deleted stay deleted.</p>
      <input ref={picker} type="file" accept=".zip,application/zip" hidden aria-label="Apple Health export.zip" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void upload(f); }} />
      <button type="button" className="button button--small" style={{ alignSelf: "flex-start" }} disabled={busy || !!s?.running} onClick={() => picker.current?.click()}>
        <Upload size={14} aria-hidden="true" /> {busy ? "Uploading…" : s?.running ? "Reading your walks…" : "Upload export.zip"}
      </button>
      {error && <p role="alert" style={{ margin: 0, fontSize: 14 }}>{error}</p>}
      {s?.error && <p role="alert" style={{ margin: 0, fontSize: 14 }}>{s.error}</p>}
      {!s?.running && s?.at && (
        <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>
          Last export ({new Date(s.at).toLocaleDateString()}): {s.added} added, {s.already_here} already here{s.no_route ? `, ${s.no_route} with no route recorded` : ""}.
        </p>
      )}
    </Glass>
  );
}
