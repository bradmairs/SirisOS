/**
 * The house in 3D (4.5), built with three.js from layout.ts: a dollhouse
 * you can rotate (drag), move (two fingers or right-drag) and zoom (pinch
 * or scroll), one floor at a time or all four. Devices glow in their rooms;
 * links from the gateway carry particles that run faster and thicker with
 * live traffic, like the neurons on Siris' mind map.
 */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { FLOORS, HOUSE, type FloorId, type Furniture, type Room } from "./layout";
import { activity, type Spot } from "./placement";
import type { NetNode } from "../api/house";

export type Pick = { type: "room"; id: string } | { type: "device"; id: string } | null;

export interface HouseScene {
  setFloor(floor: FloorId | null): void;
  setNetwork(nodes: NetNode[], spots: Spot[]): void;
  setLinksVisible(on: boolean): void;
  focusRoom(roomId: string): void;
  dispose(): void;
}

const COLORS = {
  floor: 0x1c2733, floorOutdoor: 0x3a3127, wall: 0x9fb6c8, edge: 0x5fd3ff, furniture: 0x8a99a8, soft: 0xb9c6d2,
  car: 0x14181e, bed: 0x6c7a93, wood: 0x9c7b55, plant: 0x4f8a4a, glass: 0x7fd8ff,
  gateway: 0x5fd3ff, ap: 0x8ab4ff, switch: 0x9be3c3, client: 0xd6f3ff, offline: 0x5a6470, rx: 0x5fd3ff, tx: 0xffb454,
};
const FURNITURE_COLOR: Partial<Record<Furniture["kind"], number>> = {
  car: COLORS.car, bed: COLORS.bed, sofa: 0x7d8794, table: COLORS.wood, island: 0xe8ecef, bench: 0x4a4f57, tv: 0x0b0d10, bbq: 0x22262c,
  plant: COLORS.plant, robe: 0xc9cfd6, shower: COLORS.glass, toilet: 0xf2f4f6, vanity: 0xf2f4f6, cabinet: 0x30353d, chair: 0xcbb38f,
  desk: 0x23272e, stairs: 0x6b625a, door: 0xd9dde1, pergola: 0x2a2e35,
};

interface FloorGroup { id: FloorId; group: THREE.Group; level: number; height: number; materials: THREE.Material[] }

export function createHouseScene(container: HTMLElement, onPick: (p: Pick) => void): HouseScene {
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
  let devices: { id: string; mesh: THREE.Mesh; halo: THREE.Sprite; floorLevel: number; node: NetNode }[] = [];
  let links: { curve: THREE.QuadraticBezierCurve3; line: THREE.Line; points: THREE.Points; rx: number; tx: number; offsets: Float32Array; floors: [number, number] }[] = [];
  let showLinks = true;
  const haloTexture = glowTexture();

  function clearNetwork() {
    net.traverse((o) => {
      const m = o as THREE.Mesh;
      m.geometry?.dispose?.();
      const material = m.material as THREE.Material | THREE.Material[] | undefined;
      (Array.isArray(material) ? material : material ? [material] : []).forEach((x) => x.dispose());
    });
    net.clear();
    devices.forEach((d) => pickables.splice(pickables.indexOf(d.mesh), 1));
    devices = [];
    links = [];
  }

  function setNetwork(nodes: NetNode[], spots: Spot[]) {
    clearNetwork();
    const at = new Map(spots.map((s) => [s.id, s]));
    const gateway = nodes.find((n) => n.kind === "gateway");
    for (const n of nodes) {
      const s = at.get(n.id);
      if (!s) continue;
      const colour = !n.online ? COLORS.offline : n.kind === "gateway" ? COLORS.gateway : n.kind === "access_point" ? COLORS.ap : n.kind === "switch" ? COLORS.switch : COLORS.client;
      const size = n.kind === "gateway" ? 0.22 : n.kind === "client" ? 0.1 : 0.16;
      const mesh = new THREE.Mesh(new THREE.SphereGeometry(size, 20, 14), new THREE.MeshBasicMaterial({ color: colour, transparent: true }));
      mesh.position.set(s.x, s.y, s.z);
      mesh.userData = { pick: { type: "device", id: n.id } };
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTexture, color: colour, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false }));
      halo.scale.setScalar(size * 7);
      halo.position.copy(mesh.position);
      net.add(mesh, halo);
      pickables.push(mesh);
      devices.push({ id: n.id, mesh, halo, floorLevel: s.y - 1.1, node: n });
    }
    // A link from each device to what it connects through (or the gateway).
    for (const n of nodes) {
      const child = at.get(n.id);
      const parentId = n.kind === "gateway" ? null : n.uplink ?? gateway?.id ?? null;
      const parent = parentId ? at.get(parentId) : undefined;
      if (!child || !parent || parentId === n.id) continue;
      const a = new THREE.Vector3(parent.x, parent.y, parent.z), b = new THREE.Vector3(child.x, child.y, child.z);
      const mid = a.clone().lerp(b, 0.5);
      mid.y += 0.6 + a.distanceTo(b) * 0.25;
      const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(32)),
        new THREE.LineBasicMaterial({ color: n.online ? COLORS.edge : COLORS.offline, transparent: true, opacity: 0.18 + activity(n.rx_bps + n.tx_bps) * 0.4 }));
      const count = 2 + Math.round(activity(n.rx_bps + n.tx_bps) * 14);
      const offsets = new Float32Array(count).map((_, i) => i / count);
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
      geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
      const points = new THREE.Points(geometry, new THREE.PointsMaterial({ size: 0.16, map: haloTexture, vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
      net.add(line, points);
      links.push({ curve, line, points, rx: n.rx_bps, tx: n.tx_bps, offsets, floors: [parent.y - 1.1, child.y - 1.1] });
    }
    applyVisibility();
  }

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
      d.mesh.visible = d.halo.visible = v > 0;
      (d.mesh.material as THREE.Material).opacity = v;
      d.halo.material.opacity = v;
    }
    for (const l of links) {
      const v = Math.min(visibleLevel(l.floors[0]), visibleLevel(l.floors[1]));
      l.line.visible = l.points.visible = showLinks && v > 0;
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

  // -- picking: a tap (not a drag) picks a device or a room ------------------------------
  const raycaster = new THREE.Raycaster();
  let down: { x: number; y: number } | null = null;
  const onDown = (e: PointerEvent) => { down = { x: e.clientX, y: e.clientY }; };
  const pick = (e: { clientX: number; clientY: number }): Pick => {
    const rect = renderer.domElement.getBoundingClientRect();
    raycaster.setFromCamera(new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1), camera);
    const hit = raycaster.intersectObjects(pickables.filter((o) => isShown(o)), false)[0];
    return (hit?.object.userData.pick as Pick) ?? null;
  };
  const onUp = (e: PointerEvent) => {
    if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 6) return;
    onPick(pick(e));
  };
  const onDouble = (e: MouseEvent) => {
    const p = pick(e);
    if (p?.type === "room") focusRoom(p.id);
  };
  function isShown(o: THREE.Object3D): boolean {
    for (let x: THREE.Object3D | null = o; x; x = x.parent) if (!x.visible) return false;
    return (((o as THREE.Mesh).material as THREE.Material | undefined)?.opacity ?? 1) > 0.5;
  }
  renderer.domElement.addEventListener("pointerdown", onDown);
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
      if (!d.mesh.visible || reduced) continue;
      const a = activity(d.node.rx_bps + d.node.tx_bps);
      d.halo.scale.setScalar((d.node.kind === "gateway" ? 1.5 : d.node.kind === "client" ? 0.7 : 1.1) * (1 + a * 0.5 + Math.sin(now / (900 - a * 600)) * 0.08 * (0.3 + a)));
    }
    renderer.render(scene, camera);
    placeLabels();
  }
  frame = requestAnimationFrame(tick);

  return {
    setFloor,
    setNetwork,
    setLinksVisible(on) { showLinks = on; applyVisibility(); },
    focusRoom,
    dispose() {
      stopped = true;
      cancelAnimationFrame(frame);
      resize.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onDown);
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
