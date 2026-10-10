import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LOGO_STYLE, Logo, LogoMark } from "./Logo";

describe("LogoMark", () => {
  it("draws the lightning S by default and keeps the classic S", () => {
    expect(LOGO_STYLE).toBe("bolt");
    render(<Logo size={38} />);
    expect(screen.getByRole("img", { name: "SirisOS" })).toHaveAttribute("data-logo", "bolt");
  });

  it("can still draw the classic S", () => {
    const { container } = render(<LogoMark variant="classic" title="Classic" />);
    expect(screen.getByRole("img", { name: "Classic" })).toHaveAttribute("data-logo", "classic");
    expect(container.querySelector('path[d^="M 39.5 22.5 A 7.5"]')).not.toBeNull();
  });
});
