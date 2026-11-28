import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Footprints, MapPin, MapPinned, Mountain, Pencil, Trash2, Upload } from "lucide-react";
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
                      <span className="item__subtitle">{w.place ? `${w.place.split(",")[0]} · ` : ""}{day(w.start)} · {n(w.km, "km", 1)} · {hm(w.minutes)}{w.ascent_m ? ` · ↑${w.ascent_m} m` : ""}{w.kind === "hike" ? " · hike" : ""}</span>
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

type Point = [number, number, number, number]; // km, metres, lat, lon

/** The elevation profile (12.1): smoothed heights, labelled axes, and a finger or pointer on it shows that spot. */
function Profile({ profile, onHover }: { profile: Point[]; onHover: (p: Point | null) => void }) {
  const [at, setAt] = useState<number | null>(null);
  if (profile.length < 2) return null;
  const W = 600, H = 150, L = 44, B = 22, maxX = profile[profile.length - 1][0] || 1;
  const eles = profile.map((p) => p[1]);
  const lo = Math.min(...eles), hi = Math.max(...eles);
  const span = Math.max(hi - lo, 40);                  // a flat walk stays flat on the chart
  const base = lo - (span - (hi - lo)) / 2;
  const x = (km: number) => L + (km / maxX) * (W - L);
  const y = (m: number) => (H - B) - ((m - base) / span) * (H - B - 8);
  const pts = profile.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
  const pick = (clientX: number, rect: DOMRect) => {
    const km = ((clientX - rect.left) / rect.width * W - L) / (W - L) * maxX;
    let best = 0;
    for (let i = 1; i < profile.length; i++) if (Math.abs(profile[i][0] - km) < Math.abs(profile[best][0] - km)) best = i;
    setAt(best); onHover(profile[best]);
  };
  const p = at != null ? profile[at] : null;
  return (
    <figure className="trail-profile" style={{ margin: 0 }} aria-label="Elevation profile">
      <figcaption className="trail-section-title">Elevation</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Elevation from ${Math.round(lo)} m to ${Math.round(hi)} m over ${maxX.toFixed(1)} km`}
        onPointerMove={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
        onPointerDown={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
        onPointerLeave={() => { setAt(null); onHover(null); }} style={{ touchAction: "pan-y" }}>
        {[hi, lo].map((m) => (
          <g key={m}>
            <line x1={L} x2={W} y1={y(m)} y2={y(m)} stroke="currentColor" strokeOpacity="0.15" strokeDasharray="3 4" />
            <text x={L - 6} y={y(m) + 4} textAnchor="end" fontSize="12" fill="currentColor" opacity="0.6">{Math.round(m)} m</text>
          </g>
        ))}
        <polygon points={`${x(0)},${H - B} ${pts} ${x(maxX)},${H - B}`} fill="color-mix(in srgb, #f97316 22%, transparent)" />
        <polyline points={pts} fill="none" stroke="#f97316" strokeWidth="2.5" strokeLinejoin="round" />
        {[0, maxX / 2, maxX].map((km, i) => (
          <text key={i} x={x(km)} y={H - 4} textAnchor={i === 0 ? "start" : i === 2 ? "end" : "middle"} fontSize="12" fill="currentColor" opacity="0.6">{km.toFixed(km < 10 ? 1 : 0)} km</text>
        ))}
        {p && (
          <g>
            <line x1={x(p[0])} x2={x(p[0])} y1={0} y2={H - B} stroke="currentColor" strokeOpacity="0.5" />
            <circle cx={x(p[0])} cy={y(p[1])} r="5" fill="#f97316" stroke="#fff" strokeWidth="2" />
          </g>
        )}
      </svg>
      <div className="muted trail-profile__readout" aria-live="polite">{p ? `${p[0].toFixed(2)} km · ${Math.round(p[1])} m` : "Touch the chart to see where that is on the map"}</div>
    </figure>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return <div className="trail-stat"><div className="trail-stat__value">{value}</div><div className="trail-stat__label">{label}</div></div>;
}

const pace = (v: number | null) => (v ? `${Math.floor(v)}:${String(Math.round((v % 1) * 60)).padStart(2, "0")} /km` : "–");
const time = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

function WalkSheet({ id, onClose, onChanged, onDelete }: { id: string; onClose: () => void; onChanged: () => void; onDelete: (w: Walk) => void }) {
  const [w, setW] = useState<WalkDetail | null>(null);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [hover, setHover] = useState<Point | null>(null);
  const marker = useRef<L.CircleMarker | null>(null);
  useEffect(() => { void trails.get(id).then((x) => { setW(x); setName(x.name); setNote(x.note); }); }, [id]);
  const el = useMap((_, layer) => {
    marker.current = null;
    if (!w || w.route.length < 2) return null;
    const colour = w.kind === "hike" ? HIKE : WALK;
    L.polyline(w.route, { color: "#0f172a", weight: 8, opacity: 0.35 }).addTo(layer);   // a dark edge: readable on satellite
    const line = L.polyline(w.route, { color: colour, weight: 5 }).addTo(layer);
    for (const [km, lat, lon] of w.km_marks ?? []) {
      L.marker([lat, lon], { icon: L.divIcon({ className: "trail-km", html: String(km), iconSize: [20, 20] }), interactive: false }).addTo(layer);
    }
    const first = w.route[0], last = w.route[w.route.length - 1];
    if (w.loop) {
      L.circleMarker(first, { radius: 8, color: "#fff", weight: 2, fillColor: "#22c55e", fillOpacity: 1 }).bindTooltip("Start and finish").addTo(layer);
    } else {
      L.circleMarker(first, { radius: 7, color: "#fff", weight: 2, fillColor: "#22c55e", fillOpacity: 1 }).bindTooltip("Start").addTo(layer);
      L.circleMarker(last, { radius: 7, color: "#fff", weight: 2, fillColor: "#ef4444", fillOpacity: 1 }).bindTooltip("Finish").addTo(layer);
    }
    marker.current = L.circleMarker(first, { radius: 7, color: "#fff", weight: 3, fillColor: "#f97316", fillOpacity: 0, opacity: 0 }).addTo(layer);
    return line.getBounds();
  }, [w]);
  useEffect(() => {
    if (!marker.current) return;
    if (hover) marker.current.setLatLng([hover[2], hover[3]]).setStyle({ opacity: 1, fillOpacity: 1 });
    else marker.current.setStyle({ opacity: 0, fillOpacity: 0 });
  }, [hover]);
  async function save() {
    if (!w) return;
    if (name.trim() !== w.name || note !== w.note) { await trails.change(w.id, { name, note }); onChanged(); }
  }
  const close = () => { void save(); onClose(); };
  return (
    <Sheet label={w?.name ?? "Walk"} onClose={close}>
      <div className="stack trail-sheet">
        <header className="trail-head">
          {editing ? (
            <input className="field" value={name} autoFocus onChange={(e) => setName(e.target.value)} onBlur={() => { setEditing(false); void save(); }}
              onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} aria-label="Name" />
          ) : (
            <h2 className="trail-head__name">{name || "Walk"}
              <button type="button" className="icon-link" onClick={() => setEditing(true)} aria-label="Rename"><Pencil size={16} aria-hidden="true" /></button>
            </h2>
          )}
          {w && (
            <div className="trail-head__meta">
              <span className="chip" style={{ background: `color-mix(in srgb, ${w.kind === "hike" ? HIKE : WALK} 25%, transparent)` }}>{w.kind === "hike" ? "Hike" : "Walk"}{w.loop ? " · loop" : ""}</span>
              {w.place && <span><MapPin size={13} aria-hidden="true" /> {w.place}</span>}
              <span>{day(w.start)}, {time(w.start)}{w.end ? `–${time(w.end)}` : ""}</span>
            </div>
          )}
        </header>
        <div ref={el} className="trail-map trail-map--small" role="application" aria-label="Route" />
        {w && (
          <>
            <div className="trail-stats">
              <Stat value={n(w.km, "km", 2)} label="Distance" />
              <Stat value={hm(w.minutes)} label={w.moving_minutes ? `Time · ${hm(w.moving_minutes)} moving` : "Time"} />
              <Stat value={pace(w.pace_min_per_km)} label="Average pace" />
              <Stat value={n(w.ascent_m, "m")} label={`Ascent · ${n(w.descent_m, "m")} descent`} />
              <Stat value={n(w.highest_m, "m")} label={w.lowest_m != null ? `Highest · lowest ${w.lowest_m} m` : "Highest"} />
              {w.avg_hr ? <Stat value={`${w.avg_hr} bpm`} label={w.max_hr ? `Heart rate · max ${w.max_hr}` : "Heart rate"} /> : null}
              {w.kcal ? <Stat value={n(w.kcal, "kcal")} label="Active energy" /> : null}
            </div>
            <Profile profile={w.profile as Point[]} onHover={setHover} />
            {w.splits?.length > 1 && (
              <section aria-label="Splits">
                <div className="trail-section-title">Splits</div>
                <table className="trail-splits">
                  <thead><tr><th>km</th><th>Time</th><th>Pace</th><th>Climb</th></tr></thead>
                  <tbody>
                    {w.splits.map((s) => {
                      const fastest = Math.min(...w.splits.filter((x) => x.pace_min_per_km).map((x) => x.pace_min_per_km!));
                      return (
                        <tr key={s.km}>
                          <td>{s.length_km < 1 ? s.length_km.toFixed(2) : s.km}</td>
                          <td>{s.minutes != null ? hm(s.minutes).replace(/^0h /, "") : "–"}</td>
                          <td className={s.pace_min_per_km === fastest ? "trail-splits__best" : undefined}>{pace(s.pace_min_per_km)}</td>
                          <td>{s.up_m || s.down_m ? `↑${s.up_m} ↓${s.down_m}` : "–"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </section>
            )}
            <textarea className="field" rows={3} placeholder="Notes: the track, the weather, who came" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Notes" />
            <div className="row">
              <button type="button" className="button button--small button--primary" onClick={close}>Done</button>
              <span className="spacer" />
              <button type="button" className="button button--small" onClick={() => onDelete(w)}><Trash2 size={14} aria-hidden="true" /> Delete</button>
            </div>
            <p className="muted" style={{ margin: 0, fontSize: 12 }}>From {w.source === "apple_health_export" ? "the Apple Health export" : "Health Auto Export"}.{w.name_auto !== false && w.place ? " Named from OpenStreetMap; rename it any time." : ""}</p>
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
