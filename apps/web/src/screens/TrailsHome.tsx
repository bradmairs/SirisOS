import { Footprints } from "lucide-react";
import { Link } from "react-router-dom";
import { useResource } from "../api/resource";
import { trails } from "../api/trails";
import { Glass } from "../components/Glass";

/** Home (12.6): your last walk and the year so far, from SirisTrails. Shown once there's a walk in the last 60 days. */
export function TrailsHomeCard() {
  const res = useResource("trails:home", () => trails.home(), { staleMs: 30 * 60_000, persist: true });
  const h = res.data;
  if (!h || !h.latest) return null;
  const last = h.latest;
  if (Date.now() - Date.parse(last.start) > 60 * 86_400_000) return null;
  const when = new Date(last.start).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", timeZone: last.tz || undefined });
  const mins = last.minutes ?? 0;
  return (
    <Glass as="section" className="widget" aria-label="Walks">
      <header className="widget__head"><Footprints aria-hidden="true" /><span>Walks</span>
        <Link className="widget__source icon-link" to="/trails">SirisTrails</Link></header>
      <Link to="/trails" className="item item--button" style={{ textDecoration: "none", color: "inherit" }}>
        <span className="item__text">
          <span className="item__title">{last.name}</span>
          <span className="item__subtitle">
            {when} · {last.km ?? "–"} km · {Math.floor(mins / 60)}h {String(Math.round(mins % 60)).padStart(2, "0")}m
            {last.weather ? ` · ${last.weather.icon} ${Math.round(last.weather.temp_c)}°` : ""}
            {last.times ? ` · ${last.best ? "your best of" : "walked"} ${last.times}${last.best ? "" : " times"}` : ""}
          </span>
        </span>
      </Link>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        {h.year.year}: {h.year.walks} walk{h.year.walks === 1 ? "" : "s"} · {h.year.km.toLocaleString()} km · {h.year.ascent_m.toLocaleString()} m climbed
        {h.wishlist.open ? ` · ${h.wishlist.open} on your wishlist` : ""}
      </p>
    </Glass>
  );
}
