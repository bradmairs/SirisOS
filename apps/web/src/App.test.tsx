import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";
import { jsonResponse, mockFetch, signIn } from "./test/helpers";

describe("<App />", () => {
  it("signs in and lands on the home screen", async () => {
    const calls = mockFetch({
      "/api/v1/auth/login": () => jsonResponse({ access_token: "jwt-1", token_type: "bearer", expires_in: 3600, username: "brad" }),
      "/api/v1/hub/apps": () => jsonResponse({ apps: [] }),
    });
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByPlaceholderText("Username"), "brad");
    await user.type(screen.getByPlaceholderText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(localStorage.getItem("sirisos.token")).toBe("jwt-1");
    expect(JSON.parse(calls[0].init.body as string)).toEqual({ username: "brad", password: "secret" });
  });

  it("shows a rejected sign-in", async () => {
    mockFetch({ "/api/v1/auth/login": () => jsonResponse({ detail: "Incorrect username or password." }, 401) });
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByPlaceholderText("Username"), "brad");
    await user.type(screen.getByPlaceholderText("Password"), "nope");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect username or password.");
  });

  it("returns to sign-in when the session expires", async () => {
    signIn();
    mockFetch({ "/api/v1/hub/apps": () => jsonResponse({ detail: "Invalid or expired session." }, 401) });
    render(<App />);
    expect(await screen.findByRole("form", { name: "Sign in" })).toBeInTheDocument();
    expect(localStorage.getItem("sirisos.token")).toBeNull();
  });
});
