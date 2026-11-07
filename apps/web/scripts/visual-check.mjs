// Visual checks (6.0): open the main screens of the built app at phone and
// desktop widths, with the API answered from fixtures, and fail when a page
// scrolls sideways, a widget pokes out of the screen, the dock isn't at the
// bottom, or a screen throws. Screenshots land in visual-check/ (CI keeps
// them as an artifact). Run after `npm run build`: `npm run visual`.
import { spawn } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
// PLAYWRIGHT_MODULE points at an installed copy (e.g. a global one) when it isn't in node_modules.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");

const PORT = 4199;
const OUT = "visual-check";
const SCREENS = ["/", "/brief", "/health", "/inbox", "/tasks", "/career", "/training", "/gym", "/gym?view=routines", "/gym?view=history", "/gym?view=progress", "/gym?view=settings", "/gym/workout", "/status", "/assistant", "/wrapup", "/year", "/work", "/work?wrapup=1"];
// 7.5: an iPad too (the Work page is meant to stay open on one at work).
const SIZES = [{ name: "phone", width: 390, height: 844, mobile: true }, { name: "tablet", width: 820, height: 1180, mobile: true },
  { name: "desktop", width: 1280, height: 900, mobile: false }];
const health = JSON.parse(readFileSync("src/screens/__health_fixture.json", "utf8"));
const hud = { system: { cpu_percent: 7, memory: { percent_used: 41, used_gb: 13.1, total_gb: 32 }, disk: { "/": { percent_used: 63, used_gb: 590, total_gb: 937 } }, temperatures_celsius: {} } };
const LONG = "https://web.push.apple.com/QGZ2Yd0ab1cdEfGhIjKlMnOpQrStUvWxYz0123456789abcdefghijklmnopqrstuvwxyz0123456789";
const attention = { items: [
  { id: "1", source: "containers", kind: "suggestion", title: "22 container updates: sonarr, radarr, prowlarr, jellyfin, homeassistant, caddy and 16 more", body: LONG, severity: "info", actions: [{ id: "update", label: "Update all", style: "primary" }], created_at: "2026-10-31T05:00:00Z", updated_at: "2026-10-31T05:00:00Z", app: "sirisai", origin: "sirisai", url: null, link: null },
  { id: "2", source: "devices", kind: "alert", title: "New device: Espressif on IoT", body: "MAC: aa:bb:cc:dd:ee:ff", severity: "attention", actions: [{ id: "name", label: "Name it", style: "primary" }], created_at: "2026-10-31T05:00:00Z", updated_at: "2026-10-31T05:00:00Z", app: "sirisai", origin: "sirisai", url: null, link: null },
], counts: { open: 2, urgent: 0 } };
const gymFixture = {
  settings: { unit: "kg", bar: 20, plates: [25, 20, 15, 10, 5, 2.5, 1.25], increment: 2.5, rest_s: 90, current_gym: "home", warmups: true,
    warmup_steps: [{ percent: 0.4, reps: 5 }, { percent: 0.6, reps: 3 }, { percent: 0.8, reps: 2 }],
    gyms: [{ id: "home", name: "Home", bar: 20, plates: [25, 20, 15, 10, 5, 2.5, 1.25], dumbbells: [], stack_step: null },
      { id: "work", name: "Work gym", bar: 15, plates: [20, 10, 5, 2.5], dumbbells: [10, 12.5, 15, 17.5, 20], stack_step: 5 }] },
  exercises: [{ id: "bench-press", name: "Bench Press", primary: "chest", secondary: ["triceps", "shoulders"], equipment: "barbell", kind: "weight", custom: false },
    { id: "plank", name: "Plank", primary: "abs", secondary: [], equipment: "bodyweight", kind: "time", custom: false }],
  routines: [{ id: "r1", name: "Push, pull, legs", days: [{ name: "Push", exercises: [{ exercise: "bench-press", sets: 4, reps: "5-8", rest_s: 150 }] }], active: true }],
  active: { routine: "r1", next_day: 0, schedule: { today: 0, rest: false, next: { day: 0, date: "2026-11-06", weekday: "Thursday" },
    week: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((w, i) => ({ weekday: w, day: [0, 2, 4].includes(i) ? 0 : null, name: [0, 2, 4].includes(i) ? ["Push", "Pull", "Legs"][[0, 2, 4].indexOf(i)] : null })) } }, recent: [{ id: "s1", title: "Push, pull, legs: Push", date: "2026-11-02", started_at: "2026-11-02T07:00:00Z", minutes: 64, sets: 18, exercises: 5, volume: 9420, names: [] }],
  week: { week_of: "2026-11-02", sessions: 2, sets_by_muscle: { chest: 8, shoulders: 6, triceps: 5.5, back: 4 }, volume: 15200 }, streak_weeks: 6, total_sessions: 41,
  readiness: { score: 41, band: "Recover" }, deload: { active: false, until: null, suggest: true, why: ["bench Press has stalled for three sessions", "7 weeks of training in a row without a lighter week"] },
  muscles: [["chest", 12, "in range"], ["back", 4, "under"], ["shoulders", 9, "under"], ["quads", 22, "over"], ["triceps", 6, "under"]].map(([m, n, st]) => ({ muscle: m, sets: n, target: [10, 20], status: st })),
};
const strength = { bodyweight: 82, lifts: [
  { exercise: "back-squat", name: "Back Squat", best: 152.5, date: "2026-09-20", this_year: 152.5, last_year: 140, ratio: 1.86, level: "intermediate" },
  { exercise: "bench-press", name: "Bench Press", best: 116.7, date: "2026-10-02", this_year: 116.7, last_year: 105, ratio: 1.42, level: "intermediate" },
  { exercise: "pull-up", name: "Pull-up", best: 20, date: "2026-08-02", this_year: 20, last_year: null, ratio: 0.24, level: "novice" }] };
const yearReview = { year: 2026, sessions: 132, hours: 141.5, sets: 2650, volume: 512340, previous: { sessions: 110, hours: 118, sets: 2200, volume: 430000 },
  months: Array.from({ length: 12 }, (_, i) => ({ month: `2026-${String(i + 1).padStart(2, "0")}`, sessions: i < 10 ? 12 : 0, volume: i < 10 ? 38000 + (i % 4) * 6000 : 0, records: i % 3 === 0 ? 1 : 0 })),
  muscles: [{ muscle: "chest", sets: 520 }, { muscle: "back", sets: 480 }, { muscle: "quads", sets: 400 }],
  best: [{ exercise: "back-squat", name: "Back Squat", e1rm: 152.5, date: "2026-09-20" }, { exercise: "bench-press", name: "Bench Press", e1rm: 116.7, date: "2026-10-02" }] };
const heat = { days: Array.from({ length: 120 }, (_, i) => { const d = new Date(Date.now() - i * 3 * 86400000); return { date: d.toISOString().slice(0, 10), volume: 4000 + (i % 5) * 1500, sets: 18, muscles: ["chest"] }; }) };
const task = (id, title, due, group) => ({ id: `sirisos:${id}`, source: "sirisos", title, detail: null, due, time: null, group, area: "work" });
const workFixture = {
  date: "2026-11-05", local_time: "2026-11-05T16:20+11:00",
  hours: { start: "08:00", end: "16:30", on: true, workday: true, minutes_left: 10, minutes_in: 500 },
  tasks: { groups: { overdue: [task("a", "Send the Mooroopna pump station RFI response to the contractor", "2026-11-03", "overdue")],
    today: [task("b", "Check the pump station drawings", "2026-11-05", "today"), task("c", "Timesheet", "2026-11-05", "today")],
    week: [task("d", "Site visit: Kialla sewer main", "2026-11-07", "week")] }, counts: { overdue: 1, today: 2, week: 1 } },
  todos: [{ task: "Issue RFI 3", note: "GVW Sewer Upgrade", due: "2026-11-07" }, { task: "Update the valve schedule", note: "Pump Stations", due: null }],
  engineering: { current: { id: "p1", name: "Mooroopna pump station", kind: "water", tags: [] }, active: [] },
  cpd: { total: 112, required: 150, short: 38, minimums: [{ category: "area", label: "Area of practice", hours: 60, minimum: 50, short: 0 },
    { category: "risk", label: "Risk management", hours: 6, minimum: 10, short: 4 }, { category: "business", label: "Business & management", hours: 9, minimum: 15, short: 6 }] },
  week: { days: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d, i) => ({ date: `2026-11-0${i + 2}`, weekday: d, done: [3, 5, 2, 4, 0, 0, 0][i], focus_min: [50, 75, 25, 100, 0, 0, 0][i] })), done_today: 4, focus_today: 100 },
  apps: [{ id: "l1", name: "GVW", url: "https://gvw.example", icon: null, note: "" }, { id: "l2", name: "Timesheet", url: "https://ts.example", icon: null, note: "" }, { id: "l3", name: "Archive", url: "https://archive.example", icon: null, note: "" }],
  notes: [{ title: "Pump Stations", path: "Work/GVW/Pump Stations.md", type: "note", as_of: "2026-11-05", tags: [], excerpt: "Wet well levels and the duty/standby changeover." }],
  wrapup: { due: true, saved: null, next_workday: "2026-11-06" },
  chartership: { now: { percent: 50, solid: 5, elements: 16, evidence: 31 }, change: { percent: 13, solid: 2, since: "2026-10-08" },
    trend: Array.from({ length: 10 }, (_, i) => ({ week: `2026-${i < 4 ? "09" : "10"}-${String(1 + (i % 4) * 7).padStart(2, "0")}`, percent: 25 + i * 3, solid: 2 + Math.floor(i / 3), elements: 16, evidence: 20 })),
    next: "Add a second piece of evidence: a project or task where you did this",
    weakest: [{ id: "1.1", title: "Deal with ethical issues", strength: "none" }, { id: "2.3", title: "Develop safe and sustainable solutions", strength: "thin" }] },
};
const FIXTURES = [
  ["/api/v1/work", workFixture],
  ["/api/v1/gym/heatmap", heat],
  ["/api/v1/gym/strength", strength],
  ["/api/v1/gym/body", { measurements: [{ id: "a", date: "2026-08-01", waist: 88, chest: 104 }, { id: "b", date: "2026-11-01", waist: 84.5, chest: 106, arm: 38.5 }],
    photos: [], weight: Array.from({ length: 30 }, (_, i) => ({ date: `2026-10-${String(i + 1).padStart(2, "0")}`, kg: 83 - i * 0.05 + (i % 3) * 0.3, trend: 83 - i * 0.05 })) }],
  ["/api/v1/gym/year", yearReview],
  ["/api/v1/gym/sessions", { sessions: gymFixture.recent }],
  ["/api/v1/gym/templates", { templates: [] }],
  ["/api/v1/gym", gymFixture],
  ["/api/v1/health/today", { readiness: health.readiness, energy: health.energy }],
  ["/api/v1/health", health],
  ["/api/v1/assistant/hud", hud],
  ["/api/v1/attention", attention],
  ["/api/v1/hub/apps", { apps: [] }],
  ["/api/v1/brief/status", { show: false }],
];

const server = spawn("npx", ["vite", "preview", "--port", String(PORT), "--strictPort"], { stdio: "ignore" });
const failures = [];
try {
  await waitFor(`http://localhost:${PORT}/`);
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
  for (const size of SIZES) {
    const ctx = await browser.newContext({ viewport: { width: size.width, height: size.height }, isMobile: size.mobile, hasTouch: size.mobile, colorScheme: "dark" });
    await ctx.addInitScript(() => {
      localStorage.setItem("sirisos.token", "t"); localStorage.setItem("sirisos.user", "brad");
      localStorage.setItem("sirisos.gym.active", JSON.stringify({ id: "w1", title: "Push, pull, legs: Push", started_at: new Date(Date.now() - 1500000).toISOString(), entries: [
        { exercise: "bench-press", group: "A", note: "Elbows in", sets: [{ weight: 20, reps: 10, done: true, type: "warmup" }, { weight: 82.5, reps: 8, done: true, type: "normal", rpe: 8 }, { weight: 82.5, reps: null, done: false, type: "normal" }] },
        { exercise: "plank", group: "A", sets: [{ seconds: 60, done: false, type: "normal" }] }] }));
    });
    await ctx.route("**/api/**", (route) => {
      const path = new URL(route.request().url()).pathname;  // query strings aside
      const hit = FIXTURES.find(([p]) => path === p);
      return hit ? route.fulfill({ json: hit[1] }) : route.fulfill({ status: 404, json: { detail: "Not in the visual-check fixtures" } });
    });
    for (const screen of SCREENS) {
      const page = await ctx.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(`http://localhost:${PORT}${screen}`);
      await page.waitForTimeout(1200);
      const more = page.getByText(/^Show everything/);
      if (await more.count()) { await more.first().click(); await page.waitForTimeout(600); }  // Home hides some widgets by time of day
      const where = `${screen} (${size.name})`;
      const layout = await page.evaluate(() => {
        const width = document.documentElement.clientWidth;
        // Anything on the page past the screen's edge, unless it sits in its
        // own sideways-scrolling strip (chips, tables) or is the page itself.
        const shell = document.querySelector(".shell");
        const scrolls = (el) => {
          for (let p = el.parentElement; p && p !== shell; p = p.parentElement) {
            if (["auto", "scroll"].includes(getComputedStyle(p).overflowX)) return true;
          }
          return false;
        };
        const wide = [...document.querySelectorAll(".shell *, .dock")]
          .map((el) => ({ el, r: el.getBoundingClientRect() }))
          .filter(({ el, r }) => r.width > 0 && r.height > 0 && (r.right > width + 1 || r.left < -1) && !scrolls(el))
          .map(({ el, r }) => `${(typeof el.className === "string" && el.className) || el.tagName.toLowerCase()} (${Math.round(r.left)}–${Math.round(r.right)})`);
        const dock = document.querySelector(".dock");
        const d = dock && getComputedStyle(dock).display !== "none" ? dock.getBoundingClientRect() : null;
        return { scroll: document.documentElement.scrollWidth, width, wide: wide.slice(0, 5), dockBottom: d ? Math.round(innerHeight - d.bottom) : null };
      });
      if (layout.scroll > layout.width + 1) failures.push(`${where}: the page scrolls sideways (${layout.scroll}px wide on a ${layout.width}px screen)`);
      for (const w of layout.wide) failures.push(`${where}: pokes out of the screen: ${w}`);
      if (layout.dockBottom != null && (layout.dockBottom < 0 || layout.dockBottom > 60)) failures.push(`${where}: the dock is ${layout.dockBottom}px off the bottom`);
      for (const e of errors) failures.push(`${where}: threw ${e}`);
      await page.screenshot({ path: `${OUT}/${size.name}${screen === "/" ? "-home" : screen.replace(/[/?=]/g, "-")}.png`, fullPage: true });
      await page.close();
    }
    await ctx.close();
  }
  await browser.close();
} finally {
  server.kill();
}
if (failures.length) {
  console.error(`Visual check failed:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log(`Visual check passed: ${SCREENS.length} screens at ${SIZES.map((s) => s.width).join(" and ")}px.`);

async function waitFor(url) {
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch(url)).ok) return; } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`${url} didn't come up`);
}
