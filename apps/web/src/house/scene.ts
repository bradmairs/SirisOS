/**
 * The house in 3D (4.5), built with three.js from layout.ts: a dollhouse
 * you can rotate (drag), move (two fingers or right-drag) and zoom (pinch
 * or scroll), one floor at a time or all four. Devices are small models of
 * themselves (4.7), grouped when they sit close together; tap one, then drag
 * it to move it. Links from the gateway carry particles that run faster and
 * thicker with live traffic, like the neurons on Siris' mind map.
 */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { FLOORS, HOUSE, floorOf, type FloorId, type Furniture, type Room } from "./layout";
import { activity, type Marker } from "./placement";
import type { DeviceType } from "./devices";
import type { NetNode } from "../api/house";

export type Pick = { type: "room"; id: string } | { type: "device"; id: string } | { type: "group"; ids: string[] } | null;

export interface HouseScene {
  setFloor(floor: FloorId | null): void;
  setNetwork(nodes: NetNode[], markers: Marker[]): void;
  /** The devices picked: their marker gets a ring and can be dragged. */
  setSelected(ids: string[]): void;
  setLinksVisible(on: boolean): void;
  focusRoom(roomId: string): void;
  dispose(): void;
}

const COLORS = {
  floor: 0x1c2733, floorOutdoor: 0x3a3127, wall: 0x9fb6c8, edge: 0x5fd3ff, furniture: 0x8a99a8, soft: 0xb9c6d2,
  car: 0x14181e, bed: 0x6c7a93, wood: 0x9c7b55, plant: 0x4f8a4a, glass: 0x7fd8ff,
  gateway: 0x5fd3ff, ap: 0x8ab4ff, switch: 0x9be3c3, led: 0x7fe3ff, offline: 0x5a6470, rx: 0x5fd3ff, tx: 0xffb454,
};
const FURNITURE_COLOR: Partial<Record<Furniture["kind"], number>> = {
  car: COLORS.car, bed: COLORS.bed, sofa: 0x7d8794, table: COLORS.wood, island: 0xe8ecef, bench: 0x4a4f57, tv: 0x0b0d10, bbq: 0x22262c,
  plant: COLORS.plant, robe: 0xc9cfd6, shower: COLORS.glass, toilet: 0xf2f4f6, vanity: 0xf2f4f6, cabinet: 0x30353d, chair: 0xcbb38f,
  desk: 0x23272e, stairs: 0x6b625a, door: 0xd9dde1, pergola: 0x2a2e35,
};

interface FloorGroup { id: FloorId; group: THREE.Group; level: number; height: number; materials: THREE.Material[] }

/** Models are drawn larger than life so they read from across the house. */
const MODEL_SCALE = 1.5;
/** Where up to three models sit on a group's marker (model units, before scaling). */
const SLOTS = [[[0, 0]], [[-0.22, 0], [0.22, 0]], [[0, -0.12], [-0.25, 0.14], [0.25, 0.14]]];

export function createHouseScene(container: HTMLElement, onPick: (p: Pick) => void, onMove: (ids: string[], dx: number, dz: number) => void): HouseScene {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);
  renderer.domElement.style.touchAction = "none";

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 200);
  const centre = new THREE.Vector3(HOUSE.width / 2, 4.5, HOUSE.depth / 2);
  camera.position.set(-14, 16, -12);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.copy(centre);
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI * 0.49;
  controls.minDistance = 4;
  controls.maxDistance = 60;
  controls.update();

  scene.add(new THREE.HemisphereLight(0xdfefff, 0x1a1d22, 1.1));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(-10, 25, -8);
  scene.add(sun);

  // The ground around the house, and the street edge.
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshStandardMaterial({ color: 0x0e1318, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(HOUSE.width / 2, -0.01, HOUSE.depth / 2);
  scene.add(ground);
  const grid = new THREE.GridHelper(40, 40, 0x1d2a35, 0x141c24);
  grid.position.copy(ground.position);
  scene.add(grid);

  // Names on the rooms (one floor) or the floors (all of them), drawn as HTML over the canvas.
  const labelLayer = document.createElement("div");
  labelLayer.className = "house__labels";
  container.appendChild(labelLayer);
  const labels: { el: HTMLDivElement; at: THREE.Vector3; floor: FloorId; room: boolean }[] = [];
  for (const f of FLOORS) {
    const el = document.createElement("div");
    el.className = "house__label house__label--floor";
    el.textContent = f.name;
    labelLayer.appendChild(el);
    labels.push({ el, at: new THREE.Vector3(-0.4, f.level + 0.3, 0), floor: f.id, room: false });
    for (const r of f.rooms) {
      if (r.id.startsWith("stairs")) continue;
      const rel = document.createElement("div");
      rel.className = "house__label";
      rel.textContent = r.name;
      labelLayer.appendChild(rel);
      labels.push({ el: rel, at: new THREE.Vector3(r.x + r.w / 2, f.level + 0.25, r.z + r.d / 2), floor: f.id, room: true });
    }
  }
  const projected = new THREE.Vector3();
  function placeLabels() {
    const w = container.clientWidth, h = container.clientHeight;
    for (const l of labels) {
      const show = active === null ? !l.room : l.room && l.floor === active;
      if (!show) { l.el.style.display = "none"; continue; }
      projected.copy(l.at).project(camera);
      const behind = projected.z > 1;
      l.el.style.display = behind ? "none" : "block";
      l.el.style.transform = `translate(${((projected.x + 1) / 2) * w}px, ${((1 - projected.y) / 2) * h}px) translate(-50%, -50%)`;
    }
    for (const d of devices) {
      if (!d.badge) continue;
      projected.set(d.group.position.x, d.group.position.y + 0.75, d.group.position.z).project(camera);
      const show = d.shown > 0.5 && projected.z <= 1;
      d.badge.style.display = show ? "block" : "none";
      if (show) d.badge.style.transform = `translate(${((projected.x + 1) / 2) * w}px, ${((1 - projected.y) / 2) * h}px) translate(-50%, -50%)`;
    }
  }

  const pickables: THREE.Object3D[] = [];
  const floors: FloorGroup[] = FLOORS.map((f) => {
    const group = new THREE.Group();
    group.position.y = f.level;
    const materials: THREE.Material[] = [];
    const mat = <T extends THREE.Material>(m: T) => { materials.push(m); m.transparent = true; return m; };

    for (const room of f.rooms) {
      const tile = new THREE.Mesh(new THREE.BoxGeometry(room.w - 0.04, 0.12, room.d - 0.04),
        mat(new THREE.MeshStandardMaterial({ color: room.outdoor ? COLORS.floorOutdoor : COLORS.floor, roughness: 0.9 })));
      tile.position.set(room.x + room.w / 2, -0.06, room.z + room.d / 2);
      tile.userData = { pick: { type: "room", id: room.id }, room };
      group.add(tile);
      pickables.push(tile);

      // The room's outline at floor and ceiling, so walls read without hiding what's inside.
      const height = room.outdoor ? 1.1 : f.height;
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(room.w, height, room.d)),
        mat(new THREE.LineBasicMaterial({ color: room.outdoor ? COLORS.wood : COLORS.edge, opacity: room.outdoor ? 0.35 : 0.28 })));
      edges.position.set(room.x + room.w / 2, height / 2, room.z + room.d / 2);
      group.add(edges);
      for (const item of room.furniture ?? []) group.add(furniture(item, mat));
      if (room.walled) {
        const wall = new THREE.Mesh(new THREE.BoxGeometry(0.1, f.height, room.d),
          mat(new THREE.MeshStandardMaterial({ color: COLORS.wall, opacity: 0.22, depthWrite: false, side: THREE.DoubleSide })));
        wall.position.set(room.x + room.w, f.height / 2, room.z + room.d / 2);
        group.add(wall);
      }
    }

    // Faint outer walls on each storey (none for the open roof).
    if (f.id !== "roof") {
      const shell = new THREE.Mesh(new THREE.BoxGeometry(HOUSE.width, f.height, HOUSE.depth),
        mat(new THREE.MeshStandardMaterial({ color: COLORS.wall, opacity: 0.06, depthWrite: false, side: THREE.DoubleSide })));
      shell.position.set(HOUSE.width / 2, f.height / 2, HOUSE.depth / 2);
      group.add(shell);
    } else {
      const parapet = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(HOUSE.width, 1.1, HOUSE.depth)),
        mat(new THREE.LineBasicMaterial({ color: COLORS.soft, opacity: 0.5 })));
      parapet.position.set(HOUSE.width / 2, 0.55, HOUSE.depth / 2);
      group.add(parapet);
    }
    scene.add(group);
    return { id: f.id, group, level: f.level, height: f.height, materials };
  });

  // -- the network ---------------------------------------------------------------
  const net = new THREE.Group();
  scene.add(net);
  interface Device {
    marker: Marker; group: THREE.Group; hit: THREE.Mesh; halo: THREE.Sprite; ring: THREE.Mesh; badge: HTMLDivElement | null;
    materials: THREE.Material[]; floorLevel: number; rate: number; infra: boolean; shown: number;
  }
  let devices: Device[] = [];
  let links: { ends: [string, string]; curve: THREE.QuadraticBezierCurve3; line: THREE.Line; points: THREE.Points; rx: number; tx: number; offsets: Float32Array; floors: [number, number] }[] = [];
  let showLinks = true;
  let selected: string[] = [];
  const haloTexture = glowTexture();

  function clearNetwork() {
    net.traverse((o) => {
      const m = o as THREE.Mesh;
      m.geometry?.dispose?.();
      const material = m.material as THREE.Material | THREE.Material[] | undefined;
      (Array.isArray(material) ? material : material ? [material] : []).forEach((x) => x.dispose());
    });
    net.clear();
    devices.forEach((d) => { pickables.splice(pickables.indexOf(d.hit), 1); d.badge?.remove(); });
    devices = [];
    links = [];
  }

  function setNetwork(nodes: NetNode[], markers: Marker[]) {
    clearNetwork();
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const markerOf = new Map<string, Marker>();
    for (const m of markers) for (const id of m.ids) markerOf.set(id, m);
    const centre = (m: Marker) => new THREE.Vector3(m.x, m.y - 0.1, m.z);
    for (const m of markers) {
      const members = m.ids.map((id) => byId.get(id)).filter((n): n is NetNode => !!n);
      if (!members.length) continue;
      const lead = members.find((n) => n.kind !== "client") ?? members[0];
      const online = members.some((n) => n.online);
      const accent = !online ? COLORS.offline : lead.kind === "gateway" ? COLORS.gateway : lead.kind === "access_point" ? COLORS.ap : lead.kind === "switch" ? COLORS.switch : COLORS.led;
      const group = new THREE.Group();
      const types = m.types.slice(0, 3);
      types.forEach((t, i) => {
        const model = deviceModel(t, accent, online);
        const [ox, oz] = SLOTS[types.length - 1][i];
        model.position.set(ox, 0, oz);
        if (i > 0) model.scale.setScalar(0.8);
        group.add(model);
      });
      group.scale.setScalar(MODEL_SCALE);
      group.position.set(m.x, m.y - 0.35, m.z);
      const materials: THREE.Material[] = [];
      group.traverse((o) => {
        const material = (o as THREE.Mesh).material as THREE.Material | undefined;
        if (material) { material.transparent = true; materials.push(material); }
      });
      // An invisible ball to tap and drag: easier to hit than the model itself.
      const hit = new THREE.Mesh(new THREE.SphereGeometry(types.length > 1 ? 0.55 : 0.4, 12, 8), new THREE.MeshBasicMaterial({ visible: false }));
      hit.position.copy(centre(m));
      hit.userData = { pick: m.ids.length === 1 ? { type: "device", id: m.ids[0] } : { type: "group", ids: m.ids }, hitbox: true, shown: 1 };
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTexture, color: accent, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false }));
      halo.position.copy(centre(m));
      const ring = new THREE.Mesh(new THREE.RingGeometry(0.42, 0.5, 40), new THREE.MeshBasicMaterial({ color: COLORS.edge, transparent: true, side: THREE.DoubleSide, depthWrite: false }));
      ring.rotation.x = -Math.PI / 2;
      ring.position.set(m.x, m.y - 0.38, m.z);
      ring.scale.setScalar(types.length > 1 ? 1.4 : 1);
      ring.visible = false;
      let badge: HTMLDivElement | null = null;
      if (m.ids.length > 1) {
        badge = document.createElement("div");
        badge.className = "house__badge";
        badge.textContent = String(m.ids.length);
        labelLayer.appendChild(badge);
      }
      net.add(group, hit, halo, ring);
      pickables.push(hit);
      const rate = members.reduce((t, n) => t + n.rx_bps + n.tx_bps, 0);
      devices.push({ marker: m, group, hit, halo, ring, badge, materials, floorLevel: floorOf(m.floor).level, rate, infra: lead.kind !== "client", shown: 1 });
    }
    // A link from each marker to what its devices connect through (or the gateway), traffic added up.
    const gateway = nodes.find((n) => n.kind === "gateway");
    const joined = new Map<string, { from: Marker; to: Marker; rx: number; tx: number; online: boolean }>();
    for (const n of nodes) {
      const child = markerOf.get(n.id);
      const parentId = n.kind === "gateway" ? null : n.uplink ?? gateway?.id ?? null;
      const parent = parentId ? markerOf.get(parentId) : undefined;
      if (!child || !parent || parent === child) continue;
      const key = `${parent.key}>${child.key}`;
      const j = joined.get(key) ?? { from: parent, to: child, rx: 0, tx: 0, online: false };
      j.rx += n.rx_bps;
      j.tx += n.tx_bps;
      j.online ||= n.online;
      joined.set(key, j);
    }
    for (const { from, to, rx, tx, online } of joined.values()) {
      const a = centre(from), b = centre(to);
      const mid = a.clone().lerp(b, 0.5);
      mid.y += 0.6 + a.distanceTo(b) * 0.25;
      const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(32)),
        new THREE.LineBasicMaterial({ color: online ? COLORS.edge : COLORS.offline, transparent: true, opacity: 0.18 + activity(rx + tx) * 0.4 }));
      const count = 2 + Math.round(activity(rx + tx) * 14);
      const offsets = new Float32Array(count).map((_, i) => i / count);
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
      geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
      const points = new THREE.Points(geometry, new THREE.PointsMaterial({ size: 0.16, map: haloTexture, vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
      net.add(line, points);
      links.push({ ends: [from.key, to.key], curve, line, points, rx, tx, offsets, floors: [floorOf(from.floor).level, floorOf(to.floor).level] });
    }
    applyVisibility();
  }

  const isSelected = (d: Device) => selected.length > 0 && d.marker.ids.every((id) => selected.includes(id));

  // -- floors ----------------------------------------------------------------------
  let active: FloorId | null = null;
  const visibleLevel = (level: number) => {
    if (active === null) return 1;
    const sel = FLOORS.find((f) => f.id === active)!;
    if (Math.abs(level - sel.level) < 0.01) return 1;
    return level < sel.level ? 0.12 : 0;
  };
  function applyVisibility() {
    for (const f of floors) {
      const v = visibleLevel(f.level);
      f.group.visible = v > 0;
      for (const m of f.materials) {
        const base = (m.userData.baseOpacity ??= m.opacity);
        m.opacity = base * v;
      }
    }
    for (const d of devices) {
      const v = visibleLevel(d.floorLevel);
      d.shown = d.hit.userData.shown = v;
      d.group.visible = d.halo.visible = v > 0;
      for (const m of d.materials) m.opacity = v;
      d.halo.material.opacity = v * 0.7;
      d.ring.visible = v > 0.5 && isSelected(d);
    }
    for (const l of links) {
      const v = Math.min(visibleLevel(l.floors[0]), visibleLevel(l.floors[1]));
      l.line.visible = l.points.visible = showLinks && v > 0 && !(drag?.moved && l.ends.includes(drag.d.marker.key));
    }
  }

  let flight: { from: THREE.Vector3; to: THREE.Vector3; fromT: THREE.Vector3; toT: THREE.Vector3; start: number } | null = null;
  function flyTo(target: THREE.Vector3, distance: number) {
    const dir = camera.position.clone().sub(controls.target).normalize();
    if (dir.y < 0.45) dir.y = 0.6;
    dir.normalize();
    flight = { from: camera.position.clone(), to: target.clone().add(dir.multiplyScalar(distance)), fromT: controls.target.clone(), toT: target.clone(), start: performance.now() };
  }
  function setFloor(id: FloorId | null) {
    active = id;
    applyVisibility();
    if (id === null) flyTo(centre, 26);
    else {
      const f = FLOORS.find((x) => x.id === id)!;
      flyTo(new THREE.Vector3(HOUSE.width / 2, f.level + 0.5, HOUSE.depth / 2), 17);
    }
  }
  function focusRoom(roomId: string) {
    const f = FLOORS.find((x) => x.rooms.some((r) => r.id === roomId));
    const r = f?.rooms.find((x) => x.id === roomId);
    if (!f || !r) return;
    if (active !== f.id) { active = f.id; applyVisibility(); }
    flyTo(new THREE.Vector3(r.x + r.w / 2, f.level + 0.6, r.z + r.d / 2), Math.max(6, Math.max(r.w, r.d) * 1.6));
  }

  // -- picking: a tap (not a drag) picks a device or a room; a picked device drags ------
  const raycaster = new THREE.Raycaster();
  let down: { x: number; y: number } | null = null;
  let drag: { d: Device; pointer: number; plane: THREE.Plane; start: THREE.Vector3; dx: number; dz: number; moved: boolean } | null = null;
  const aim = (e: { clientX: number; clientY: number }) => {
    const rect = renderer.domElement.getBoundingClientRect();
    raycaster.setFromCamera(new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1), camera);
  };
  const pick = (e: { clientX: number; clientY: number }): Pick => {
    aim(e);
    const hit = raycaster.intersectObjects(pickables.filter((o) => isShown(o)), false)[0];
    return (hit?.object.userData.pick as Pick) ?? null;
  };
  const deviceAt = (e: { clientX: number; clientY: number }) => {
    aim(e);
    const hit = raycaster.intersectObjects(devices.filter((d) => d.shown > 0.5).map((d) => d.hit), false)[0];
    return hit ? devices.find((d) => d.hit === hit.object) : undefined;
  };
  // Runs before OrbitControls (capture, on the container) so dragging a device doesn't turn the house.
  const onDown = (e: PointerEvent) => {
    if (drag) { e.stopPropagation(); return; }
    down = { x: e.clientX, y: e.clientY };
    const d = deviceAt(e);
    if (!d || !isSelected(d)) return;
    e.stopPropagation();
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -d.hit.position.y);
    const start = raycaster.ray.intersectPlane(plane, new THREE.Vector3());
    if (!start) return;
    drag = { d, pointer: e.pointerId, plane, start, dx: 0, dz: 0, moved: false };
    try { renderer.domElement.setPointerCapture(e.pointerId); } catch { /* not a live pointer (tests) */ }
    renderer.domElement.style.cursor = "grabbing";
  };
  const onMovePointer = (e: PointerEvent) => {
    if (!drag) {
      if (e.pointerType === "mouse" && !e.buttons) {
        const d = deviceAt(e);
        renderer.domElement.style.cursor = d ? (isSelected(d) ? "grab" : "pointer") : "";
      }
      return;
    }
    if (e.pointerId !== drag.pointer || !down) return;
    if (!drag.moved && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 6) return;
    aim(e);
    const p = raycaster.ray.intersectPlane(drag.plane, new THREE.Vector3());
    if (!p) return;
    const { d } = drag;
    const dx = p.x - drag.start.x - drag.dx, dz = p.z - drag.start.z - drag.dz;
    drag.dx += dx;
    drag.dz += dz;
    for (const o of [d.group, d.hit, d.halo, d.ring]) { o.position.x += dx; o.position.z += dz; }
    if (!drag.moved) { drag.moved = true; applyVisibility(); }
  };
  const onUp = (e: PointerEvent) => {
    if (drag) {
      if (e.pointerId !== drag.pointer) return;
      const done = drag;
      drag = null;
      renderer.domElement.style.cursor = "";
      if (done.moved) onMove(done.d.marker.ids, done.dx, done.dz);
      else onPick(done.d.hit.userData.pick as Pick);
      applyVisibility();
      return;
    }
    if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 6) return;
    onPick(pick(e));
  };
  const onDouble = (e: MouseEvent) => {
    const p = pick(e);
    if (p?.type === "room") focusRoom(p.id);
  };
  function isShown(o: THREE.Object3D): boolean {
    if (o.userData.hitbox) return o.userData.shown > 0.5;
    for (let x: THREE.Object3D | null = o; x; x = x.parent) if (!x.visible) return false;
    return (((o as THREE.Mesh).material as THREE.Material | undefined)?.opacity ?? 1) > 0.5;
  }
  container.addEventListener("pointerdown", onDown, true);
  renderer.domElement.addEventListener("pointermove", onMovePointer);
  renderer.domElement.addEventListener("pointerup", onUp);
  renderer.domElement.addEventListener("dblclick", onDouble);

  // -- the loop --------------------------------------------------------------------
  const resize = new ResizeObserver(() => {
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  });
  resize.observe(container);
  const rxColour = new THREE.Color(COLORS.rx), txColour = new THREE.Color(COLORS.tx);
  const point = new THREE.Vector3();
  let frame = 0, last = performance.now(), stopped = false;
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  function tick(now: number) {
    if (stopped) return;
    frame = requestAnimationFrame(tick);
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    if (flight) {
      const t = Math.min(1, (now - flight.start) / 700), e = 1 - Math.pow(1 - t, 3);
      camera.position.lerpVectors(flight.from, flight.to, e);
      controls.target.lerpVectors(flight.fromT, flight.toT, e);
      if (t >= 1) flight = null;
    }
    controls.update();
    for (const l of links) {
      if (!l.points.visible) continue;
      const pos = l.points.geometry.getAttribute("position") as THREE.BufferAttribute;
      const col = l.points.geometry.getAttribute("color") as THREE.BufferAttribute;
      const down = activity(l.rx), up = activity(l.tx);
      const speed = reduced ? 0 : 0.08 + Math.max(down, up) * 0.9;
      for (let i = 0; i < l.offsets.length; i++) {
        l.offsets[i] = (l.offsets[i] + dt * speed) % 1;
        const upstream = i % 3 === 2 && up > 0;  // every third particle carries uploads back
        l.curve.getPoint(upstream ? 1 - l.offsets[i] : l.offsets[i], point);
        pos.setXYZ(i, point.x, point.y, point.z);
        const c = upstream ? txColour : rxColour;
        const glow = 0.35 + (upstream ? up : down) * 0.65;
        col.setXYZ(i, c.r * glow, c.g * glow, c.b * glow);
      }
      pos.needsUpdate = col.needsUpdate = true;
    }
    for (const d of devices) {
      if (!d.group.visible) continue;
      const a = activity(d.rate);
      const pulse = reduced ? 0 : Math.sin(now / (900 - a * 600)) * 0.08 * (0.3 + a);
      d.halo.scale.setScalar((d.infra ? 1.1 : 0.8) * (d.marker.ids.length > 1 ? 1.3 : 1) * (1 + a * 0.5 + pulse));
    }
    renderer.render(scene, camera);
    placeLabels();
  }
  frame = requestAnimationFrame(tick);

  return {
    setFloor,
    setNetwork,
    setSelected(ids) { selected = ids; applyVisibility(); },
    setLinksVisible(on) { showLinks = on; applyVisibility(); },
    focusRoom,
    dispose() {
      stopped = true;
      cancelAnimationFrame(frame);
      resize.disconnect();
      container.removeEventListener("pointerdown", onDown, true);
      renderer.domElement.removeEventListener("pointermove", onMovePointer);
      renderer.domElement.removeEventListener("pointerup", onUp);
      renderer.domElement.removeEventListener("dblclick", onDouble);
      controls.dispose();
      clearNetwork();
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        m.geometry?.dispose?.();
        const material = m.material as THREE.Material | THREE.Material[] | undefined;
        (Array.isArray(material) ? material : material ? [material] : []).forEach((x) => x.dispose());
      });
      haloTexture.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      labelLayer.remove();
    },
  };
}

function furniture(item: Furniture, mat: <T extends THREE.Material>(m: T) => T): THREE.Object3D {
  const colour = FURNITURE_COLOR[item.kind] ?? COLORS.furniture;
  const standard = () => mat(new THREE.MeshStandardMaterial({ color: colour, roughness: 0.7, opacity: item.kind === "shower" ? 0.35 : 1 }));
  const g = new THREE.Group();
  if (item.kind === "stairs") {
    const steps = 12;
    for (let i = 0; i < steps; i++) {
      const step = new THREE.Mesh(new THREE.BoxGeometry(item.w, 0.18, item.d / steps), standard());
      step.position.set(item.x + item.w / 2, 0.09 + i * 0.22, item.z + (i + 0.5) * (item.d / steps));
      g.add(step);
    }
    return g;
  }
  if (item.kind === "pergola") {
    for (const [px, pz] of [[0, 0], [item.w, 0], [0, item.d], [item.w, item.d]]) {
      const post = new THREE.Mesh(new THREE.BoxGeometry(0.12, item.h, 0.12), standard());
      post.position.set(item.x + px, item.h / 2, item.z + pz);
      g.add(post);
    }
    for (const [w, d, x, z] of [[item.w, 0.12, item.w / 2, 0], [item.w, 0.12, item.w / 2, item.d], [0.12, item.d, 0, item.d / 2], [0.12, item.d, item.w, item.d / 2]]) {
      const beam = new THREE.Mesh(new THREE.BoxGeometry(w + 0.12, 0.14, d + 0.12), standard());
      beam.position.set(item.x + x, item.h, item.z + z);
      g.add(beam);
    }
    return g;
  }
  const body = new THREE.Mesh(new THREE.BoxGeometry(item.w, item.kind === "car" ? item.h * 0.55 : item.h, item.d), standard());
  body.position.set(item.x + item.w / 2, (item.kind === "car" ? item.h * 0.55 : item.h) / 2 + (item.kind === "tv" ? 0.8 : 0), item.z + item.d / 2);
  g.add(body);
  if (item.kind === "car") {
    const cabin = new THREE.Mesh(new THREE.BoxGeometry(item.w * 0.9, item.h * 0.45, item.d * 0.5), mat(new THREE.MeshStandardMaterial({ color: 0x2a3442, roughness: 0.3, opacity: 1 })));
    cabin.position.set(item.x + item.w / 2, item.h * 0.55 + item.h * 0.22, item.z + item.d * 0.52);
    g.add(cabin);
  }
  if (item.kind === "bed") {
    const pillow = new THREE.Mesh(new THREE.BoxGeometry(item.w * 0.8, 0.12, 0.35), mat(new THREE.MeshStandardMaterial({ color: 0xe8ecf0, opacity: 1 })));
    pillow.position.set(item.x + item.w / 2, item.h + 0.06, item.z + 0.3);
    g.add(pillow);
  }
  return g;
}

/** A small model of a device, about 30 cm across, standing on y = 0 with its front (screen, lights) to the street. */
function deviceModel(type: DeviceType, accent: number, online: boolean): THREE.Group {
  const g = new THREE.Group();
  const white = online ? 0xe9eef2 : 0x6a737c, dark = online ? 0x262b32 : 0x3a4048, grey = online ? 0xaab3bc : 0x5a6470;
  const body = (color: number) => new THREE.MeshStandardMaterial({ color, roughness: 0.45, metalness: 0.1, emissive: color, emissiveIntensity: 0.12 });
  const glow = new THREE.MeshBasicMaterial({ color: accent });
  const screen = new THREE.MeshBasicMaterial({ color: online ? 0x2f7da6 : 0x2a3036 });
  const add = (geometry: THREE.BufferGeometry, material: THREE.Material, x = 0, y = 0, z = 0, parent: THREE.Object3D = g) => {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(x, y, z);
    parent.add(mesh);
    return mesh;
  };
  const box = (w: number, h: number, d: number, m: THREE.Material, x = 0, y = h / 2, z = 0, parent?: THREE.Object3D) => add(new THREE.BoxGeometry(w, h, d), m, x, y, z, parent);
  const cyl = (r: number, h: number, m: THREE.Material, x = 0, y = h / 2, z = 0) => add(new THREE.CylinderGeometry(r, r, h, 28), m, x, y, z);
  const ringOn = (r: number, y: number) => { const t = add(new THREE.TorusGeometry(r, 0.008, 8, 40), glow, 0, y, 0); t.rotation.x = -Math.PI / 2; };
  const led = (x: number, y: number, z: number) => add(new THREE.SphereGeometry(0.012, 8, 6), glow, x, y, z);
  /** A flat panel facing the street with a screen on it. */
  const panel = (w: number, h: number, y: number, frame = dark, x = 0) => { box(w, h, 0.015, body(frame), x, y, 0); box(w * 0.92, h * 0.88, 0.002, screen, x, y, -0.009); };

  switch (type) {
    case "gateway":
      box(0.3, 0.1, 0.22, body(white));
      box(0.2, 0.012, 0.004, glow, 0, 0.05, -0.112);
      break;
    case "switch":
      box(0.36, 0.06, 0.2, body(dark));
      for (let i = 0; i < 8; i++) box(0.026, 0.018, 0.004, glow, -0.14 + i * 0.04, 0.03, -0.101);
      break;
    case "ap":
      cyl(0.17, 0.045, body(white));
      ringOn(0.12, 0.047);
      break;
    case "phone":
      box(0.1, 0.2, 0.012, body(dark));
      box(0.088, 0.18, 0.002, screen, 0, 0.1, -0.007);
      break;
    case "tablet":
      box(0.2, 0.26, 0.012, body(dark));
      box(0.185, 0.24, 0.002, screen, 0, 0.13, -0.007);
      break;
    case "watch":
      box(0.035, 0.15, 0.012, body(grey), 0, 0.075, 0.006);
      box(0.06, 0.072, 0.022, body(dark), 0, 0.075, -0.004);
      box(0.05, 0.06, 0.002, screen, 0, 0.075, -0.016);
      break;
    case "laptop": {
      box(0.28, 0.015, 0.19, body(grey));
      const lid = new THREE.Group();
      lid.position.set(0, 0.015, 0.095);
      lid.rotation.x = 0.25;
      g.add(lid);
      box(0.28, 0.18, 0.01, body(grey), 0, 0.09, 0, lid);
      box(0.26, 0.16, 0.002, screen, 0, 0.09, -0.006, lid);
      break;
    }
    case "desktop":
      box(0.1, 0.012, 0.08, body(dark), -0.06, 0.006);
      box(0.02, 0.1, 0.02, body(dark), -0.06, 0.05);
      panel(0.32, 0.2, 0.19, dark, -0.06);
      box(0.1, 0.26, 0.22, body(dark), 0.2, 0.13);
      box(0.006, 0.2, 0.004, glow, 0.2, 0.13, -0.111);
      break;
    case "server":
      box(0.2, 0.24, 0.24, body(dark));
      for (let i = 0; i < 3; i++) box(0.14, 0.008, 0.004, glow, 0, 0.06 + i * 0.06, -0.121);
      break;
    case "console":
      box(0.08, 0.28, 0.2, body(white));
      box(0.035, 0.282, 0.204, body(dark));
      box(0.004, 0.24, 0.004, glow, 0, 0.14, -0.103);
      break;
    case "streamer":
      box(0.12, 0.045, 0.12, body(dark));
      led(0, 0.022, -0.061);
      break;
    case "tv":
      box(0.14, 0.01, 0.07, body(dark));
      box(0.025, 0.06, 0.02, body(dark), 0, 0.04);
      panel(0.46, 0.27, 0.2);
      break;
    case "frame":
      box(0.06, 0.012, 0.06, body(dark), 0, 0.006);
      panel(0.24, 0.17, 0.1, 0x6b5a45);
      break;
    case "speaker":
      cyl(0.075, 0.15, body(dark));
      cyl(0.04, 0.004, glow, 0, 0.152);
      break;
    case "hub":
      box(0.13, 0.035, 0.13, body(white));
      led(0, 0.036, 0);
      break;
    case "plug":
      box(0.08, 0.1, 0.05, body(white));
      box(0.008, 0.02, 0.004, body(dark), -0.015, 0.06, -0.026);
      box(0.008, 0.02, 0.004, body(dark), 0.015, 0.06, -0.026);
      led(0, 0.025, -0.026);
      break;
    case "light":
      cyl(0.028, 0.06, body(grey));
      add(new THREE.SphereGeometry(0.065, 20, 14), new THREE.MeshBasicMaterial({ color: online ? 0xffd88a : 0x5a6470 }), 0, 0.12, 0);
      break;
    case "climate":
      box(0.42, 0.13, 0.11, body(white));
      box(0.36, 0.01, 0.004, body(dark), 0, 0.025, -0.056);
      led(0.17, 0.1, -0.056);
      break;
    case "vacuum":
      cyl(0.15, 0.05, body(dark));
      ringOn(0.1, 0.052);
      cyl(0.03, 0.02, body(grey), 0, 0.06);
      break;
    case "camera": {
      box(0.08, 0.08, 0.11, body(white), 0, 0.06);
      const lens = add(new THREE.CylinderGeometry(0.028, 0.028, 0.02, 20), body(dark), 0, 0.06, -0.064);
      lens.rotation.x = Math.PI / 2;
      led(0.025, 0.088, -0.056);
      break;
    }
    case "sensor":
      box(0.08, 0.08, 0.025, body(white));
      led(0, 0.04, -0.013);
      break;
    case "appliance":
      box(0.18, 0.32, 0.17, body(white));
      box(0.18, 0.004, 0.172, body(grey), 0, 0.21);
      box(0.012, 0.08, 0.012, body(grey), 0.07, 0.26, -0.09);
      break;
    case "printer":
      box(0.26, 0.12, 0.2, body(white));
      box(0.18, 0.01, 0.004, body(dark), 0, 0.08, -0.101);
      led(0.1, 0.1, -0.101);
      break;
    default:
      box(0.12, 0.12, 0.12, body(white));
      led(0, 0.06, -0.061);
  }
  return g;
}

function glowTexture(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.25, "rgba(255,255,255,0.6)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(canvas);
}

export type { Room };
