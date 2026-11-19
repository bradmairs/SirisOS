import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import type { MealWeek, Shopping } from "../api/meals";
import type { TripView } from "../api/travel";
import type { Recap } from "../api/recap";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { MealsScreen } from "./Meals";
import { TravelScreen, TripHomeCard } from "./Travel";
import { RecapCard } from "./RecapCard";

afterEach(() => { clearResources(); vi.restoreAllMocks(); vi.useRealTimers(); });

const today = new Date();
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const days = Array.from({ length: 7 }, (_, i) => { const d = new Date(today); d.setDate(d.getDate() + i); return iso(d); });

const week = (over: Partial<MealWeek> = {}): MealWeek => ({
  start: days[0], days: days.map((d) => ({ date: d, dinner: null })), often: [{ title: "Spag bol", slug: "spag-bol", recipe_id: "r2", times: 3 }],
  staples: ["salt"], list: null, mealie: { configured: true, error: null }, ...over,
});

describe("SirisOS 10.2", () => {
  it("plans tonight from a Mealie recipe and adds the shopping to Home Assistant's list", async () => {
    signIn();
    const planned = week({ days: days.map((d, i) => ({ date: d, dinner: i === 0 ? { title: "Chicken stir fry", slug: "chicken-stir-fry", source: "mealie", url: "http://m/g/home/r/chicken-stir-fry" } : null })) });
    const shopping: Shopping = { start: days[0], no_ingredients: [], list: "todo.shopping_list", staples: ["salt"],
      lists: [{ entity_id: "todo.shopping_list", name: "Shopping list" }],
      items: [{ key: "onion", name: "onions", lines: ["2 onions, sliced"], for: ["Chicken stir fry"], staple: false, on_list: false, need: true },
        { key: "salt", name: "salt", lines: ["Salt"], for: ["Chicken stir fry"], staple: true, on_list: false, need: false }] };
    const calls = mockFetch({
      "/api/v1/meals/recipes": () => jsonResponse({ configured: true, recipes: [{ id: "r1", slug: "chicken-stir-fry", name: "Chicken stir fry" }] }),
      [`/api/v1/meals/${days[0]}`]: () => jsonResponse(planned),
      "/api/v1/meals/shopping": (_u, init) => (init.method === "POST" ? jsonResponse({ added: 1, list: "todo.shopping_list" }) : jsonResponse(shopping)),
      "/api/v1/meals": () => jsonResponse(week()),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><MealsScreen /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Dinners this week" });
    await user.click(within(card).getAllByRole("button", { name: "Plan dinner" })[0]);
    await user.type(within(card).getByRole("textbox", { name: "Search your Mealie recipes" }), "chick");
    await user.click(await within(card).findByRole("button", { name: /Chicken stir fry/ }));
    expect(await within(card).findByRole("link", { name: "Chicken stir fry in Mealie" })).toHaveAttribute("href", "http://m/g/home/r/chicken-stir-fry");
    const put = calls.find((c) => c.url === `/api/v1/meals/${days[0]}`);
    expect(JSON.parse(String(put?.init.body))).toMatchObject({ title: "Chicken stir fry", slug: "chicken-stir-fry", recipe_id: "r1" });

    const shop = screen.getByRole("region", { name: "Shopping for the week" });
    await user.click(within(shop).getByRole("button", { name: "What do I need?" }));
    expect(await within(shop).findByText(/you always have this/)).toBeInTheDocument();
    await user.click(within(shop).getByRole("button", { name: "Add 1 to the list" }));
    expect(await within(shop).findByText("Added 1 to Shopping list.")).toBeInTheDocument();
    const post = calls.find((c) => c.url === "/api/v1/meals/shopping" && c.init.method === "POST");
    expect(JSON.parse(String(post?.init.body))).toEqual({ items: ["Onions"], list: "todo.shopping_list" });
  });

  it("says how to connect Mealie, and plans a plain dinner without it", async () => {
    signIn();
    const calls = mockFetch({
      [`/api/v1/meals/${days[1]}`]: () => jsonResponse(week({ mealie: { configured: false, error: null } })),
      "/api/v1/meals": () => jsonResponse(week({ mealie: { configured: false, error: null }, often: [] })),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><MealsScreen /></MemoryRouter>);
    expect(await screen.findByText(/Connect Mealie/)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Plan dinner" })[1]);
    await user.type(screen.getByRole("textbox", { name: "Dinner" }), "Tacos");
    await user.type(screen.getByRole("textbox", { name: "Ingredients" }), "Tortillas, cheese");
    await user.click(screen.getByRole("button", { name: "Plan it" }));
    const put = calls.find((c) => c.url === `/api/v1/meals/${days[1]}`);
    expect(JSON.parse(String(put?.init.body))).toMatchObject({ title: "Tacos", ingredients: ["Tortillas", "cheese"] });
  });

  const trip: TripView = {
    id: "abcdef1234", destination: "Hobart", place: "Hobart, Tasmania, Australia", country: "AU", start: "2026-11-27", end: "2026-11-30", notes: "",
    ooo_done: false, packing: [{ item: "Rain jacket", done: false }, { item: "Toiletries", done: true }], days_to_go: 5, nights: 3, away: false,
    weather: { days: [{ date: "2026-11-27", conditions: "Rain", high_c: 14, low_c: 6, rain_chance: 70, uv: 3 }], note: null },
    bills: [{ date: "2026-11-28", name: "NETFLIX.COM", amount: 25.99, kind: "charge" }], ooo_day: "2026-11-26", packed: 1, to_pack: 2,
  };

  it("shows a trip with weather, packing, bills and the out-of-office", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/travel/abcdef1234": () => jsonResponse({ ...trip, packing: [{ item: "Rain jacket", done: true }, { item: "Toiletries", done: true }], packed: 2 }),
      "/api/v1/travel": () => jsonResponse({ next: trip, upcoming: [trip], past: [] }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><TravelScreen /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Trip to Hobart" });
    expect(within(card).getByText("in 5 days · 3 nights")).toBeInTheDocument();
    expect(within(card).getByText(/Rain 70%/)).toBeInTheDocument();
    expect(within(card).getByText(/NETFLIX.COM/)).toBeInTheDocument();
    expect(within(card).getByText(/a reminder at 3pm/)).toBeInTheDocument();
    await user.click(within(card).getByRole("checkbox", { name: "Rain jacket" }));
    const patch = calls.find((c) => c.url === "/api/v1/travel/abcdef1234");
    expect(JSON.parse(String(patch?.init.body)).packing[0]).toEqual({ item: "Rain jacket", done: true });
  });

  it("puts the trip and last month on Home", async () => {
    signIn();
    const r: Recap = { month: "2026-10", title: "October 2026 recap", text: "- Slept 7.2 h a night (from 6.8).\n- Stretch: 3 of 11 days.", filed_as: "October 2026 recap",
      seen: false, show: true, money: null, health: null, work: { timesheet_hours: 0, cpd_hours: 0 }, habits: [] };
    const calls = mockFetch({
      "/api/v1/travel/current": () => jsonResponse({ trip }),
      "/api/v1/recap/2026-10/seen": () => jsonResponse({ seen: true }),
      "/api/v1/recap": () => jsonResponse(r),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><TripHomeCard /><RecapCard /></MemoryRouter>);
    expect(await screen.findByRole("region", { name: "Trip to Hobart" })).toBeInTheDocument();
    expect(screen.getByText("Packed 1 of 2", { exact: false })).toBeInTheDocument();
    const recap = await screen.findByRole("region", { name: "October in short" });
    expect(within(recap).getByText("Slept 7.2 h a night (from 6.8).")).toBeInTheDocument();
    await user.click(within(recap).getByRole("button", { name: "Got it" }));
    expect(screen.queryByRole("region", { name: "October in short" })).not.toBeInTheDocument();
    expect(calls.some((c) => c.url === "/api/v1/recap/2026-10/seen")).toBe(true);
  });
});
