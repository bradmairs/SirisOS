import { useState } from "react";
import type { HubApp } from "../api/types";
import { AppGrid, useApps } from "./Home";
import { AppSheet } from "./AppSheet";

export function Engineering() {
  const { apps } = useApps(false);
  const [open, setOpen] = useState<HubApp | null>(null);
  const engineering = (apps ?? []).filter((a) => a.category === "engineering");
  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">Civil & water</p>
          <h1 className="page-head__title">Engineering</h1>
        </div>
      </header>
      {engineering.length > 0 && (
        <>
          <h2 className="section-title">Apps</h2>
          <AppGrid apps={engineering} onOpen={setOpen} />
        </>
      )}
      {open && <AppSheet appId={open.id} initial={open} onClose={() => setOpen(null)} />}
    </>
  );
}
