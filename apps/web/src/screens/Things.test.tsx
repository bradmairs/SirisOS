import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import { PeopleCard, ThingsCard } from "./Things";

describe("Things & people (7.7)", () => {
  it("lists things with their warranty and adds one", async () => {
    signIn();
    clearResources();
    const calls = mockFetch({
      "/api/v1/life/things": (_url, init) => init.method === "POST" ? jsonResponse({ id: 9 }) : jsonResponse([
        { id: 1, name: "Dishwasher", brand: "Bosch", model: "", room: "Kitchen", bought: "2025-01-10", price: 1099, shop: "", warranty_until: "2026-11-20",
          manual: "https://bosch.example/manual", notes: "", document_id: null, warranty_days_left: 13, under_warranty: true },
      ]),
    });
    const user = userEvent.setup();
    render(<ThingsCard />);
    const card = await screen.findByRole("region", { name: "Things you own" });
    expect(await within(card).findByText("⚠ Warranty ends in 13 days")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Manual" })).toHaveAttribute("href", "https://bosch.example/manual");
    await user.click(within(card).getByRole("button", { name: "Add" }));
    await user.type(within(card).getByLabelText("What"), "TV");
    await user.type(within(card).getByLabelText("Warranty in months"), "24");
    await user.click(within(card).getByRole("button", { name: "Save" }));
    const post = calls.find((c) => c.init.method === "POST");
    expect(JSON.parse(String(post!.init.body))).toMatchObject({ name: "TV", warranty_months: 24 });
  });

  it("shows birthdays and gift ideas", async () => {
    signIn();
    clearResources();
    mockFetch({
      "/api/v1/life/people/2/gifts": () => jsonResponse({ ideas: ["Sam loves pour-over coffee"], last_seen: { text: "6 days ago (2026-11-01): lunch." } }),
      "/api/v1/life/people": () => jsonResponse([{ id: 2, name: "Sam", relation: "friend", birthday: "1990-11-12", anniversary: null, notes: "",
        last_contact: null, keep_in_touch_days: null, days_to_birthday: 5, turning: 36 }]),
    });
    const user = userEvent.setup();
    render(<PeopleCard />);
    const card = await screen.findByRole("region", { name: "People" });
    expect(await within(card).findByText("birthday in 5 days (turning 36)")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Gift ideas and catch-ups for Sam" }));
    expect(await within(card).findByText(/pour-over coffee/)).toBeInTheDocument();
  });
});
