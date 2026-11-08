import { afterEach, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { categoryOf, LatestThenGrouped } from "../components/Grouped";

afterEach(() => window.localStorage.clear());

type Item = { id: number; name: string; shop: string; bought: string };
const items: Item[] = [
  { id: 1, name: "MacBook", shop: "JB Hi-Fi", bought: "2024-01-01" },
  { id: 2, name: "Drill", shop: "Bunnings", bought: "2026-01-01" },
  { id: 3, name: "Shirt", shop: "Tarocash", bought: "2025-06-01" },
  { id: 4, name: "Dishwasher", shop: "Harvey Norman", bought: "2026-03-01" },
  { id: 5, name: "Sofa", shop: "Freedom", bought: "2025-01-01" },
  { id: 6, name: "Thing nobody knows", shop: "Somewhere", bought: "2026-05-01" },
  { id: 7, name: "UniFi Switch Lite 8 PoE", shop: "Scorptec", bought: "2023-01-01" },
];

describe("The latest five, then every one by category (8.22)", () => {
  it("sorts purchases into categories", () => {
    expect(categoryOf("UniFi Switch Lite 8 PoE", "Scorptec")).toBe("Computers and electronics");
    expect(categoryOf("Bunnings Online Order Invoice", "Bunnings")).toBe("Tools and garden");
    expect(categoryOf("Shell Unleaded 91 Fuel", "OTR")).toBe("Car and fuel");
    expect(categoryOf("Vibe Hotel: Accommodation")).toBe("Travel and stays");
    expect(categoryOf("Dishwasher", "Harvey Norman")).toBe("Appliances");
    expect(categoryOf("A mystery")).toBe("Other");
  });

  it("shows the newest five, then all of them grouped with Other last", async () => {
    render(<LatestThenGrouped items={items} label="things" newest={(a, b) => b.bought.localeCompare(a.bought)} category={(i) => categoryOf(i.name, i.shop)}
      render={(i) => <li key={i.id}>{i.name}</li>} />);
    const latest = screen.getByRole("list", { name: "Latest things" });
    expect(within(latest).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["Thing nobody knows", "Dishwasher", "Drill", "Shirt", "Sofa"]);
    await userEvent.click(screen.getByRole("button", { name: "Show all 7, by category" }));
    const heads = screen.getAllByRole("heading").map((h) => h.textContent?.replace(/\d+$/, "").trim());
    expect(heads[heads.length - 1]).toBe("Other");
    expect(within(screen.getByRole("list", { name: "things: Computers and electronics" })).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["MacBook", "UniFi Switch Lite 8 PoE"]);
    await userEvent.click(screen.getByRole("button", { name: "Just the latest 5" }));
    expect(screen.getByRole("list", { name: "Latest things" })).toBeInTheDocument();
  });
});
