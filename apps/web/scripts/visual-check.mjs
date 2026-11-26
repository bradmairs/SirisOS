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
const PICTURE = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4pLSwzOko+MzZGNywtQFdBRkxOUlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0//wAARCAAkADADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDGooorgPrQooooAKKKKALvkRf3f1NHkRf3f1NS0VFzxPa1P5n95F5EX939TR5EX939TUtFFw9rU/mf3kXkRf3f1NHkRf3f1NS0UXD2tT+Z/eFFFFBmFFFFABRRRQB//9k=";
const SCREENS = ["/", "/brief", "/health", "/health?view=mind", "/health?view=habits", "/inbox", "/tasks", "/career", "/fitness", "/fitness?view=activity", "/gym", "/gym?view=routines", "/gym?view=history", "/gym?view=progress", "/gym?view=settings", "/gym/workout", "/gym/workout#one", "/status", "/assistant", "/wrapup", "/year", "/work", "/work?wrapup=1", "/budget", "/meals", "/travel", "/things", "/life", "/homelab", "/week"];
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
  exercises: [{ id: "bench-press", name: "Bench Press", primary: "chest", secondary: ["triceps", "shoulders"], equipment: "barbell", kind: "weight", custom: false, image: true },
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
const budgetFixture = {
  currency: "AUD",
  income: [{ id: "i1", name: "Salary", amount: 3000, every: "fortnightly", pay_day: "2026-11-06" }, { id: "i2", name: "Side work", amount: 400, every: "monthly" }],
  sections: {
    expenses: [{ id: "e1", name: "Rent", amount: 2000, every: "monthly" }, { id: "e2", name: "Power and gas", amount: 420, every: "quarterly" },
      { id: "e3", name: "Car rego", amount: 900, every: "yearly" }, { id: "e4", name: "Netflix", amount: 22.99, every: "monthly" }],
    savings: [{ id: "s1", name: "Holiday", amount: 500, every: "monthly", goal: 6000, saved: 1000 }, { id: "s2", name: "Emergency fund", amount: 300, every: "monthly", goal: 10000, saved: 7200 }],
    spending: [{ id: "p1", name: "Groceries", amount: 200, every: "weekly" }, { id: "p2", name: "Eating out", amount: 300, every: "monthly" }, { id: "p3", name: "Fuel", amount: 70, every: "weekly" }],
  },
  history: ["2026-07", "2026-08", "2026-09", "2026-10", "2026-11"].map((month, i) => ({ month, income: 6500 + i * 100, expenses: 2400 + i * 20, savings: 600 + i * 50, spending: 1450 - i * 30, left: 2050 + i * 60 })),
  totals: { income: 6900, expenses: 2408, savings: 800, spending: 1470, left: 2222 },
};
const thingsFixture = [{ id: 1, name: "Dishwasher", brand: "Bosch", model: "SMS6", room: "Kitchen", bought: "2025-01-10", price: 1099, shop: "Harvey Norman",
  warranty_until: "2026-11-20", manual: "https://bosch.example/manual", notes: "", document_id: null, warranty_days_left: 13, under_warranty: true }];
const peopleFixture = [{ id: 2, name: "Sam Lee", relation: "friend", birthday: "1990-11-12", anniversary: null, notes: "", last_contact: null, keep_in_touch_days: null, days_to_birthday: 5, turning: 36 }];
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
const lab = { clients: { total: 34, online: 21 }, sources: { network: true, servers: true, docker: true }, nodes: [
  { id: "internet", label: "Internet", kind: "internet", parent: null, online: true, found: "built in" },
  { id: "own:modem", label: "NBN modem", kind: "modem", parent: "internet", online: null, found: "you", model: "Arris CM8200" },
  { id: "net:gw", label: "UDM Pro", kind: "gateway", parent: "own:modem", online: true, found: "network", model: "UniFi Dream Machine Pro" },
  { id: "net:sw", label: "USW 24 PoE", kind: "switch", parent: "net:gw", online: true, found: "network", parent_guessed: true },
  { id: "net:ap1", label: "U6 Lite hallway", kind: "access_point", parent: "net:sw", online: true, found: "network", parent_guessed: true },
  { id: "net:ap2", label: "U6 Lite garage", kind: "access_point", parent: "net:sw", online: false, found: "network", parent_guessed: true },
  { id: "server:unraid", label: "unraid", kind: "server", parent: "net:sw", online: null, found: "terminal", detail: "192.168.0.100" },
  { id: "docker", label: "Docker", kind: "docker", parent: "server:unraid", online: true, found: "sirisai", detail: "41 of 43 containers running", parent_guessed: true },
  { id: "own:ups", label: "Eaton UPS", kind: "ups", parent: "net:sw", online: null, found: "you" }] };
const FIXTURES = [
  ["/api/v1/homelab", lab],
  ["/api/v1/plan/today", { date: "2026-11-24", readiness: 78, until: "20:00", free_minutes: 120, tasks: 4, events: [{ start: "09:00", end: "10:00" }],
    blocks: [{ start: "23:00", end: "23:15", minutes: 15, kind: "quick", title: "Call Sam back about the trailer", task_id: "t1", area: "personal" },
      { start: "23:15", end: "23:45", minutes: 30, kind: "errand", title: "Errands: Buy milk, Pick up the parcel", task_id: null, area: "personal" },
      { start: "23:45", end: "23:59", minutes: 14, kind: "goal", title: "Run about 8 km", task_id: null, area: "personal", goal: "Run 1,200 km" }],
    left: [{ id: "t4", title: "Write the drainage report", why: "No gap long enough today." }] }],
  ["/api/v1/away", { away: true, away_for: "2 days", keys: ["inbox:a1"], items: [
    { kind: "inbox", title: "2 things need you", lines: ["Backup failed on the NAS", "New device on IoT"], url: "/inbox" },
    { kind: "tasks", title: "Tasks: 1 overdue, 3 due today", lines: ["Pay rego", "Call Sam back", "Buy milk"], url: "/tasks" },
    { kind: "money", title: "Charges that went up", lines: ["Netflix: $18.99 → $22.99"], url: "/budget" }] }],
  ["/api/v1/patterns", { at: "2026-11-24T07:00", days: 120, sources: ["sleep_hours"], patterns: [
    { id: "drinks-hrv", text: "After drinking, your HRV next morning 57 ms on average, against 72 ms after a day without.", try: "Try a dry week and watch whether HRV comes back up.", strength: 1.2, worse: true, days: 99 },
    { id: "busy-sleep", text: "After a busy calendar, you slept 6.6 h on average, against 7.4 h after a lighter one.", try: "On busy days, keep the evening quiet and wind down on time.", strength: 0.6, worse: true, days: 88 }] }],
  ["/api/v1/goals/steer", { year: 2026, through_year: 90, goals: [], behind: [{ id: "g1", title: "Run 1,200 km", state: "behind", value: 900, target: 1200, unit: "km", projected: 1007.7, projected_percent: 84, weekly: 50, weeks_left: 6, step: { text: "Run 50 km this week: 4 runs of about 12 km." } }] }],
  ["/api/v1/home/usage", { on: true, phases: {} }],
  ["/api/v1/push/active", { inapp: [{ key: "task:t1", title: "Call the plumber about the hot water", body: "Before 5pm, they close early on Fridays.", url: "/tasks", at: "2026-11-21T01:00:00Z" }] }],
  ["/api/v1/weekend", { days: ["2026-11-28", "2026-11-29"], recover: false, note: null, readiness: { score: 72, band: "Steady" },
    routes: [{ id: "r1", name: "You Yangs loop", kind: "hike", hours: 2.5, km: 9, link: null, notes: "" }, { id: "r2", name: "Merri Creek walk", kind: "walk", hours: 1, km: 4, link: null, notes: "" }],
    windows: [{ date: "2026-11-28", start: "06:00", end: "10:00", hours: 4, low_c: 14, high_c: 19, rain_chance: 5, conditions: "mainly clear", score: 9,
      route: { id: "r1", name: "You Yangs loop", kind: "hike", hours: 2.5, km: 9, link: null, notes: "" } },
      { date: "2026-11-29", start: "14:00", end: "17:00", hours: 3, low_c: 20, high_c: 23, rain_chance: 10, conditions: "partly cloudy", score: 7,
      route: { id: "r1", name: "You Yangs loop", kind: "hike", hours: 2.5, km: 9, link: null, notes: "" } }] }],
  ["/api/v1/garden", { on: true, protocol: "Water the garden", last_watered: "2026-11-18", water: true, why: "Dry for days and none coming: give it a good drink.", past_mm: 0, coming_mm: 0, high_c: 27 }],
  ["/api/v1/fuel", { settings: { on: true, weekday: 2, leave: "06:00", fuel_type: "U91", first_km: 30, off_route_km: 1.5, destination: { name: "Shepparton", lat: -36.38, lon: 145.4 }, home: null },
    configured: true, attribution: "© State of Victoria accessed via the Victorian Government Service Victoria Platform", for: "2026-11-25",
    best: { id: "s2", name: "BP Wallan", brand: "BP", address: "", lat: -37.47, lon: 144.96, price: 176.5, updated: null, off_km: 0.9, km_in: 25.6, maps: "https://maps.apple.com/?daddr=-37.47,144.96" },
    options: [{ id: "s2", name: "BP Wallan", brand: "BP", address: "", lat: -37.47, lon: 144.96, price: 176.5, updated: null, off_km: 0.9, km_in: 25.6, maps: "https://maps.apple.com/?daddr=-37.47,144.96" },
      { id: "s1", name: "United Craigieburn", brand: "United", address: "", lat: -37.6, lon: 144.94, price: 181.9, updated: null, off_km: 0.2, km_in: 11.1, maps: "https://maps.apple.com/?daddr=-37.6,144.94" }],
    average: 179.2, saving_cents: 2.7, route_km: 30, note: "Prices are about a day old (Fair Fuel's open data)." }],
  ["/api/v1/bins", { bins: [{ kind: "rubbish", every_weeks: 1, first: "2026-11-06" }, { kind: "recycling", every_weeks: 2, first: "2026-11-06" }],
    next: { date: "2026-11-27", kinds: ["rubbish", "recycling"], text: "Rubbish and recycling" }, show: true, when: "tonight" }],
  ["/api/v1/bedroom", { temp_entity: "sensor.bedroom_temperature", humidity_entity: "sensor.bedroom_humidity", low: 17, high: 20, show: true, temp: 23.4, humidity: 52,
    advice: "Bedroom is 23.4°: fan or aircon for half an hour before bed?", bedtime: "22:30", best: { low: 18, high: 20, sleep: 7.6, other: 6.9, nights: 21 }, nights: 21 }],
  ["/api/v1/watch/tonight", { available: true, minutes_to_bed: 150, bedtime: "22:30", plex: true, on_deck: [], new_unwatched: [],
    picks: [{ title: "Slow Horses: S04E03", type: "episode", why: "Carry on where you left off" }, { title: "Dune: Part Two", type: "movie", why: "A film fits before bed" }],
    episodes: [{ series: "Severance", season: 2, number: 4, air_date: "2026-11-28" }], movies: [] }],
  ["/api/v1/lab/containers", { available: true, checked_at: "2026-11-21T02:00:00Z", running: false, up_to_date: ["plex"], skipped: {},
    updates: [{ container: "sonarr", image: "linuxserver/sonarr", current: "4.0.1", available: "4.0.2" }, { container: "radarr", image: "linuxserver/radarr" }] }],
  ["/api/v1/lab/internet", { available: true, speeds: [], outages: [{ start: "2026-11-19T03:00:00Z", end: "2026-11-19T03:12:00Z", seconds: 720 }], plan: { down: 100, up: 20 }, slow: ["2026-11-19", "2026-11-20"], share_of_plan: 52,
    daily: [["2026-11-14", 94], ["2026-11-15", 92], ["2026-11-16", 95], ["2026-11-17", 88], ["2026-11-18", 71], ["2026-11-19", 44], ["2026-11-20", 47], ["2026-11-21", 61]].map(([date, down]) => ({ date, down, up: 19, tests: 6 })) }],
  ["/api/v1/catchups", { available: true, keeping_up: 4, overdue: [{ id: 1, name: "Sam", relation: "friend", days_since: 86, gap: 30, over_by: 56 }],
    free: [{ date: "2026-11-28", part: "morning" }, { date: "2026-11-29", part: "afternoon" }] }],
  ["/api/v1/budget/pay-days", { currency: "AUD", pay_days: [], today: [{ id: "i1", name: "Salary", amount: 3000, every: "fortnightly", next: "2026-11-20", days: 0 }] }],
  ["/api/v1/meals/tonight", { dinner: { title: "Chicken stir fry", slug: "chicken-stir-fry" } }],
  ["/api/v1/meals/recipes", { configured: true, recipes: [] }],
  ["/api/v1/meals/shopping", { start: "2026-11-19", items: [], no_ingredients: [], lists: [], list: null, staples: ["salt"] }],
  ["/api/v1/meals", { start: "2026-11-19", staples: ["salt"], list: "todo.shopping_list", mealie: { configured: true, error: null },
    often: [{ title: "Spag bol", slug: "spag-bol", recipe_id: "r2", times: 3 }],
    days: ["2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24", "2026-11-25"].map((date, i) => ({ date,
      dinner: i === 0 ? { title: "Chicken stir fry with a long name for wrapping", slug: "chicken-stir-fry", source: "mealie", url: "http://mealie/g/home/r/chicken-stir-fry" }
        : i === 2 ? { title: "Tacos", source: "local", ingredients: ["Tortillas"] } : null })) }],
  ["/api/v1/travel/current", { trip: null }],
  ["/api/v1/travel", { next: { id: "abcdef1234", destination: "Hobart", place: "Hobart, Tasmania, Australia", country: "AU", start: "2026-11-27", end: "2026-11-30", notes: "",
    ooo_done: false, packing: [{ item: "4 sets of clothes", done: true }, { item: "Rain jacket", done: false }, { item: "Warm jacket", done: false }],
    days_to_go: 8, nights: 3, away: false, ooo_day: "2026-11-26", packed: 1, to_pack: 3,
    weather: { note: null, days: ["2026-11-27", "2026-11-28", "2026-11-29", "2026-11-30"].map((date) => ({ date, conditions: "Showers", high_c: 15, low_c: 7, rain_chance: 60, uv: 4 })) },
    bills: [{ date: "2026-11-28", name: "NETFLIX.COM MELBOURNE AUS CARD XX1234", amount: 25.99, kind: "charge" }] }, upcoming: [], past: [] }],
  ["/api/v1/recap", { month: "2026-10", title: "October 2026 recap", text: "- Slept 7.2 h a night (from 6.8).", filed_as: null, seen: false, show: false,
    money: null, health: null, work: { timesheet_hours: 0, cpd_hours: 0 }, habits: [] }],
  ["/api/v1/push/digest", { on: true, times: ["07:30", "18:00"], waiting: 0, titles: [] }],
  ["/api/v1/budget/cashflow", { ready: true, currency: "AUD", start: 400, as_of: "2026-11-19", per_day: 29.6, basis: "your spending over the last two months", next_pay: "2026-11-27",
    days: Array.from({ length: 15 }, (_, i) => ({ date: `2026-11-${String(19 + i > 30 ? 19 + i - 30 : 19 + i).padStart(2, "0")}`.replace("2026-11-0", "2026-12-0"), balance: i < 8 ? 400 - i * 33 : 2900 - (i - 8) * 30, events: [] })),
    low: { date: "2026-11-26", balance: 169 }, end: 2690, warn: true, low_mark: 200,
    bills: [{ date: "2026-11-21", name: "NETFLIX.COM MELBOURNE", amount: -25.99 }, { date: "2026-11-27", name: "ANYTIME FITNESS RICHMOND", amount: -32 }] }],
  ["/api/v1/budget/recurring", { per_month: 95.7, subscriptions_per_month: 26.37, flagged: 2, currency: "AUD", items: [
    { id: "r1", name: "NETFLIX.COM MELBOURNE AUS CARD XX1234", key: "netflix.com melbourne", every: "monthly", amount: 25.99, was: 22.99, per_month: 26.37, last: "2026-10-22", next: "2026-11-21", times: 3, line_id: null, line: null, subscription: true, status: null, flags: ["price_up", "not_in_budget", "check"] },
    { id: "r2", name: "ANYTIME FITNESS RICHMOND", key: "anytime fitness", every: "fortnightly", amount: 32, was: null, per_month: 69.57, last: "2026-11-13", next: "2026-11-27", times: 7, line_id: null, line: null, subscription: false, status: null, flags: ["not_in_budget"] }] }],
  ["/api/v1/budget/suggestions", { ready: true, currency: "AUD", months: ["2026-09", "2026-10"], items: [{ line_id: "p1", name: "Groceries", section: "spending", kind: "raise",
    plan: 866.67, average: 1104.2, amount: 254, every: "weekly", monthly: 1100, where: [{ shop: "Woolworths", per_month: 812.4 }, { shop: "Aldi", per_month: 291.8 }] }] }],
  ["/api/v1/budget/actuals", { month: "2026-11", through: 0.6, spent: 1240.5, currency: "AUD", has_data: true, months: ["2026-11", "2026-10"],
    lines: [{ id: "p1", name: "Groceries", section: "spending", plan: 866.67, spent: 1059.5, status: "over" },
      { id: "p3", name: "Fuel", section: "spending", plan: 303.33, spent: 211, status: "ahead" }, { id: "p2", name: "Eating out", section: "spending", plan: 300, spent: 96, status: "ok" }],
    over: [{ id: "p1", name: "Groceries", section: "spending", plan: 866.67, spent: 1059.5, status: "over" }],
    unsorted: [{ id: "t1", date: "2026-11-06", description: "JB HIFI 0042 MELBOURNE AUS CARD XX1234", amount: -39, account: "Everyday" }],
    unsorted_count: 1, guessed: [], dupes_removed: 0, imports: [
      { id: "abcdef1234", name: "CommBank-Everyday-November-2026-export.csv", account: "Everyday", at: "2026-11-20T09:00", added: 42, transactions: 42, first: "2026-11-01", last: "2026-11-19" },
      { id: "earlier", name: "Added before files were listed", account: "Bank", at: null, added: 6, transactions: 6, first: "2026-10-03", last: "2026-10-30" }] }],
  ["/api/v1/budget/balances", { currency: "AUD", net_worth: 61300, kinds: ["everyday", "savings", "super", "investment", "loan", "credit"],
    series: ["2026-07", "2026-08", "2026-09", "2026-10", "2026-11"].map((month, i) => ({ month, net_worth: 58000 + i * 820 })),
    accounts: [{ id: "a1", name: "Everyday", kind: "everyday", balance: 3962.5, as_of: "2026-11-12", per_month: null },
      { id: "a2", name: "Holiday saver", kind: "savings", line_id: "s1", balance: 2500, as_of: "2026-11-01", per_month: 496, goal: { line: "Holiday", target: 6000, percent: 42, eta: "Jun 2027", months: 7.1 } },
      { id: "a3", name: "Super", kind: "super", balance: 58837.5, as_of: "2026-10-31", per_month: 610 },
      { id: "a4", name: "Car loan", kind: "loan", balance: 4000, as_of: "2026-11-01", per_month: -350 }] }],
  ["/api/v1/budget", budgetFixture],
  ["/api/v1/tasks/lists", { lists: [{ entity_id: "todo.shopping_list", name: "Shopping list", items: [{ summary: "Milk", status: "needs_action" }, { summary: "Sourdough", status: "needs_action" }, { summary: "Eggs", status: "completed" }] }] }],
  ["/api/v1/life/things", thingsFixture],
  ["/api/v1/life/people", peopleFixture],
  ["/api/v1/work", workFixture],
  ["/api/v1/renewals", { renewals: [
    { id: "r1", name: "Car rego (Corolla)", kind: "rego", expires: "2026-11-20", note: "", days_left: 7, state: "soon" },
    { id: "r2", name: "Passport", kind: "passport", expires: "2029-03-02", note: "", days_left: 840, state: "fine" }] }],
  ["/api/v1/glance/key", { set: false, created: null }],
  ["/api/v1/mind/clarity", { started: null }],
  ["/api/v1/mind/journal", { journal: [] }],
  ["/api/v1/mind/habits", { habits: [
    { id: "h1", name: "Stretch for 10 minutes", created: "2026-10-01", streak: 6, best: 12, today: true, rate: 73,
      month: Array.from({ length: 30 }, (_, i) => ({ date: new Date(Date.UTC(2026, 9, 14 + i)).toISOString().slice(0, 10), done: i % 4 !== 1 })) },
    { id: "h2", name: "Read 20 pages", created: "2026-10-20", streak: 0, best: 4, today: false, rate: 35,
      month: Array.from({ length: 30 }, (_, i) => ({ date: new Date(Date.UTC(2026, 9, 14 + i)).toISOString().slice(0, 10), done: i > 8 && i % 3 === 0 })) }] }],
  ["/api/v1/mind", { available: true, today: { date: "2026-11-12", valence: 0.5, word: "Pleasant", mindful_minutes: 12, here_minutes: 2 },
    days: Array.from({ length: 30 }, (_, i) => ({ date: new Date(Date.UTC(2026, 9, 14 + i)).toISOString().slice(0, 10), valence: Math.round(Math.sin(i / 3) * 70) / 100,
      word: "Neutral", mindful_minutes: i % 3 ? 10 : 0, here_minutes: null })),
    week: { valence: 0.3, word: "Slightly pleasant", before: 0.1, mindful_minutes: 40, mindful_before: 20, mood_days: 6 },
    patterns: [{ key: "sleep", text: "Your mood is better after 7 hours' sleep or more than after less.", with: 0.5, without: -0.2, days: 20 }],
    journal_count: 3, locking: true, tools_minutes_week: 6 }],
  ["/api/v1/gym/last", { last: { "bench-press": { date: "2026-11-04", sets: [{ weight: 80, reps: 8, done: true, type: "normal" }, { weight: 80, reps: 7, done: true, type: "normal" }] } } }],
  ["/api/v1/gym/heatmap", heat],
  ["/api/v1/gym/strength", strength],
  ["/api/v1/work/timesheet", { week_of: "2026-11-16", today: "2026-11-18", hours: 13.5, text: "Mon 16 Nov (7.5 h)", recent_codes: ["GVW-123"],
    by_code: [{ code: "GVW-123", hours: 10 }, { code: "No code", hours: 3.5 }],
    days: [
      { date: "2026-11-16", hours: 7.5, entries: [{ id: "a", date: "2026-11-16", what: "Pump station review", hours: 4, code: "GVW-123" }, { id: "b", date: "2026-11-16", what: "Team meeting", hours: 3.5, code: "" }] },
      { date: "2026-11-17", hours: 0, entries: [] },
      { date: "2026-11-18", hours: 6, entries: [{ id: "c", date: "2026-11-18", what: "Hydraulic model calibration for the Melrose East catchment", hours: 6, code: "GVW-123" }] },
      { date: "2026-11-19", hours: 0, entries: [] }, { date: "2026-11-20", hours: 0, entries: [] }, { date: "2026-11-21", hours: 0, entries: [] }, { date: "2026-11-22", hours: 0, entries: [] }] }],
  ["/api/v1/gym/good-sessions", { scored: 41, health: true, note: null, findings: [
    { key: "sleep", text: "You lift about 4% more after 7 hours' sleep or more than after less.", gap: 4.1, with: 98.2, without: 94.1, sessions: 38, counts: "21 sessions after a good night, 17 after a short one" },
    { key: "morning", text: "You lift about 3% less before noon than later in the day.", gap: -2.6, with: 94.9, without: 97.5, sessions: 41, counts: "12 morning sessions, 29 later" }] }],
  ["/api/v1/gym/body", { measurements: [{ id: "a", date: "2026-08-01", waist: 88, chest: 104 }, { id: "b", date: "2026-11-01", waist: 84.5, chest: 106, arm: 38.5 }],
    photos: [], weight: Array.from({ length: 30 }, (_, i) => ({ date: `2026-10-${String(i + 1).padStart(2, "0")}`, kg: 83 - i * 0.05 + (i % 3) * 0.3, trend: 83 - i * 0.05 })) }],
  ["/api/v1/gym/year", yearReview],
  ["/api/v1/gym/sessions", { sessions: gymFixture.recent }],
  ["/api/v1/gym/templates", { templates: [] }],
  ["/api/v1/gym", gymFixture],
  ["/api/v1/health/today", { readiness: health.readiness, energy: health.energy, strain: health.strain ?? { today: 8.4, target: [10, 14], status: "under", advice: "", max_hr: 190, workouts: [], week: [] } }],
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
      // 11.7: the workout one exercise at a time.
      if (location.hash === "#one") localStorage.setItem("sirisos.gym.view", "focus"); else localStorage.removeItem("sirisos.gym.view");
      localStorage.setItem("sirisos.gym.active", JSON.stringify({ id: "w1", title: "Push, pull, legs: Push", started_at: new Date(Date.now() - 1500000).toISOString(), entries: [
        { exercise: "bench-press", group: "A", note: "Elbows in", sets: [{ weight: 20, reps: 10, done: true, type: "warmup" }, { weight: 82.5, reps: 8, done: true, type: "normal", rpe: 8 }, { weight: 82.5, reps: null, done: false, type: "normal" }, { weight: null, reps: null, hint: { weight: 82.5, reps: 7 }, done: false, type: "normal" }] },
        { exercise: "plank", group: "A", sets: [{ seconds: 60, done: false, type: "normal" }] }] }));
    });
    await ctx.route("**/api/**", (route) => {
      const path = new URL(route.request().url()).pathname;  // query strings aside
      // 9.71: an exercise's picture, so the workout's thumbnails are in the check (they once covered the name).
      if (/\/api\/v1\/gym\/exercises\/[^/]+\/image$/.test(path)) return route.fulfill({ status: 200, contentType: "image/jpeg", body: Buffer.from(PICTURE, "base64") });
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
