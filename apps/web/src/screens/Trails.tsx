import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Footprints, MapPin, MapPinned, Mountain, Pencil, Trash2, Trophy, Upload } from "lucide-react";
import { useResource } from "../api/resource";
import { trails, type TrailRecord, type Trails, type TrailsImport, type Walk, type WalkDetail } from "../api/trails";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";
import { Sheet } from "../components/Sheet";
import { undoable } from "../components/Undo";

/** SirisTrails (11.22): every walk of an hour or more and every hike, from Apple Health, on a map. */

const HIKE = "#f97316", WALK = "#38bdf8";
const hm = (min: number | null) => (min == null ? "–" : `${Math.floor(min / 60)}h ${String(Math.round(min % 60)).padStart(2, "0")}m`);
/** 12.2.3: a walk's date and times where it happened (the offset Apple Health recorded), not in this phone's time zone. */
const wallClock = (iso: string) => new Date(`${iso.slice(0, 19)}Z`);
/** In the walk's time zone (worked out from where it was); without one, as the time was recorded. */
const day = (iso: string, tz?: string | null) => (tz ? new Date(iso) : wallClock(iso)).toLocaleDateString(undefined,
  { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: tz || "UTC" });
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
    // 12.2: the world always fills the map: no grey above and below it when zoomed out.
    const fill = Math.max(1, Math.ceil(Math.log2(Math.max(el.current.clientHeight, el.current.clientWidth) / 256)));
    map.current = L.map(el.current, { worldCopyJump: true, layers: [layers.Topographic], minZoom: fill,
      maxBounds: [[-85, -10000], [85, 10000]], maxBoundsViscosity: 1 });
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
  const [focus, setFocusState] = useState<{ label: string; walks: Walk[] } | null>(null);
  const setFocus = (f: { label: string; walks: Walk[] } | null) => {  // 12.2.3: and show the map, which is above the list
    setFocusState(f);
    const map = f ? document.querySelector<HTMLElement>('[aria-label="Map of walks"]') : null;
    if (map && typeof map.scrollIntoView === "function") map.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const d = res.data;
  const walks = useMemo(() => (d?.walks ?? []).filter((w) => !gone.has(w.id)), [d, gone]);
  const reload = () => void res.reload(true);

  return (
    <>
      <PageHead eyebrow={d ? `${d.count} walk${d.count === 1 ? "" : "s"} and hikes` : "Walks and hikes"} title="SirisTrails" />
      {res.error && !d && <div className="error-banner" role="alert">{res.error}</div>}
      <div className="stack" style={{ marginTop: 16 }}>
        {d && d.years.length > 1 && (
          <div className="trail-years" role="tablist" aria-label="Year">
            <button type="button" role="tab" aria-selected={!year} className={`chip chip--button ${!year ? "chip--active" : ""}`} onClick={() => setYear(undefined)}>All years</button>
            {d.years.map((y) => <button key={y} type="button" role="tab" aria-selected={year === y} className={`chip chip--button ${year === y ? "chip--active" : ""}`} onClick={() => setYear(y)}>{y}</button>)}
          </div>
        )}
        {d && (
          <section className="trail-stats" aria-label="Totals">
            <Stat value={String(d.count)} label={`walks and hikes${d.hikes ? ` · ${d.hikes} hikes` : ""}`} />
            <Stat value={n(d.km, "km", 1)} label="walked" />
            <Stat value={n(d.hours, "h", 1)} label="on foot" />
            <Stat value={n(d.ascent_m, "m")} label="climbed" />
            <Stat value={n(d.highest_m, "m")} label="highest point" />
            <Stat value={n(d.longest_km, "km", 1)} label="longest walk" />
            <Stat value={n(d.avg_km, "km", 1)} label={`average walk${d.avg_minutes ? ` · ${hm(d.avg_minutes)}` : ""}`} />
            <Stat value={pace(d.avg_pace)} label="average pace" />
            <Stat value={String(d.countries)} label={d.countries === 1 ? "country" : "countries"} />
            <Stat value={String(d.regions)} label="states and regions" />
            <Stat value={String(d.places)} label="towns and suburbs" />
          </section>
        )}
        <OverviewMap walks={walks} onPick={setOpen} focus={focus} />
        {d && d.where.length > 0 && <WhereCard d={d} walks={walks} onFocus={setFocus} />}
        {d && <RecordsCard d={d} onPick={setOpen} />}
        {d && !year && d.by_year.length > 1 && <YearsCard d={d} onPick={setYear} />}
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
                      <span className="item__subtitle">{w.place ? `${w.place.split(",")[0]} · ` : ""}{day(w.start, w.tz)} · {n(w.km, "km", 1)} · {hm(w.minutes)}{w.ascent_m ? ` · ↑${w.ascent_m} m` : ""}{w.kind === "hike" ? " · hike" : ""}</span>
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

function OverviewMap({ walks, onPick, focus }: { walks: Walk[]; onPick: (id: string) => void; focus: { label: string; walks: Walk[] } | null }) {
  const el = useMap((_, layer) => {
    const all = L.latLngBounds([]), shown = L.latLngBounds([]);
    const ids = new Set((focus?.walks ?? []).map((w) => w.id));
    for (const w of walks) {
      if (w.line.length < 2) continue;
      const line = L.polyline(w.line, { color: w.kind === "hike" ? HIKE : WALK, weight: 4, opacity: 0.9 })
        .bindTooltip(`${w.name} · ${n(w.km, "km", 1)}`).on("click", () => onPick(w.id));
      line.addTo(layer);
      L.circleMarker(w.start_point, { radius: 4, color: "#fff", weight: 1, fillColor: w.kind === "hike" ? HIKE : WALK, fillOpacity: 1 }).addTo(layer);
      all.extend(line.getBounds());
      if (ids.has(w.id)) shown.extend(line.getBounds());
    }
    return focus && shown.isValid() ? shown : all;
  }, [walks, focus]);
  return (
    <Glass as="section" className="widget" style={{ padding: 0, overflow: "hidden" }} aria-label="Map of walks">
      <div ref={el} className="trail-map" role="application" aria-label="Map" />
      <div className="row muted" style={{ gap: 14, fontSize: 12, padding: "8px 14px", flexWrap: "wrap" }}>
        <span><span className="trail-dot" style={{ background: HIKE }} /> Hikes</span><span><span className="trail-dot" style={{ background: WALK }} /> Walks of an hour or more</span>
        {focus && <span style={{ marginLeft: "auto" }}>Showing {focus.label}</span>}
      </div>
    </Glass>
  );
}

/** 12.2: countries and their states, each tap zooming the map there. */
function WhereCard({ d, walks, onFocus }: { d: Trails; walks: Walk[]; onFocus: (f: { label: string; walks: Walk[] } | null) => void }) {
  const [open, setOpen] = useState<string | null>(d.where.length === 1 ? d.where[0].country : null);
  return (
    <Glass as="section" className="widget" aria-label="Where you've walked">
      <header className="widget__head"><MapPin aria-hidden="true" /><span>Where you've walked</span>
        <button type="button" className="widget__source icon-link" onClick={() => { setOpen(null); onFocus(null); }}>Whole map</button></header>
      <ul className="trail-where">
        {d.where.map((c) => (
          <li key={c.country}>
            <button type="button" className="trail-where__country" aria-expanded={open === c.country}
              onClick={() => { setOpen(open === c.country ? null : c.country); onFocus({ label: c.country, walks: walks.filter((w) => w.country === c.country) }); }}>
              <span className="trail-where__flag" aria-hidden="true">{c.flag || "🌏"}</span>
              <span className="trail-where__name">{c.country}</span>
              <span className="trail-where__nums">{c.walks} · {n(c.km, "km")} · {n(c.hours, "h")}</span>
            </button>
            {open === c.country && (
              <ul className="trail-where__regions">
                {c.regions.map((r) => (
                  <li key={r.region}>
                    <button type="button" onClick={() => onFocus({ label: `${r.region}, ${c.country}`, walks: walks.filter((w) => w.country === c.country && (w.region || "Elsewhere") === r.region) })}>
                      <span>{r.region}</span>
                      <span className="muted">{r.walks} walk{r.walks === 1 ? "" : "s"} · {n(r.km, "km", 1)}{r.places ? ` · ${r.places} place${r.places === 1 ? "" : "s"}` : ""}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </Glass>
  );
}

function RecordsCard({ d, onPick }: { d: Trails; onPick: (id: string) => void }) {
  const rows: [string, TrailRecord | null, (v: number) => string][] = [
    ["Longest walk", d.records.longest, (v) => n(v, "km", 1)],
    ["Longest time", d.records.longest_time, (v) => hm(v)],
    ["Most climbing", d.records.most_climbing, (v) => n(v, "m")],
    ["Highest walk", d.records.highest, (v) => n(v, "m")],
  ];
  if (!rows.some(([, r]) => r)) return null;
  return (
    <Glass as="section" className="widget" aria-label="Records">
      <header className="widget__head"><Trophy aria-hidden="true" /><span>Records</span></header>
      <ul className="items">
        {rows.filter(([, r]) => r).map(([label, r, fmt]) => (
          <li key={label}>
            <button type="button" className="item item--button" onClick={() => onPick(r!.id)}>
              <span className="item__text"><span className="item__title">{label}: {fmt(r!.value)}</span><span className="item__subtitle">{r!.name} · {day(r!.start, r!.tz)}</span></span>
            </button>
          </li>
        ))}
      </ul>
    </Glass>
  );
}

function YearsCard({ d, onPick }: { d: Trails; onPick: (y: number) => void }) {
  const max = Math.max(...d.by_year.map((y) => y.km), 1);
  return (
    <Glass as="section" className="widget" aria-label="By year">
      <header className="widget__head"><Footprints aria-hidden="true" /><span>By year</span></header>
      <ul className="trail-years-chart">
        {[...d.by_year].reverse().map((y) => (
          <li key={y.year}>
            <button type="button" onClick={() => onPick(y.year)} aria-label={`${y.year}: ${y.walks} walks, ${y.km} km`}>
              <span className="trail-years-chart__year">{y.year}</span>
              <span className="trail-years-chart__bar"><span style={{ width: `${(y.km / max) * 100}%` }} /></span>
              <span className="trail-years-chart__nums">{n(y.km, "km")} · {y.walks}</span>
            </button>
          </li>
        ))}
      </ul>
    </Glass>
  );
}

type Point = [number, number, number, number]; // km, metres, lat, lon

/** The elevation profile (12.1): smoothed heights, labelled axes, and a finger or pointer on it shows that spot. */
function Profile({ profile, onHover }: { profile: Point[]; onHover: (p: Point | null) => void }) {
  const [at, setAt] = useState<number | null>(null);
  if (profile.length < 2) return null;
  const W = 600, H = 220, maxX = profile[profile.length - 1][0] || 1;
  const eles = profile.map((p) => p[1]);
  const lo = Math.min(...eles), hi = Math.max(...eles);
  const span = Math.max(hi - lo, 40);                  // a flat walk stays flat on the chart
  const base = lo - (span - (hi - lo)) / 2;
  const x = (km: number) => (km / maxX) * W;
  const y = (m: number) => H - ((m - base) / span) * (H - 16) - 8;
  const pts = profile.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
  const pick = (clientX: number, rect: DOMRect) => {
    const km = ((clientX - rect.left) / rect.width) * maxX;
    let best = 0;
    for (let i = 1; i < profile.length; i++) if (Math.abs(profile[i][0] - km) < Math.abs(profile[best][0] - km)) best = i;
    setAt(best); onHover(profile[best]);
  };
  const p = at != null ? profile[at] : null;
  return (
    <figure className="trail-profile" style={{ margin: 0 }} aria-label="Elevation profile">
      <figcaption className="trail-profile__head">
        <span className="trail-section-title" style={{ margin: 0 }}>Elevation</span>
        <span className="muted">{Math.round(lo)} m to {Math.round(hi)} m</span>
      </figcaption>
      <div className="trail-profile__chart">
        <span className="trail-profile__y trail-profile__y--top">{Math.round(hi)} m</span>
        <span className="trail-profile__y trail-profile__y--bottom">{Math.round(lo)} m</span>
        <div className="trail-profile__plot">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height="140" role="img"
          aria-label={`Elevation from ${Math.round(lo)} m to ${Math.round(hi)} m over ${maxX.toFixed(1)} km`}
          onPointerMove={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
          onPointerDown={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
          onPointerLeave={() => { setAt(null); onHover(null); }} style={{ touchAction: "pan-y" }}>
          <line x1={0} x2={W} y1={y(hi)} y2={y(hi)} stroke="currentColor" strokeOpacity="0.18" strokeDasharray="4 5" vectorEffect="non-scaling-stroke" />
          <line x1={0} x2={W} y1={y(lo)} y2={y(lo)} stroke="currentColor" strokeOpacity="0.18" strokeDasharray="4 5" vectorEffect="non-scaling-stroke" />
          <polygon points={`0,${H} ${pts} ${W},${H}`} fill="color-mix(in srgb, #f97316 22%, transparent)" />
          <polyline points={pts} fill="none" stroke="#f97316" strokeWidth="2.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
          {p && <line x1={x(p[0])} x2={x(p[0])} y1={0} y2={H} stroke="currentColor" strokeOpacity="0.6" vectorEffect="non-scaling-stroke" />}
        </svg>
        {p && <span className="trail-profile__dot" style={{ left: `${(p[0] / maxX) * 100}%`, top: `${(y(p[1]) / H) * 100}%` }} />}
        </div>
      </div>
      <div className="trail-profile__x muted"><span>0 km</span><span>{(maxX / 2).toFixed(1)} km</span><span>{maxX.toFixed(1)} km</span></div>
      <div className="muted trail-profile__readout" aria-live="polite">{p ? `${p[0].toFixed(2)} km · ${Math.round(p[1])} m` : "Touch the chart to see where that is on the map"}</div>
    </figure>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return <div className="trail-stat"><div className="trail-stat__value">{value}</div><div className="trail-stat__label">{label}</div></div>;
}

/** 12.2.3: a split's time as m:ss (h:mm:ss over an hour) */
const mss = (minutes: number) => {
  const s = Math.round(minutes * 60), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
};
const pace = (v: number | null) => (v ? `${Math.floor(v)}:${String(Math.round((v % 1) * 60)).padStart(2, "0")} /km` : "–");
const time = (iso: string, tz?: string | null) => (tz ? new Date(iso) : wallClock(iso)).toLocaleTimeString(undefined,
  { hour: "numeric", minute: "2-digit", timeZone: tz || "UTC" });

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
      L.marker([lat, lon], { icon: L.divIcon({ className: "trail-km", html: `<span>${km}</span>`, iconSize: [22, 22], iconAnchor: [11, 11] }), interactive: false }).addTo(layer);
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
              <span>{day(w.start, w.tz)}, {time(w.start, w.tz)}{w.end ? `–${time(w.end, w.tz)}` : ""}</span>
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
                  <thead><tr><th>km</th><th>Pace</th><th>Climb</th></tr></thead>
                  <tbody>
                    {w.splits.map((s) => {
                      // whole kilometres only: a short last bit isn't a fair "fastest"
                      const fastest = Math.min(...w.splits.filter((x) => x.pace_min_per_km && x.length_km >= 1).map((x) => x.pace_min_per_km!));
                      return (
                        <tr key={s.km}>
                          <td>{s.length_km < 1 ? `${s.length_km.toFixed(2)} (${s.minutes != null ? mss(s.minutes) : "–"})` : s.km}</td>
                          <td className={s.length_km >= 1 && s.pace_min_per_km === fastest ? "trail-splits__best" : undefined}>{pace(s.pace_min_per_km)}</td>
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
