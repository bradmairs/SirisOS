import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import type { Health } from "../api/health";
import fixture from "./__health_fixture.json";
import { HealthScreen, ReadinessWidget } from "./Health";

const data = fixture as unknown as Health;

describe("<HealthScreen />", () => {
  it("shows readiness with what drove it, then sleep, fitness and vitals", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/health": () => jsonResponse(data) });
    const user = userEvent.setup();
    render(<MemoryRouter><HealthScreen /></MemoryRouter>);
    const ring = await screen.findByRole("img", { name: new RegExp(`^Readiness ${data.readiness!.score} out of 100, ${data.readiness!.band}$`) });
    expect(ring).toBeInTheDocument();
    expect(screen.getByText(data.readiness!.advice)).toBeInTheDocument();
    expect(screen.getAllByText(/HRV 71 ms/)[0]).toBeInTheDocument();
    expect(screen.getByText(/Kept from this morning/)).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Energy 58 out of 100" })).toBeInTheDocument();
    expect(screen.getByText(/started at 84/)).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Sleep" }));
    const last = await screen.findByRole("region", { name: "Last night" });
    expect(within(last).getByText("7h 54m")).toBeInTheDocument();
    expect(within(last).getByText(/Asleep 10:38 pm to 6:41 am/)).toBeInTheDocument();
    const nights = screen.getByRole("list", { name: "Hours asleep each night" });
    await user.hover(within(nights).getAllByRole("listitem")[0]);
    expect(screen.getByText(/· need 7h 30m/)).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Fitness" }));
    expect(await screen.findByText("Outdoor Run")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Vitals" }));
    expect(await screen.findByRole("region", { name: "VO₂ max" })).toBeInTheDocument();
  });

  it("5.8: warns of illness, shows bedtime, weight, insights and goals, and logs and exports through SirisAI", async () => {
    signIn();
    clearResources();
    const more: Health = {
      ...data,
      getting_sick: { date: data.today, today: ["wrist temperature +0.6 °C", "HRV 22% down"], yesterday: ["resting heart rate +5 bpm", "HRV 18% down"] },
      bedtime: { bedtime: "22:20", wake: "06:00", sleep_target_h: 7.75, debt_7d: 0.5, because: "Site visit at 07:15", text: "Bed by 22:20 for 7.8 h before Site visit at 07:15 (06:00)." },
      weight: { latest: 79.4, latest_date: data.today, trend: 79.8, per_week: -0.25, goal_kg: 76, to_go_kg: 3.8, weeks_to_goal: 15, series: [] },
      insights: [{ factor: "late_meeting", minutes: -38, nights_with: 6, nights_without: 31, text: "After a meeting past 8pm you sleep 38 minutes less (6 nights vs 31)." }],
      logged: { water_ml: 750, caffeine_mg: 160, alcohol_drinks: null, mood: 4, notes: [{ id: 1, day: data.today, kind: "symptom", text: "Sore throat", at: "x" }] },
    };
    const calls = mockFetch({
      "/api/v1/health/goals": (_u, init) => jsonResponse(init?.method === "POST" ? { goal: {} } : { goals: [
        { goal_id: 3, metric: "running_km", target: 1000, start: "2026-01-01", end: "2026-12-31", title: "1,000 km run by 2026-12-31", done: 702, expected_by_now: 830, percent: 70.2, on_pace: false, needed_per_week: 32 }] }),
      "/api/v1/health/log": () => jsonResponse({ logged: {} }),
      "/api/v1/health/data": () => jsonResponse({ readings: 12, workouts: 1 }),
      "/api/v1/health": () => jsonResponse(more),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><HealthScreen /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("fighting something off: wrist temperature +0.6 °C, HRV 22% down");
    expect(screen.getByRole("region", { name: "Tonight" })).toHaveTextContent("22:20");
    expect(screen.getByRole("region", { name: "Weight" })).toHaveTextContent("79.8 kg");
    expect(screen.getByRole("region", { name: "Weight" })).toHaveTextContent("3.8 kg to go, about 15 weeks");
    expect(screen.getByText(/After a meeting past 8pm you sleep 38 minutes less/)).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Fitness" }));
    expect(await screen.findByText(/behind: 32 a week to make it/)).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Log" }));
    expect(await screen.findByText("0.75 L")).toBeInTheDocument();
    expect(screen.getByText("Sore throat")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "+250 ml water" }));
    const log = calls.find((c) => c.url === "/api/v1/health/log");
    expect(JSON.parse(String(log!.init.body))).toEqual({ kind: "water", amount: 250, text: "" });
    await user.type(screen.getByRole("textbox", { name: "Note" }), "Headache since lunch");
    await user.click(screen.getByRole("button", { name: "Log" }));
    expect(JSON.parse(String(calls.filter((c) => c.url === "/api/v1/health/log").at(-1)!.init.body))).toEqual({ kind: "symptom", text: "Headache since lunch" });

    await user.click(screen.getByRole("tab", { name: "Data" }));
    window.confirm = () => true;
    const region = await screen.findByRole("region", { name: "Your health data" });
    await user.type(within(region).getByLabelText("From"), "2026-10-01");
    await user.type(within(region).getByLabelText("To"), "2026-10-31");
    await user.click(within(region).getByRole("button", { name: "Delete" }));
    expect(await within(region).findByText("Deleted 12 readings and 1 workouts.")).toBeInTheDocument();
    expect(calls.some((c) => c.url === "/api/v1/health/data?start=2026-10-01&end=2026-10-31" && c.init.method === "DELETE")).toBe(true);
  });

  it("Home's readiness card hides without a score", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/health/today": () => jsonResponse({ readiness: null }) });
    const { container } = render(<MemoryRouter><ReadinessWidget /></MemoryRouter>);
    await new Promise((r) => setTimeout(r, 30));
    expect(container).toBeEmptyDOMElement();
  });
});
