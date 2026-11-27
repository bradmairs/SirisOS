import { afterEach, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { ApplePayCard } from "./ApplePayCard";

afterEach(() => clearResources());

describe("<ApplePayCard />", () => {
  it("makes the Shortcut's key once, and says how the month's taps are going", async () => {
    signIn();
    let on = false;
    mockFetch({ "/api/v1/budget/tap-key": (_u, init) => {
      if (init?.method === "POST") { on = true; return jsonResponse({ key: "pay_test", url: "/api/v1/budget-tap" }); }
      return jsonResponse({ on, made: null, last: on ? "2026-11-27T09:12" : null, count: on ? 3 : 0, taps: on ? 3 : 0, unsorted: on ? 1 : 0, spent: on ? 87.4 : 0 });
    } });
    const user = userEvent.setup();
    render(<ApplePayCard />);
    const card = await screen.findByRole("region", { name: "Apple Pay to the budget" });
    expect(within(card).getByText(/api\/v1\/budget-tap/)).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Make a key" }));
    expect(await within(card).findByLabelText("Apple Pay key")).toHaveTextContent("pay_test");
    expect(await within(card).findByText(/This month: 3 taps, \$87, 1 to sort/)).toBeInTheDocument();
  });
});
