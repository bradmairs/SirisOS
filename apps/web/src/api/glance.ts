import { api } from "./client";

/** The iPhone widget's feed (9.4): a read-only glance behind its own key. */
export const glance = {
  status: () => api<{ set: boolean; created: string | null }>("/api/v1/glance/key"),
  newKey: () => api<{ key: string }>("/api/v1/glance/key", { method: "POST" }),
  stop: () => api<{ set: boolean }>("/api/v1/glance/key", { method: "DELETE" }),
};

/** A Scriptable script that draws the widget from the feed. The rest timer counts down live on the widget itself. */
export function widgetScript(url: string): string {
  return `// SirisOS widget (Scriptable). Add a Scriptable widget to the Home Screen, choose this script.
const URL = ${JSON.stringify(url)};
const g = await new Request(URL).loadJSON();
const w = new ListWidget();
w.backgroundColor = new Color("#0b1220");
w.url = URL.split("/api/")[0];
const line = (text, size = 13, color = "#e6edf7") => { const t = w.addText(text); t.font = Font.systemFont(size); t.textColor = new Color(color); t.lineLimit = 1; return t; };
line("SirisOS", 11, "#6fd3ff");
if (g.rest) { const t = w.addDate(new Date(g.rest.until)); t.applyTimerStyle(); t.font = Font.boldSystemFont(22); t.textColor = new Color("#6fd3ff"); if (g.rest.next) line(g.rest.next, 11, "#9fb0c8"); }
if (g.readiness && g.readiness.score != null) line(\`Readiness \${g.readiness.score}\`, 15);
if (g.event) line(\`\${g.event.start.slice(11, 16)} \${g.event.title}\`);
if (g.tasks) line(g.tasks.next ? \`\${g.tasks.count} to do · \${g.tasks.next}\` : "Nothing due today");
if (g.gym && !g.gym.trained_today) line(\`Gym: \${g.gym.next}\`);
if (g.habits) line(\`Habits \${g.habits.done}/\${g.habits.of}\${g.habits.left.length ? " · " + g.habits.left[0] : ""}\`);
if (g.renewal) line(\`\${g.renewal.name}: \${g.renewal.days_left} days\`, 12, "#ffcf6b");
w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);
Script.setWidget(w);
Script.complete();
`;
}
