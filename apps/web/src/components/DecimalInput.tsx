import { useEffect, useState, type InputHTMLAttributes } from "react";

/** A number box you can type a decimal into (7.8). Bound straight to a number, "62." became 62 as you typed it, so
 * 62.5 came out as 625. This keeps what you've typed while you type, and hands back the number (a comma works as the point). */
export function DecimalInput({ value, onValue, ...rest }: { value: number | null | undefined; onValue: (v: number | null) => void }
  & Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  const [text, setText] = useState(value == null ? "" : String(value));
  useEffect(() => {
    // Someone else changed it (a weight carried down, a swap): show theirs, unless it's what we're typing.
    setText((t) => (parse(t) === (value ?? null) ? t : value == null ? "" : String(value)));
  }, [value]);
  return (
    <input inputMode="decimal" {...rest} value={text}
      onChange={(e) => {
        const t = e.target.value.replace(",", ".");
        if (t !== "" && !/^\d*\.?\d*$/.test(t)) return;
        setText(t);
        const v = parse(t);
        if (v !== (value ?? null)) onValue(v);
      }} />
  );
}

function parse(t: string): number | null {
  if (t === "" || t === ".") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}
