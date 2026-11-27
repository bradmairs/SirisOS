"""Keep private things out of this public repo (11.15).

Run by CI on every pull request, and by hand before committing. It reads only the lines a change adds, and fails
when one has:

- **a LAN address** (192.168.x.x, 10.x.x.x, 172.16-31.x.x), unless the line says `privacy: ok` (an example address
  that has to be there);
- **an email address** other than example ones (example.com, example.org, *.test, noreply addresses);
- **a word or number on your private list**: PRIVACY_TERMS, comma-separated (names, a street, real amounts from your
  budget). It's a GitHub Actions secret, so the list itself is never in the repo. Matching ignores case; a number
  matches with or without thousands commas ("5929" also catches "5,929").

    python3 scripts/privacy_check.py                 # this branch against origin/main
    python3 scripts/privacy_check.py --staged        # what's staged, before a commit
    PRIVACY_TERMS="..." python3 scripts/privacy_check.py

Exit status 1 lists each line found, as file:line and what it matched (never the private term's value in full).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

LAN = re.compile(r"\b(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b")
EMAIL_OK = re.compile(r"(^|\.)(example\.(com|org|net)|[a-z0-9-]+\.test|localhost|users\.noreply\.github\.com|noreply\.[a-z.]+|anthropic\.com)$", re.I)
OK_MARK = "privacy: ok"
SKIP_FILES = re.compile(r"(^|/)(package-lock\.json|.*\.lock|.*\.svg|.*\.png|.*\.jpg|.*\.webp|.*\.pdf)$")


def added_lines(args: list[str]) -> list[tuple[str, int, str]]:
    """(file, line number, text) for each line the change adds."""
    diff_args = ["diff", "--cached", "-U0"] if "--staged" in args else ["diff", "-U0", f"{_base()}...HEAD"]
    out = subprocess.run(["git", *diff_args], capture_output=True, text=True, check=True).stdout
    found, file, line = [], "", 0
    for raw in out.splitlines():
        if raw.startswith("+++ "):
            file = raw[6:] if raw.startswith("+++ b/") else ""
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            line = int(m.group(1)) if m else 0
        elif raw.startswith("+") and not raw.startswith("+++"):
            if file and not SKIP_FILES.search(file):
                found.append((file, line, raw[1:]))
            line += 1
    return found


def _base() -> str:
    for ref in (os.getenv("PRIVACY_BASE", ""), "origin/main", "main"):
        if ref and subprocess.run(["git", "rev-parse", "--verify", "-q", ref], capture_output=True).returncode == 0:
            return ref
    return "HEAD~1"


def terms() -> list[tuple[str, re.Pattern[str]]]:
    out = []
    for t in (os.getenv("PRIVACY_TERMS") or "").split(","):
        t = t.strip()
        if len(t) < 3:
            continue
        if re.fullmatch(r"[\d.,]+", t):  # a number: with or without thousands commas
            digits = t.replace(",", "")
            whole, _, frac = digits.partition(".")
            grouped = f"{int(whole):,}" if whole.isdigit() else whole
            body = "|".join(re.escape(x + (f".{frac}" if frac else "")) for x in {whole, grouped})
            out.append((t, re.compile(rf"(?<![\d.,])(?:{body})(?![\d])")))
        else:
            out.append((t, re.compile(rf"(?<!\w){re.escape(t)}(?!\w)", re.I)))
    return out


def hide(term: str) -> str:
    return term[0] + "…" if len(term) > 1 else "…"


def check(lines: list[tuple[str, int, str]], private: list[tuple[str, re.Pattern[str]]]) -> list[str]:
    problems = []
    for file, n, text in lines:
        if OK_MARK in text:
            continue
        if LAN.search(text):
            problems.append(f"{file}:{n}: a LAN address ({LAN.search(text).group(0)}): use an example, or mark the line '{OK_MARK}'")  # type: ignore[union-attr]
        for m in EMAIL.finditer(text):
            if not EMAIL_OK.search(m.group(1)):
                problems.append(f"{file}:{n}: an email address ({m.group(0)[:3]}…@{m.group(1)})")
        for term, pattern in private:
            if pattern.search(text):
                problems.append(f"{file}:{n}: a word or number on your private list ({hide(term)})")
    return problems


def main(args: list[str]) -> int:
    problems = check(added_lines(args), terms())
    if problems:
        print("Private things in this change (the repo is public):")
        print("\n".join(f"  {p}" for p in problems))
        return 1
    print("No private things in the added lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
