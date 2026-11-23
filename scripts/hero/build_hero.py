"""Genera assets/hero-dark.svg y assets/hero-light.svg: terminal con retrato de puntos.

Uso:
  python scripts/hero/build_hero.py prep <foto_recortada.png>   # una vez: crea portrait.npz
  python scripts/hero/build_hero.py build                       # genera los SVG

`prep` espera una foto con el fondo ya quitado (PNG con transparencia; yo usé rembg con
el modelo u2net_human_seg). Guarda el retrato procesado en portrait.npz, que es la fuente
de verdad: `build` solo necesita ese archivo, Pillow, NumPy y SciPy.

Cómo funciona el retrato:
  - Recorte de cabeza y hombros, grilla de 300x340, autocontrast(1) + contraste 1.3x +
    UnsharpMask(3, 140) y dithering Floyd-Steinberg de 1 bit en orden serpentina.
  - Los puntos se dibujan como corridas horizontales en <path> con crispEdges (sin fuentes).
  - Intro (~3.2 s): 60 grupos aleatorios repartidos por todo el retrato aparecen a la vez.
  - Bucle: el retrato se disuelve en ~94 bandas orgánicas (k-means sobre posiciones con
    ruido, para evitar el efecto de grilla) y ~900 puntos viajeros forman "</>" y un
    teléfono, emparejados con asignación óptima para que cada uno haga el camino más corto.
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from scipy.cluster.vq import kmeans2
from scipy.optimize import linear_sum_assignment

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
NPZ = HERE / "portrait.npz"
GW, GH = 300, 340
RNG = np.random.default_rng(7)

# ---------------------------------------------------------------- datos del panel
TITLE = "vecs0@github: ~ % ./perfil.sh --live"
PILL = "@vecs0 · Full Stack & Mobile"
ROWS = [
    ("Nombre", "Victor Cabrera"),
    ("Rol", "Full Stack & Mobile Developer"),
    ("Origen", "Paraguay"),
    ("Estudios", "Ingeniería en Informática"),
    ("Estado", "Construyendo · Aprendiendo · Publicando"),
    ("Herramientas", "VS Code, Git, Expo, Supabase"),
    None,
    ("Core.Lenguajes", "Python, TypeScript, C#, JavaScript"),
    ("Core.Frontend", "React, Next.js, Tailwind CSS"),
    ("Core.Mobile", "React Native, Expo, SQLite"),
    ("Core.Backend", "FastAPI, Flask, ASP.NET"),
    ("Core.Datos", "PostgreSQL, Supabase, SQLite"),
    ("Core.Infra", "Vercel, Render, Cloudflare"),
    "- Portafolio",
    ("Red.GitHub", "@vecs0"),
    ("Red.Demo", "sistema-academico-alpha.vercel.app"),
    ("Red.Proyectos", "6 propios + 1 en equipo"),
]

THEMES = {
    "dark": dict(bg="#070B16", panel="#0A101F", bar="#0B1222", sep="rgba(255,255,255,0.10)",
                 dots="#60A5FA", chrome="#2DD4BF", label="#475569", key="#2DD4BF",
                 val="#F1F5F9", lead="#334155", muted="#94A3B8", pill_bg="#134E4A", pill_fg="#CCFBF1",
                 frame="#2DD4BF", travel="#93C5FD"),
    "light": dict(bg="#FFFFFF", panel="#F8FAFC", bar="#EEF2F7", sep="rgba(15,23,42,0.10)",
                  dots="#1D4ED8", chrome="#0F766E", label="#94A3B8", key="#0F766E",
                  val="#0F172A", lead="#CBD5E1", muted="#475569", pill_bg="#CCFBF1", pill_fg="#134E4A",
                  frame="#0F766E", travel="#2563EB"),
}

W, H = 1180, 620
PX, PY, SC = 44, 96, 1.42          # origen y escala del retrato dentro del marco
LOOP = [("portrait", 3.0), ("t", 1.3), ("code", 2.0), ("t", 1.3), ("phone", 2.0), ("t", 1.3)]
INTRO = 3.2


# ---------------------------------------------------------------- preparación
def prep(path):
    im = Image.open(path).convert("RGBA")
    l, t, r, b = im.getbbox()
    # Cabeza y hombros: ancho del sujeto completo, alto proporcional a la grilla.
    w = r - l
    cx = (l + r) / 2
    side = max(w, int((b - t) * GW / GH * 0.62))
    x0 = int(max(0, cx - side / 2 - side * 0.05))
    y0 = max(0, t - int(side * 0.06))
    h = int(side * GH / GW)
    im = im.crop((x0, y0, x0 + side, y0 + h)).resize((GW, GH), Image.LANCZOS)
    alpha = np.asarray(im.split()[3], dtype=float) / 255
    g = ImageOps.grayscale(im.convert("RGB"))
    g = ImageOps.autocontrast(g, cutoff=1)
    g = ImageEnhance.Contrast(g).enhance(1.3)
    g = g.filter(ImageFilter.UnsharpMask(radius=3, percent=140))
    gray = np.asarray(g, dtype=float) / 255
    np.savez_compressed(NPZ, gray=gray, alpha=alpha)
    print("ok:", NPZ)


def dither(v, mask):
    """Floyd-Steinberg de 1 bit en serpentina; borra el sangrado fuera de la máscara."""
    a = v.copy()
    out = np.zeros_like(a, dtype=bool)
    h, w = a.shape
    for y in range(h):
        rng = range(w) if y % 2 == 0 else range(w - 1, -1, -1)
        d = 1 if y % 2 == 0 else -1
        for x in rng:
            if not mask[y, x]:
                a[y, x] = 0
                continue
            old = a[y, x]
            new = 1.0 if old >= 0.5 else 0.0
            out[y, x] = new > 0
            e = old - new
            if 0 <= x + d < w:
                a[y, x + d] += e * 7 / 16
            if y + 1 < h:
                if 0 <= x - d < w:
                    a[y + 1, x - d] += e * 3 / 16
                a[y + 1, x] += e * 5 / 16
                if 0 <= x + d < w:
                    a[y + 1, x + d] += e * 1 / 16
    return out


def shape_points(kind, n):
    im = Image.new("L", (GW, GH), 0)
    d = ImageDraw.Draw(im)
    if kind == "code":
        # "</>" con trazos rectos: dos chevrones y una barra.
        d.line([(110, 110), (40, 170), (110, 230)], fill=255, width=16, joint="curve")
        d.line([(190, 110), (260, 170), (190, 230)], fill=255, width=16, joint="curve")
        d.line([(172, 92), (128, 248)], fill=255, width=16)
    else:
        d.rounded_rectangle([88, 40, 212, 300], 22, outline=255, width=12)
        d.rounded_rectangle([128, 58, 172, 66], 4, fill=255)
        d.rounded_rectangle([108, 88, 192, 128], 8, fill=255)
        for y in (146, 176, 206):
            d.rounded_rectangle([108, y, 192, y + 18], 6, outline=255, width=5)
        d.ellipse([140, 262, 160, 282], fill=255)
    ys, xs = np.nonzero(np.asarray(im) > 0)
    idx = RNG.choice(len(xs), n, replace=len(xs) < n)
    return np.stack([xs[idx], ys[idx]], 1).astype(float) + RNG.uniform(-0.4, 0.4, (n, 2))


# ---------------------------------------------------------------- SVG helpers
def runs_path(points):
    """Puntos enteros -> path de corridas horizontales."""
    if len(points) == 0:
        return ""
    pts = sorted(map(tuple, points), key=lambda p: (p[1], p[0]))
    parts, i = [], 0
    while i < len(pts):
        x, y = pts[i]
        n = 1
        while i + n < len(pts) and pts[i + n] == (x + n, y):
            n += 1
        parts.append(f"M{x} {y}h{n}v1h-{n}z")
        i += n
    return "".join(parts)


def times():
    total = sum(d for _, d in LOOP)
    acc, marks = 0.0, [0.0]
    for _, d in LOOP:
        acc += d
        marks.append(acc / total)
    return total, marks   # marks: inicio de cada fase y 1.0


def kt(vals):
    return ";".join(f"{v:.4f}" for v in vals)


def build_theme(name, gray, alpha):
    t = THEMES[name]
    mask = alpha > 0.5
    # En oscuro, un poco de gamma para que los tonos medios no saturen de puntos.
    tone = gray ** 1.35 if name == "dark" else 1 - gray
    dots = dither(tone, mask)
    ys, xs = np.nonzero(dots)
    pts = np.stack([xs, ys], 1)
    total, m = times()
    # m = [0, p_end, t1_end, code_end, t2_end, phone_end, 1]

    # ----- intro: 60 grupos aleatorios dispersos
    gid = RNG.integers(0, 60, len(pts))
    starts = RNG.uniform(0.0, 2.0, 60)
    intro = [f'<g fill="{t["dots"]}"><set attributeName="opacity" to="0" begin="{INTRO}s" fill="freeze"/>']
    for g in range(60):
        sel = pts[gid == g]
        intro.append(
            f'<path d="{runs_path(sel)}" opacity="0"><animate attributeName="opacity" values="0;1" '
            f'begin="{starts[g]:.2f}s" dur="0.9s" fill="freeze"/></path>')
    intro.append("</g>")

    # ----- bucle: bandas que se disuelven hacia el centro del primer logo
    code = shape_points("code", 900)
    phone = shape_points("phone", 900)
    target = code.mean(0)
    noisy = pts + RNG.normal(0, 4, pts.shape)
    cent, lab = kmeans2(noisy.astype(float), 94, seed=3, minit="++")
    band = [f'<g fill="{t["dots"]}" opacity="0"><set attributeName="opacity" to="1" begin="{INTRO}s" fill="freeze"/>']
    ktimes = kt([0, m[1], m[2], m[5], 1])
    for k in range(94):
        sel = pts[lab == k]
        if len(sel) == 0:
            continue
        dx, dy = 0.42 * (target - cent[k])
        band.append(
            f'<g><path d="{runs_path(sel)}"/>'
            f'<animateTransform attributeName="transform" type="translate" begin="{INTRO}s" dur="{total}s" repeatCount="indefinite" '
            f'keyTimes="{ktimes}" values="0 0;0 0;{dx:.1f} {dy:.1f};{dx:.1f} {dy:.1f};0 0"/>'
            f'<animate attributeName="opacity" begin="{INTRO}s" dur="{total}s" repeatCount="indefinite" '
            f'keyTimes="{ktimes}" values="1;1;0;0;1"/></g>')
    band.append("</g>")

    # ----- viajeros: retrato -> </> -> teléfono -> retrato, por asignación óptima
    src = pts[RNG.choice(len(pts), 900, replace=False)].astype(float)
    _, c1 = linear_sum_assignment(((src[:, None] - code[None]) ** 2).sum(-1))
    code = code[c1]
    _, c2 = linear_sum_assignment(((code[:, None] - phone[None]) ** 2).sum(-1))
    phone = phone[c2]
    keys = [0, m[1], m[2], m[3], m[4], m[5], 1]
    trav = [f'<g fill="{t["travel"]}" opacity="0"><set attributeName="opacity" to="1" begin="{INTRO}s" fill="freeze"/>']
    for i in range(900):
        a, b, c = src[i], code[i], phone[i]
        vals = [a, a, b, b, c, c, a]
        tv = ";".join(f"{p[0]:.1f} {p[1]:.1f}" for p in vals)
        trav.append(
            f'<rect width="1.6" height="1.6" opacity="0">'
            f'<animateTransform attributeName="transform" type="translate" begin="{INTRO}s" dur="{total}s" repeatCount="indefinite" keyTimes="{kt(keys)}" values="{tv}"/>'
            f'<animate attributeName="opacity" begin="{INTRO}s" dur="{total}s" repeatCount="indefinite" keyTimes="{kt(keys)}" values="0;0;1;1;1;1;0"/></rect>')
    trav.append("</g>")

    # ----- panel de información
    fx, fy, fw, fh = PX - 12, PY - 14, int(GW * SC) + 24, int(GH * SC) + 26
    ix = fx + fw + 44
    iw = W - ix - 44
    cw = 8.4  # ancho de carácter a 14px; las filas se fijan con textLength
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,\'Liberation Mono\',monospace" role="img" '
        f'aria-label="Victor Cabrera, Full Stack y Mobile Developer: perfil.sh --live">',
        "<style>.r{opacity:0;animation:in .5s ease-out forwards}"
        "@keyframes in{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:none}}"
        ".live{animation:pulse 1.6s ease-in-out infinite}@keyframes pulse{50%{opacity:.25}}"
        ".cur{animation:blink 1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
        "@media (prefers-reduced-motion:reduce){.r{animation:none;opacity:1}.live,.cur{animation:none}}</style>",
        f'<defs><clipPath id="win"><rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="18"/></clipPath>'
        f'<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3"/></filter></defs>',
        f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="18" fill="{t["bg"]}"/>',
        '<g clip-path="url(#win)">',
        f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" fill="{t["panel"]}"/>',
        f'<rect x="2" y="2" width="{W - 4}" height="46" fill="{t["bar"]}"/>',
        f'<line x1="2" y1="48" x2="{W - 2}" y2="48" stroke="{t["sep"]}"/>',
        '<circle cx="30" cy="25" r="5.5" fill="#ff5f56"/><circle cx="50" cy="25" r="5.5" fill="#ffbd2e"/><circle cx="70" cy="25" r="5.5" fill="#27c93f"/>',
        f'<text x="{W / 2}" y="29" text-anchor="middle" font-size="12" fill="{t["muted"]}">{escape(TITLE)}</text>',
        f'<text x="{fx + 2}" y="{fy - 10}" font-size="10" letter-spacing="3" fill="{t["label"]}">MAPA.VISUAL</text>',
        f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="10" fill="none" stroke="{t["frame"]}" stroke-width="2" opacity=".4" filter="url(#glow)"/>',
        f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="10" fill="{t["panel"]}" stroke="{t["frame"]}" stroke-opacity=".35"/>',
        f'<g transform="translate({PX},{PY}) scale({SC})" shape-rendering="crispEdges">',
        *intro, *band, *trav,
        "</g>",
    ]
    # Encabezado del panel
    y = 92
    out.append(f'<g class="r" style="animation-delay:.2s"><text x="{ix}" y="{y}" font-size="13" font-weight="700" letter-spacing="2" fill="{t["chrome"]}">SISTEMA.INFO</text>'
               f'<g class="live"><circle cx="{ix + iw - 44}" cy="{y - 4}" r="4" fill="#EF4444"/>'
               f'<text x="{ix + iw}" y="{y}" font-size="12" text-anchor="end" fill="#EF4444">LIVE</text></g>'
               f'<line x1="{ix + 128}" y1="{y - 4}" x2="{ix + iw - 58}" y2="{y - 4}" stroke="{t["lead"]}" stroke-dasharray="2 4"/></g>')
    y += 30
    pw = len(PILL) * cw + 24
    out.append(f'<g class="r" style="animation-delay:.35s"><rect x="{ix}" y="{y - 17}" width="{pw:.0f}" height="24" rx="5" fill="{t["pill_bg"]}"/>'
               f'<text x="{ix + 12}" y="{y}" font-size="14" font-weight="700" fill="{t["pill_fg"]}">{escape(PILL)}</text></g>')
    y += 34
    delay = 0.5
    for row in ROWS:
        if row is None:
            y += 10
            continue
        if isinstance(row, str):
            out.append(f'<g class="r" style="animation-delay:{delay:.2f}s"><text x="{ix}" y="{y}" font-size="13" fill="{t["muted"]}">{escape(row)}</text>'
                       f'<line x1="{ix + len(row) * 7.8 + 12}" y1="{y - 4}" x2="{ix + iw}" y2="{y - 4}" stroke="{t["lead"]}" stroke-dasharray="2 4"/></g>')
            y += 23
            delay += 0.08
            continue
        k, v = row
        kw, vw = len(k) * cw, len(v) * cw
        lead_x0, lead_x1 = ix + kw + 10, ix + iw - vw - 10
        out.append(
            f'<g class="r" style="animation-delay:{delay:.2f}s">'
            f'<text x="{ix}" y="{y}" font-size="14" fill="{t["key"]}" textLength="{kw:.1f}" lengthAdjust="spacingAndGlyphs">{escape(k)}</text>'
            f'<line x1="{lead_x0:.1f}" y1="{y - 4}" x2="{lead_x1:.1f}" y2="{y - 4}" stroke="{t["lead"]}" stroke-dasharray="1.5 4.5" stroke-linecap="round"/>'
            f'<text x="{ix + iw}" y="{y}" font-size="14" font-weight="700" text-anchor="end" fill="{t["val"]}" textLength="{vw:.1f}" lengthAdjust="spacingAndGlyphs">{escape(v)}</text></g>')
        y += 23
        delay += 0.08
    y += 14
    foot = "▸ Proyectos destacados más abajo ↓"
    out.append(f'<g class="r" style="animation-delay:{delay + .1:.2f}s"><text x="{ix}" y="{y}" font-size="13" fill="{t["muted"]}">{escape(foot)}</text>'
               f'<rect class="cur" x="{ix + len(foot) * 7.8 + 8:.0f}" y="{y - 12}" width="8" height="15" fill="{t["chrome"]}"/></g>')
    out.append("</g>")
    out.append(f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="18" fill="none" stroke="{t["frame"]}" stroke-opacity=".45"/>')
    out.append("</svg>")
    return "\n".join(out)


def build():
    data = np.load(NPZ)
    for name in THEMES:
        svg = build_theme(name, data["gray"], data["alpha"])
        p = ROOT / "assets" / f"hero-{name}.svg"
        p.write_text(svg, encoding="utf-8")
        print(f"{p.name}: {len(svg.encode()) / 1024:.0f} KB")


if __name__ == "__main__":
    if sys.argv[1:2] == ["prep"]:
        prep(sys.argv[2])
    else:
        build()
