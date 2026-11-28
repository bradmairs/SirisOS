import { afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { TrailsHomeCard } from "./TrailsHome";

describe("SirisTrails on Home (12.6)", () => {
  afterEach(() => clearResources());

  it("shows the last walk, how often you've done it and the year so far", async () => {
    signIn();
    const start = new Date(Date.now() - 2 * 86_400_000).toISOString();
    mockFetch({
      "/api/v1/trails/home": () => jsonResponse({
        latest: { id: "w_000000000001", name: "Creek loop", kind: "walk", start, tz: null, km: 6.6, minutes: 70, ascent_m: 64, place: null,
          weather: { temp_c: 18.4, icon: "⛅" }, times: 12, best: false },
        year: { year: 2026, walks: 57, km: 371.2, hours: 80, ascent_m: 4210 }, last_30_days: { walks: 6, km: 40 }, wishlist: { open: 2, done: 1 } }),
    });
    render(<MemoryRouter><TrailsHomeCard /></MemoryRouter>);
    expect(await screen.findByText("Creek loop")).toBeTruthy();
    expect(screen.getByText(/6.6 km · 1h 10m · ⛅ 18° · walked 12 times/)).toBeTruthy();
    expect(screen.getByText(/2026: 57 walks · 371.2 km · 4,210 m climbed · 2 on your wishlist/)).toBeTruthy();
  });
});
