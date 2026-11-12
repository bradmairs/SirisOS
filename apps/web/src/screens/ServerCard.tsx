import { HardDrive } from "lucide-react";
import { useResource } from "../api/resource";
import { machine } from "../api/machine";
import { Glass } from "../components/Glass";

/** The server itself (8.9): how full its disks are, and whether the local AI is all on the GPU. */
export function ServerCard() {
  const res = useResource("machine", (fresh) => machine.get(fresh), { staleMs: 60_000 });
  const m = res.data;
  if (!m) return null;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="The server">
      <header className="widget__head"><HardDrive aria-hidden="true" /><span>The server</span>
        <button type="button" className="button button--small" style={{ marginLeft: "auto" }} onClick={() => void res.reload(true)}>Check now</button></header>
      <ul className="items" aria-label="Disks">
        {m.disks.map((d) => (
          <li key={d.label} className="item server-disk">
            <span className="item__text"><span className="item__title">{d.label}: {d.free_gb} GB free of {d.total_gb} GB</span>
              <span className="server-disk__bar" role="meter" aria-valuenow={d.used_percent} aria-valuemin={0} aria-valuemax={100} aria-label={`${d.label} disk used`}>
                <span className={d.used_percent >= m.alert_percent ? "server-disk__fill--alert" : d.used_percent >= m.warn_percent ? "server-disk__fill--warn" : ""} style={{ width: `${d.used_percent}%` }} /></span></span>
            <span className={d.used_percent >= m.warn_percent ? "tone-warning" : "muted"}>{d.used_percent}%</span>
          </li>
        ))}
      </ul>
      {m.ollama.configured && (
        m.ollama.error ? <p className="tone-warning" style={{ margin: 0, fontSize: 14 }}>Ollama didn't answer: {m.ollama.error}</p>
          : !m.ollama.models.length ? <p className="muted" style={{ margin: 0, fontSize: 14 }}>The local AI has no model loaded right now.</p>
          : (
            <ul className="items" aria-label="Models loaded">
              {m.ollama.models.map((x) => (
                <li key={x.name} className="item">
                  <span className="item__text"><span className="item__title">{x.name}</span>
                    <span className={`item__subtitle ${x.on_gpu_percent < 98 ? "tone-warning" : ""}`}>{x.on_gpu_percent >= 98 ? `All ${x.size_gb} GB on the GPU` : `${x.ram_gb} GB in system RAM (${x.on_gpu_percent}% on the GPU)`}</span></span>
                </li>
              ))}
            </ul>
          )
      )}
    </Glass>
  );
}
