"""Genera assets/portrait.svg: retrato ASCII animado a partir de una foto.

Uso (local, una sola vez): python scripts/make_ascii_svg.py foto.png
Requiere Pillow y numpy. El fondo claro se quita con un relleno desde los bordes.
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

COLS, ROWS = 96, 58
RAMP = " .`:-=+*cs#%@"
OUT = Path(__file__).resolve().parent.parent / "assets" / "portrait.svg"


def load(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, 0, (w + s) // 2, s))
    # Máscara del fondo: relleno desde las esquinas superiores (pared lisa).
    work = im.filter(ImageFilter.GaussianBlur(3)).copy()
    for seed in [(2, 2), (s - 3, 2), (2, s // 2), (s - 3, s // 2)]:
        ImageDraw.floodfill(work, seed, (255, 0, 255), thresh=38)
    a = np.asarray(work)
    bg = (a[..., 0] == 255) & (a[..., 1] == 0) & (a[..., 2] == 255)
    gray = ImageOps.equalize(ImageOps.grayscale(im))
    gray = gray.filter(ImageFilter.UnsharpMask(4, 180, 2))
    gray = ImageEnhance.Contrast(gray).enhance(1.3)
    return np.asarray(gray, dtype=float) / 255.0, bg


def to_ascii(gray, bg):
    h, w = gray.shape
    cw, ch = w / COLS, h / ROWS
    rows = []
    for r in range(ROWS):
        line = []
        for c in range(COLS):
            y0, y1 = int(r * ch), int((r + 1) * ch)
            x0, x1 = int(c * cw), int((c + 1) * cw)
            if bg[y0:y1, x0:x1].mean() > 0.6:
                line.append(" ")
                continue
            v = gray[y0:y1, x0:x1].mean()
            line.append(RAMP[min(len(RAMP) - 1, int(v * len(RAMP)))])
        rows.append(line)
    # Quita caracteres casi aislados (ruido del fondo).
    for r in range(ROWS):
        for c in range(COLS):
            if rows[r][c] == " ":
                continue
            near = [rows[rr][cc] for rr in range(max(0, r - 2), min(ROWS, r + 3))
                    for cc in range(max(0, c - 3), min(COLS, c + 4)) if (rr, cc) != (r, c)]
            if sum(ch != " " for ch in near) < 3:
                rows[r][c] = " "
    return ["".join(line).rstrip() for line in rows]


def svg(rows):
    fs, lh, cw = 9.6, 11.0, 5.78
    W, H = int(COLS * cw + 40), int(ROWS * lh + 44)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Retrato ASCII de Victor Cabrera">',
        "<style>",
        "text{font-family:'Cascadia Code',Consolas,'SFMono-Regular',Menlo,monospace;font-size:%spx;fill:#93C5FD;white-space:pre}" % fs,
        ".r{opacity:0;animation:in .5s ease-out forwards}",
        "@keyframes in{from{opacity:0;transform:translateX(-14px)}to{opacity:1;transform:none}}",
        "@media (prefers-reduced-motion:reduce){.r{animation:none;opacity:1}}",
        "</style>",
        f'<rect width="{W}" height="{H}" rx="12" fill="#0B1220" stroke="#1E3A8A"/>',
    ]
    for i, row in enumerate(rows):
        if not row.strip():
            continue
        y = 26 + i * lh
        out.append(
            f'<text class="r" x="20" y="{y:.1f}" xml:space="preserve" textLength="{len(row) * cw:.1f}" lengthAdjust="spacingAndGlyphs" style="animation-delay:{i * 0.03:.2f}s">{escape(row)}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    g, bg = load(sys.argv[1])
    rows = to_ascii(g, bg)
    OUT.write_text(svg(rows), encoding="utf-8")
    print("\n".join(rows))
