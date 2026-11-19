import { CalendarCheck } from "lucide-react";
import { Glass } from "../components/Glass";
import { useResource } from "../api/resource";
import { recap } from "../api/recap";

/** Home (10.2): last month in short, the first week of the month until you've seen it. Also filed in Siris. */
export function RecapCard() {
  const res = useResource("recap:last", () => recap.get(), { staleMs: 60 * 60_000, persist: true });
  const r = res.data;
  if (!r || !r.show || typeof r.text !== "string") return null;
  const month = new Date(`${r.month}-01T00:00:00`).toLocaleDateString(undefined, { month: "long" });
  return (
    <Glass as="section" className="widget" aria-label={`${month} in short`}>
      <header className="widget__head"><CalendarCheck aria-hidden="true" /><span>{month} in short</span>
        {r.filed_as && <span className="widget__source">In Siris</span>}
      </header>
      <ul className="stack" style={{ gap: 4, margin: 0, paddingLeft: 18, fontSize: 14 }}>
        {r.text.split("\n").map((line) => <li key={line}>{line.replace(/^- /, "")}</li>)}
      </ul>
      <button type="button" className="button button--small" style={{ alignSelf: "flex-start" }} onClick={async () => {
        await recap.seen(r.month).catch(() => undefined);
        res.mutate({ ...r, show: false, seen: true });
      }}>Got it</button>
    </Glass>
  );
}
