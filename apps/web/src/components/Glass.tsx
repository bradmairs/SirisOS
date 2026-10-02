import { forwardRef, type ElementType, type HTMLAttributes, type ReactNode } from "react";

type Variant = "regular" | "strong" | "clear" | "tint";
type Shape = "lg" | "xl" | "md" | "pill";

export interface GlassProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType;
  variant?: Variant;
  shape?: Shape;
  interactive?: boolean;
  children?: ReactNode;
  // Pass-through for the element chosen with `as` (href, type, htmlFor, disabled…).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

/** A Liquid Glass surface. Everything translucent in SirisOS is one of these. */
export const Glass = forwardRef<HTMLElement, GlassProps>(function Glass(
  { as: Tag = "div", variant = "regular", shape = "lg", interactive = false, className = "", children, ...rest },
  ref,
) {
  const classes = [
    "glass",
    variant !== "regular" && `glass--${variant}`,
    shape !== "lg" && `glass--${shape}`,
    interactive && "glass--interactive",
    className,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <Tag ref={ref} className={classes} {...rest}>
      {children}
    </Tag>
  );
});
