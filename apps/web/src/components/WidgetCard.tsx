import { ExternalLink } from "lucide-react";
import type { HubApp, Widget } from "../api/types";
import { isWidget } from "../api/types";
import { Glass } from "./Glass";
import { hueFor, iconFor } from "./icons";

export function WidgetCard({ app, delay = 0, showSource = true }: { app: HubApp; delay?: number; showSource?: boolean }) {
  const Icon = iconFor(app.icon);
  const widget = app.widget;
  return (
    <Glass as="section" className="widget" style={{ animationDelay: `${delay}ms` }} aria-label={`${app.name} widget`}>
      <header className="widget__head">
        <Icon style={{ color: hueFor(app.id) }} aria-hidden="true" />
        <span>{isWidget(widget) ? widget.title : app.name}</span>
        {showSource && app.launch_url && (
          <a className="widget__source" href={app.launch_url} target="_blank" rel="noreferrer">
            {app.name} <ExternalLink size={11} style={{ verticalAlign: "-1px" }} aria-hidden="true" />
          </a>
        )}
      </header>
      {isWidget(widget) ? <WidgetBody widget={widget} /> : <p className="muted">{widget && "error" in widget ? widget.error : app.status.detail || "No data"}</p>}
    </Glass>
  );
}

function WidgetBody({ widget }: { widget: Widget }) {
  return (
    <>
      {widget.metrics.length > 0 && (
        <div className="metrics">
          {widget.metrics.map((m) => (
            <div key={m.label} className={m.value.length > 7 ? "metric--long" : undefined}>
              <div className={`metric__value ${m.value.length > 7 ? "metric__value--long" : ""} ${m.tone !== "neutral" ? `tone-${m.tone}` : ""}`}>{m.value}</div>
              <div className="metric__label">{m.label}</div>
            </div>
          ))}
        </div>
      )}
      {widget.items.length > 0 ? (
        <ul className="items">
          {widget.items.map((item, i) => {
            const body = (
              <>
                <span className={`item__dot ${item.tone !== "neutral" ? `dot-${item.tone}` : ""}`} aria-hidden="true" />
                <span className="item__text">
                  <div className="item__title">{item.title}</div>
                  {item.subtitle && <div className="item__subtitle">{item.subtitle}</div>}
                </span>
              </>
            );
            return (
              <li key={`${item.title}-${i}`}>
                {item.url ? (
                  <a className="item" href={item.url} target="_blank" rel="noreferrer">
                    {body}
                  </a>
                ) : (
                  <div className="item">{body}</div>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        widget.metrics.length === 0 && <p className="muted">{widget.empty || "Nothing to show"}</p>
      )}
    </>
  );
}
