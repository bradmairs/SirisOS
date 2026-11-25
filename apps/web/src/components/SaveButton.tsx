import { useState } from "react";
import { Download } from "lucide-react";
import { save, share, type Saved } from "../api/save";

/**
 * A button that fetches a file and saves it (11.8.0): a download on a computer, the share sheet (Save to Files) on an
 * iPhone. When fetching took too long for iOS to open the share sheet, it turns into "Save …" to tap.
 */
export function SaveButton({ label, get, small = true, done }: {
  label: string; get: () => Promise<{ blob: Blob; name: string }>; small?: boolean; done?: (name: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const after = (r: Saved, name: string) => { if (r === "tap") return; setReady(null); if (r === "saved") done?.(name); };
  async function go() {
    setError(null);
    if (ready) {
      try { after(await share(ready), ready.name); } catch (e) { setError(e instanceof Error ? e.message : "Couldn't save it."); }
      return;
    }
    setBusy(true);
    try {
      const { blob, name } = await get();
      const r = await save(blob, name);
      if (r === "tap") setReady(new File([blob], name, { type: blob.type }));
      after(r, name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't download it.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <span className="row" style={{ gap: 6, alignItems: "center", flexWrap: "wrap" }}>
      <button type="button" className={`button${small ? " button--small" : ""}${ready ? " button--primary" : ""}`} onClick={go} disabled={busy}>
        <Download size={14} aria-hidden="true" /> {busy ? "Getting it…" : ready ? `Save ${ready.name}` : label}
      </button>
      {error && <span className="tone-critical" role="alert" style={{ fontSize: 13 }}>{error}</span>}
    </span>
  );
}
