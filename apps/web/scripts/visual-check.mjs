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
const SCREENS = ["/", "/brief", "/health", "/inbox", "/tasks", "/career", "/training", "/status", "/assistant", "/wrapup", "/year"];
const SIZES = [{ name: "phone", width: 390, height: 844, mobile: true }, { name: "desktop", width: 1280, height: 900, mobile: false }];
const health = JSON.parse(readFileSync("src/screens/__health_fixture.json", "utf8"));
const hud = { system: { cpu_percent: 7, memory: { percent_used: 41, used_gb: 13.1, total_gb: 32 }, disk: { "/": { percent_used: 63, used_gb: 590, total_gb: 937 } }, temperatures_celsius: {} } };
const LONG = "https://web.push.apple.com/QGZ2Yd0ab1cdEfGhIjKlMnOpQrStUvWxYz0123456789abcdefghijklmnopqrstuvwxyz0123456789";
const attention = { items: [
  { id: "1", source: "containers", kind: "suggestion", title: "22 container updates: sonarr, radarr, prowlarr, jellyfin, homeassistant, caddy and 16 more", body: LONG, severity: "info", actions: [{ id: "update", label: "Update all", style: "primary" }], created_at: "2026-10-31T05:00:00Z", updated_at: "2026-10-31T05:00:00Z", app: "sirisai", origin: "sirisai", url: null, link: null },
  { id: "2", source: "devices", kind: "alert", title: "New device: Espressif on IoT", body: "MAC: aa:bb:cc:dd:ee:ff", severity: "attention", actions: [{ id: "name", label: "Name it", style: "primary" }], created_at: "2026-10-31T05:00:00Z", updated_at: "2026-10-31T05:00:00Z", app: "sirisai", origin: "sirisai", url: null, link: null },
], counts: { open: 2, urgent: 0 } };
const FIXTURES = [
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
    await ctx.addInitScript(() => { localStorage.setItem("sirisos.token", "t"); localStorage.setItem("sirisos.user", "brad"); });
    await ctx.route("**/api/**", (route) => {
      const path = new URL(route.request().url()).pathname;
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
      await page.screenshot({ path: `${OUT}/${size.name}${screen === "/" ? "-home" : screen.replaceAll("/", "-")}.png`, fullPage: true });
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
