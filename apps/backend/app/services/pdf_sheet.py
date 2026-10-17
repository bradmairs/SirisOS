"""A one-page A4 PDF built by hand: text in the PDF's own Helvetica fonts
(no font files, no extra libraries) plus thin rules. Enough for a clean
calculation sheet; text is Windows-1252, so °, ³, – and the like print, and
anything outside it becomes "?".
"""

from __future__ import annotations

from dataclasses import dataclass, field

PAGE_W, PAGE_H = 595.0, 842.0  # A4 in points
MARGIN = 56.0
# Average Helvetica glyph width as a share of the font size: generous, so
# wrapping errs towards shorter lines rather than overflowing the margin.
AVG_WIDTH = 0.53


def _escape(text: str) -> bytes:
    raw = text.encode("cp1252", errors="replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def wrap(text: str, size: float, width: float) -> list[str]:
    limit = max(10, int(width / (size * AVG_WIDTH)))
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words, line = paragraph.split(), ""
        for word in words:
            if line and len(line) + 1 + len(word) > limit:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}" if line else word
        lines.append(line)
    return lines


@dataclass
class Sheet:
    """Lays out top to bottom; `y` is the next baseline."""

    y: float = PAGE_H - MARGIN
    ops: list[bytes] = field(default_factory=list)

    def text(self, value: str, size: float = 10.5, bold: bool = False, x: float = MARGIN, grey: bool = False, advance: bool = True) -> None:
        font = b"/F2" if bold else b"/F1"
        colour = b"0.42 0.45 0.5 rg" if grey else b"0.08 0.1 0.13 rg"
        self.ops.append(colour + b" BT " + font + b" %.1f Tf %.2f %.2f Td (" % (size, x, self.y) + _escape(value) + b") Tj ET")
        if advance:
            self.y -= size * 1.45

    def paragraph(self, value: str, size: float = 10.5, grey: bool = False) -> None:
        for line in wrap(value, size, PAGE_W - 2 * MARGIN):
            self.text(line, size, grey=grey)

    def row(self, left: str, right: str, size: float = 10.5, bold_right: bool = False) -> None:
        """A two-column line: label on the left, value from the middle."""
        col = MARGIN + (PAGE_W - 2 * MARGIN) * 0.55
        label_lines = wrap(left, size, col - MARGIN - 8)
        self.text(right, size, bold=bold_right, x=col, advance=False)
        for line in label_lines:
            self.text(line, size)

    def rule(self, at: float | None = None) -> None:
        y = self.y + 4 if at is None else at
        self.ops.append(b"0.82 0.85 0.88 RG 0.6 w %.2f %.2f m %.2f %.2f l S" % (MARGIN, y, PAGE_W - MARGIN, y))

    def space(self, points: float) -> None:
        self.y -= points

    def heading(self, value: str) -> None:
        """A small grey caps label with a rule just under it."""
        self.y -= 8
        baseline = self.y
        self.text(value.upper(), 8.5, bold=True, grey=True)
        self.rule(at=baseline - 4)
        self.y -= 4

    def footer(self, lines: list[str]) -> None:
        y = MARGIN
        for line in reversed(lines):
            self.ops.append(b"0.42 0.45 0.5 rg BT /F1 8 Tf %.2f %.2f Td (" % (MARGIN, y) + _escape(line) + b") Tj ET")
            y += 11

    def pdf(self, title: str = "") -> bytes:
        content = b"\n".join(self.ops)
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>" % (PAGE_W, PAGE_H),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
            b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
            # Document info strings aren't WinAnsi: UTF-16 with a byte-order mark.
            b"<< /Title <" + ("\ufeff" + title).encode("utf-16-be").hex().upper().encode() + b"> /Producer (SirisOS) >>",
        ]
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for number, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
        out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
        out += b"trailer\n<< /Size %d /Root 1 0 R /Info 7 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
        return bytes(out)
