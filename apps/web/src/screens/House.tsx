import { useEffect, useMemo, useRef, useState } from "react";
import { Layers, Network as NetworkIcon, X } from "lucide-react";
import { useResource } from "../api/resource";
import { assistant } from "../api/hub";
import { house, rate, type NetNode, type Placements } from "../api/house";
import type { HomeControls } from "../api/types";
import { FLOORS, HOUSE, ROOMS, roomById, type FloorId } from "../house/layout";
import { guessRoom, markers, moved, spots } from "../house/placement";
import type { HouseScene, Pick } from "../house/scene";
import { Glass } from "../components/Glass";
import { useShowMore } from "../components/ShowMore";
import { HomeControlsWidget } from "./SirisControls";

const KIND_LABEL: Record<NetNode["kind"], string> = { gateway: "Gateway", switch: "Switch", access_point: "Access point", client: "Device" };

/** Home Assistant controls as devices in the house, linked to Home Assistant itself on the network. */
function controlNodes(controls: HomeControls | null | undefined, nodes: NetNode[]): NetNode[] {
  const ha = nodes.find((n) => /home ?assist[ae]nt/i.test(n.name));
  return (controls?.controls ?? []).map((c) => ({
    id: c.entity_id, name: c.name, kind: "client", model: c.kind, wired: null, online: c.state !== "unavailable",
    uplink: ha?.id ?? null, rx_bps: 0, tx_bps: 0,
  }));
}

/** The house in 3D (4.5): rotate, move and zoom; look in each floor; devices
 * in their rooms with their live network traffic. Devices close together are
 * grouped; tap one (or a group), then drag it to where it really is (4.7). */
export function HouseScreen() {
  const net = useResource("house:network", () => house.network(), { refreshMs: 5000, staleMs: 4000 });
  const controls = useResource("sirisai:controls", () => assistant.controls(), { refreshMs: 30_000, persist: true });
  const saved = useResource("house:placements", () => house.placements(), { staleMs: 60_000, persist: true });
  const [placements, setPlacements] = useState<Placements>({});
  useEffect(() => { if (saved.data) setPlacements(saved.data.placements); }, [saved.data]);

  const holder = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<HouseScene | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [floor, setFloor] = useState<FloorId | null>(null);
  const [linksOn, setLinksOn] = useState(true);
  const [picked, setPicked] = useState<Pick>(null);

  const nodes = useMemo(() => {
    const base = net.data?.nodes ?? [];
    return [...base, ...controlNodes(controls.data, base)];
  }, [net.data, controls.data]);
  const where = useMemo(() => spots(nodes, placements), [nodes, placements]);
  // The device being looked at is drawn on its own, so it can be dragged out of its group.
  const apart = picked?.type === "device" ? picked.id : null;
  const drawn = useMemo(() => markers(nodes, where, 2, apart ? [apart] : []), [nodes, where, apart]);
  const selectedIds = useMemo(() => (picked?.type === "device" ? [picked.id] : picked?.type === "group" ? picked.ids : []), [picked]);
  const dragged = useRef<(ids: string[], dx: number, dz: number) => void>(() => undefined);
  dragged.current = (ids, dx, dz) => save(moved(where, ids, dx, dz, placements));

  useEffect(() => {
    document.title = "Smart home · SirisOS";
    let gone = false;
    import("../house/scene").then(({ createHouseScene }) => {
      if (gone || !holder.current) return;
      try {
        sceneRef.current = createHouseScene(holder.current, setPicked, (ids, dx, dz) => dragged.current(ids, dx, dz));
      } catch {
        setProblem("This device can't draw 3D (WebGL is off or unsupported).");
      }
    }).catch(() => setProblem("Couldn't load the 3D view."));
    return () => { gone = true; sceneRef.current?.dispose(); sceneRef.current = null; };
  }, []);
  useEffect(() => { sceneRef.current?.setNetwork(nodes, drawn); }, [nodes, drawn, problem]);
  useEffect(() => { sceneRef.current?.setSelected(selectedIds); }, [selectedIds, drawn, problem]);
  useEffect(() => { sceneRef.current?.setFloor(floor); }, [floor]);
  useEffect(() => { sceneRef.current?.setLinksVisible(linksOn); }, [linksOn]);

  function save(next: Placements) {
    setPlacements(next);
    house.place(next).catch(() => undefined);
  }

  function move(id: string, room: string | null) {
    const next: Placements = { ...placements };
    if (room === null) next[id] = { ...(next[id] ?? { room: guessRoom(nodes.find((n) => n.id === id)!) }), hidden: true };
    else next[id] = { room };
    save(next);
  }

  const selectedNode = picked?.type === "device" ? nodes.find((n) => n.id === picked.id) : undefined;
  const selectedRoom = picked?.type === "room" ? roomById(picked.id) : undefined;
  const selectedGroup = picked?.type === "group" ? picked.ids.map((id) => nodes.find((n) => n.id === id)).filter((n): n is NetNode => !!n) : [];
  const inRoom = selectedRoom ? where.filter((s) => s.room.id === selectedRoom.id).map((s) => nodes.find((n) => n.id === s.id)!).filter(Boolean) : [];
  const wan = net.data?.wan;
  const listed = useShowMore([...nodes].sort((a, b) => (b.rx_bps + b.tx_bps) - (a.rx_bps + a.tx_bps)), 6);

  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{HOUSE.address}</p>
          <h1 className="page-head__title">Smart home</h1>
        </div>
      </header>

      <div className="house__bar" role="toolbar" aria-label="Floors">
        <Layers size={16} className="muted" aria-hidden="true" />
        {[{ id: null, name: "All" }, ...[...FLOORS].reverse()].map((f) => (
          <button key={f.name} type="button" className={`chip ${floor === f.id ? "chip--on" : ""}`} aria-pressed={floor === f.id} onClick={() => setFloor(f.id as FloorId | null)}>{f.name}</button>
        ))}
        <button type="button" className={`chip ${linksOn ? "chip--on" : ""}`} aria-pressed={linksOn} onClick={() => setLinksOn((x) => !x)} style={{ marginLeft: "auto" }}>
          <NetworkIcon size={13} aria-hidden="true" /> Network
        </button>
      </div>

      <div className="house">
        <div ref={holder} className="house__canvas" aria-label="3D model of the house: drag to rotate, two fingers or right-drag to move, pinch or scroll to zoom, double-tap a room to go to it" role="img" />
        {problem && <p className="house__problem muted">{problem}</p>}
        <p className="house__hint muted">Drag to turn · two fingers to move · pinch to zoom · tap a device, then drag it to move it</p>
        {(selectedNode || selectedRoom || selectedGroup.length > 0) && (
          <Glass className="house__panel" aria-label={selectedNode?.name ?? selectedRoom?.name ?? `${selectedGroup.length} devices`}>
            <button type="button" className="icon-link house__close" aria-label="Close" onClick={() => setPicked(null)}><X size={16} aria-hidden="true" /></button>
            {selectedNode && <DevicePanel node={selectedNode} room={where.find((s) => s.id === selectedNode.id)?.room.id ?? guessRoom(selectedNode)} onMove={(r) => move(selectedNode.id, r)} />}
            {selectedGroup.length > 0 && (
              <>
                <div className="item__title">{selectedGroup.length} devices together</div>
                <div className="item__subtitle">Drag them in the house to move them all, or pick one to move it on its own.</div>
                <ul className="items" style={{ marginTop: 6 }}>
                  {selectedGroup.map((n) => (
                    <li key={n.id}><button type="button" className="item house__pick" onClick={() => setPicked({ type: "device", id: n.id })}>
                      <span className="item__text"><div className="item__title">{n.name}</div><div className="item__subtitle">{KIND_LABEL[n.kind]} · {rate(n.rx_bps + n.tx_bps)}</div></span>
                    </button></li>
                  ))}
                </ul>
              </>
            )}
            {selectedRoom && (
              <>
                <div className="item__title">{selectedRoom.name}</div>
                <div className="item__subtitle">{FLOORS.find((f) => f.rooms.some((r) => r.id === selectedRoom.id))?.name} floor · {inRoom.length ? `${inRoom.length} device${inRoom.length === 1 ? "" : "s"}` : "no devices yet"}</div>
                {inRoom.length > 0 && (
                  <ul className="items" style={{ marginTop: 6 }}>
                    {inRoom.map((n) => (
                      <li key={n.id}><button type="button" className="item house__pick" onClick={() => setPicked({ type: "device", id: n.id })}>
                        <span className="item__text"><div className="item__title">{n.name}</div><div className="item__subtitle">{KIND_LABEL[n.kind]} · {rate(n.rx_bps + n.tx_bps)}</div></span>
                      </button></li>
                    ))}
                  </ul>
                )}
                <button type="button" className="button button--small" style={{ marginTop: 6 }} onClick={() => sceneRef.current?.focusRoom(selectedRoom.id)}>Look inside</button>
              </>
            )}
          </Glass>
        )}
      </div>

      <div className="stack" style={{ marginTop: 16 }}>
        {/* Off the main Home page since 4.8 (Siri and the Home app do this day to day); kept here. */}
        <HomeControlsWidget onHousePage />

        <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Network now">
          <header className="widget__head"><NetworkIcon aria-hidden="true" /><span>Network now</span></header>
          {!net.data && net.error && <p className="muted" style={{ margin: 0, fontSize: 14 }}>The network isn't available: SirisAI 2.76 or later with UniFi set up reads it.</p>}
          {net.data && !net.data.configured && <p className="muted" style={{ margin: 0, fontSize: 14 }}>UniFi isn't set up in SirisAI yet (SIRISAI_UNIFI_BASE_URL and SIRISAI_UNIFI_API_KEY).</p>}
          {net.data?.configured && (
            <>
              <div className="metrics">
                <div><div className="metric__value">{rate(wan?.rx_bps ?? 0)}</div><div className="metric__label">Down</div></div>
                <div><div className="metric__value">{rate(wan?.tx_bps ?? 0)}</div><div className="metric__label">Up</div></div>
                <div><div className="metric__value">{net.data.nodes.filter((n) => n.kind === "client").length}</div><div className="metric__label">Devices</div></div>
              </div>
              {net.data.guest_mode && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Guest mode: devices are hidden.</p>}
            </>
          )}
        </Glass>

        {nodes.length > 0 && (
          <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Devices">
            <header className="widget__head"><span>Devices, busiest first</span></header>
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>Each one goes in a room by its name. Pick a different room here, or hide one; to put it in its exact spot, tap it in the house and drag it.</p>
            <ul className="items">
              {listed.shown.map((n) => {
                const room = placements[n.id]?.hidden ? "" : (where.find((s) => s.id === n.id)?.room.id ?? guessRoom(n));
                return (
                  <li key={n.id} className="item">
                    <span className={`item__dot ${n.online ? "dot-good" : ""}`} aria-hidden="true" />
                    <button type="button" className="item__text house__pick" onClick={() => setPicked({ type: "device", id: n.id })}>
                      <div className="item__title">{n.name}</div>
                      <div className="item__subtitle">{KIND_LABEL[n.kind]}{n.model ? ` · ${n.model}` : ""} · ↓ {rate(n.rx_bps)} ↑ {rate(n.tx_bps)}</div>
                    </button>
                    <RoomSelect value={room} onChange={(r) => move(n.id, r)} label={`Room for ${n.name}`} />
                  </li>
                );
              })}
            </ul>
            {listed.toggle}
          </Glass>
        )}
      </div>
    </>
  );
}

function RoomSelect({ value, onChange, label }: { value: string; onChange: (room: string | null) => void; label: string }) {
  return (
    <select className="field house__room" value={value} aria-label={label} onChange={(e) => onChange(e.target.value || null)}>
      <option value="">Hidden</option>
      {FLOORS.map((f) => (
        <optgroup key={f.id} label={`${f.name} floor`}>
          {f.rooms.filter((r) => !r.id.startsWith("stairs")).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

function DevicePanel({ node: n, room, onMove }: { node: NetNode; room: string; onMove: (room: string | null) => void }) {
  return (
    <>
      <div className="item__title">{n.name}</div>
      <div className="item__subtitle">{KIND_LABEL[n.kind]}{n.model ? ` · ${n.model}` : ""}{n.online ? "" : " · offline"}</div>
      <div className="metrics" style={{ marginTop: 6 }}>
        <div><div className="metric__value">{rate(n.rx_bps)}</div><div className="metric__label">Down</div></div>
        <div><div className="metric__value">{rate(n.tx_bps)}</div><div className="metric__label">Up</div></div>
      </div>
      <RoomSelect value={room} onChange={onMove} label={`Room for ${n.name}`} />
      <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }}>Drag it in the house to put it exactly where it is.</p>
    </>
  );
}

export const _testing = { controlNodes, ROOMS };
