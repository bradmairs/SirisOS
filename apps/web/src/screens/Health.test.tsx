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

  it("Home's readiness card hides without a score", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/health/today": () => jsonResponse({ readiness: null }) });
    const { container } = render(<MemoryRouter><ReadinessWidget /></MemoryRouter>);
    await new Promise((r) => setTimeout(r, 30));
    expect(container).toBeEmptyDOMElement();
  });
});
