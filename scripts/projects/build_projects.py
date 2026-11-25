"""Genera las tarjetas animadas de proyectos y la del proyecto destacado.

Uso: python scripts/projects/build_projects.py [--fetch]
  --fetch  actualiza los lenguajes desde la API de GitHub (usa GITHUB_TOKEN si existe)
           y los guarda en languages.json; sin la opción usa ese archivo.

Salida: assets/cards/<proyecto>-{dark,light}.svg y assets/featured-{dark,light}.svg.
GitHub no permite enlaces dentro de un SVG: por eso hay una imagen por proyecto.
Las miniaturas se incrustan como WebP en base64 (GitHub no deja que un SVG cargue
imágenes externas). Requiere Pillow.
"""
import base64
import io
import json
import os
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LANGS = HERE / "languages.json"

PROJECTS = [
    dict(repo="vecs0/sistema-academico-personal", name="Sistema Académico", kind="WEB + MOBILE",
         desc="Gestión académica para la UCA de Caacupé: portales de alumno, profesor y admin, asistencia por QR y boletas en PDF.",
         tags=["FastAPI", "React", "Expo"], metric="399 tests", thumb="sistema-academico.webp"),
    dict(repo="vecs0/mifinanzaspy", name="MiFinanzasPY", kind="MOBILE",
         desc="Finanzas personales en guaraníes. Offline-first, carga por texto o voz y 21 bancos paraguayos.",
         tags=["React Native", "Expo", "SQLite"], metric="428 tests", thumb="mifinanzaspy.webp"),
    dict(repo="vecs0/Inmobiliaria_py", name="InmobiliariaPY", kind="WEB",
         desc="Portal inmobiliario con paneles por rol, mapa, pagos con Stripe y búsqueda semántica con IA.",
         tags=["Next.js", "Supabase", "Stripe"], metric="API pública v1", thumb="inmobiliaria-py.webp"),
    dict(repo="vecs0/DesafioSaber", name="DesafíoSaber", kind="DESKTOP + WEB",
         desc="Trivia de escritorio con 760 preguntas y panel web sincronizado en tiempo real.",
         tags=["Python", "Flask", "Socket.IO"], metric="40 tests", thumb="desafio-saber.webp"),
    dict(repo="vecs0/manduara.dev", name="MANDU'ARÃ", kind="WEB",
         desc="Juego educativo de Historia para secundaria, del mundo clásico al Paraguay actual.",
         tags=["JavaScript", "Bootstrap"], metric="119 preguntas", thumb="manduara.webp"),
    dict(repo="vecs0/Gestion_calificaciones", name="Calificaciones", kind="WEB",
         desc="Notas por materia con promedios automáticos, auditoría de cambios y exportación a Excel.",
         tags=["C#", "ASP.NET"], metric="Excel y CSV", thumb="calificaciones.webp"),
]

FEATURED = dict(
    repo="dual-devs0/sistema-academico", name="Sistema Académico UCA",
    desc=["Sistema de gestión académica desarrollado para la Universidad",
          "Católica, Unidad Pedagógica de Caacupé. Backend, web y app móvil",
          "para tres roles: alumno, profesor y administrador."],
    kpis=[("399", "tests backend"), ("3", "roles"), ("2", "clientes: web + app"), ("CI", "GitHub Actions")],
    stack=["FastAPI", "PostgreSQL", "React 19", "TypeScript", "Expo", "Vercel", "Render"],
    shots=["alumno-dashboard.webp", "profesor-calificaciones.webp", "admin-dashboard.webp", "alumno-escanear-qr.webp"],
    captions=["Dashboard del alumno", "Calificaciones del profesor", "Panel de administración", "Asistencia por QR"],
)

COLORS = {"TypeScript": "#3178C6", "Python": "#3572A5", "JavaScript": "#F1E05A", "CSS": "#663399",
          "HTML": "#E34C26", "Kotlin": "#A97BFF", "PLpgSQL": "#336790", "C#": "#178600",
          "ASP.NET": "#9400FF", "Shell": "#89E051", "Batchfile": "#C1F12E"}

THEMES = {
    "dark": dict(bg="#0A101F", card="#0D1528", cardb="rgba(45,212,191,0.22)", head="#0B1222",
                 title="#F1F5F9", text="#94A3B8", muted="#64748B", accent="#2DD4BF", blue="#60A5FA",
                 chip="#13203B", chipt="#93C5FD", bar="#1E293B", star="#FBBF24", glow="#2DD4BF"),
    "light": dict(bg="#FFFFFF", card="#F8FAFC", cardb="rgba(15,118,110,0.25)", head="#EEF2F7",
                  title="#0F172A", text="#475569", muted="#94A3B8", accent="#0F766E", blue="#1D4ED8",
                  chip="#E0E7FF", chipt="#1E40AF", bar="#E2E8F0", star="#D97706", glow="#0F766E"),
}

MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"
SANS = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"


# ------------------------------------------------------------------ datos
def fetch_languages():
    repos = [p["repo"] for p in PROJECTS] + [FEATURED["repo"]]
    data = {}
    for r in repos:
        req = urllib.request.Request(f"https://api.github.com/repos/{r}/languages",
                                     headers={"User-Agent": "profile-cards"})
        tok = os.environ.get("GITHUB_TOKEN")
        if tok:
            req.add_header("Authorization", f"Bearer {tok}")
        data[r] = json.loads(urllib.request.urlopen(req, timeout=30).read())
    LANGS.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


def top_langs(langs, n=3):
    total = sum(langs.values()) or 1
    items = [kv for kv in sorted(langs.items(), key=lambda kv: -kv[1]) if kv[1] / total >= 0.01]
    top = [(k, v / total) for k, v in items[:n]]
    rest = 1 - sum(p for _, p in top)
    if rest > 0.005:
        top.append(("Otros", rest))
    return top


def b64img(path, w, h, q=72):
    im = Image.open(path).convert("RGB")
    sw, sh = im.size
    r = w / h
    if sw / sh > r:
        nw = int(sh * r)
        im = im.crop(((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh))
    else:
        im = im.crop((0, 0, sw, int(sw / r)))
    im = im.resize((w * 2, h * 2), Image.LANCZOS)  # 2x para pantallas retina
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=q)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    return lines


def style(t):
    return (f"<style>text{{font-family:{SANS}}}.m{{font-family:{MONO}}}"
            ".c{opacity:0;animation:up .6s cubic-bezier(.2,.7,.2,1) forwards}"
            "@keyframes up{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}"
            ".g{transform:scaleX(0);animation:grow 1s ease-out forwards}"
            "@keyframes grow{to{transform:scaleX(1)}}"
            ".cur{animation:blink 1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
            ".live{animation:pulse 1.6s ease-in-out infinite}@keyframes pulse{50%{opacity:.25}}"
            "@media (prefers-reduced-motion:reduce){.c{animation:none;opacity:1}.g{animation:none;transform:none}.cur,.live{animation:none}}"
            "</style>")


def lang_bar(x, y, w, langs, t, delay):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="6" rx="3" fill="{t["bar"]}"/>',
           f'<g class="g" style="transform-origin:{x}px {y}px;transform-box:view-box;animation-delay:{delay:.2f}s">']
    cx = x
    for i, (k, p) in enumerate(langs):
        pw = w * p
        col = COLORS.get(k, t["muted"])
        rx = ' rx="3"' if i in (0, len(langs) - 1) else ""
        out.append(f'<rect x="{cx:.1f}" y="{y}" width="{max(pw, 1):.1f}" height="6"{rx} fill="{col}"/>')
        cx += pw
    out.append("</g>")
    lx = x
    for k, p in langs[:3]:
        label = f"{k} {p * 100:.0f}%"
        out.append(f'<circle cx="{lx + 4}" cy="{y + 20}" r="4" fill="{COLORS.get(k, t["muted"])}"/>'
                   f'<text x="{lx + 13}" y="{y + 24}" font-size="11" fill="{t["text"]}">{escape(label)}</text>')
        lx += 13 + len(label) * 6.4 + 14
    return "".join(out)


# ------------------------------------------------------------------ tarjetas
def slug(p):
    return p["repo"].split("/")[1].lower().replace("_", "-").replace(".", "-")


def heading_svg(t):
    W, H = 1180, 44
    return chr(10).join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Proyectos">', style(t),
        f'<text class="m" x="2" y="28" font-size="17" font-weight="700" letter-spacing="3" fill="{t["accent"]}">PROYECTOS.LIST</text>',
        f'<text class="m" x="218" y="28" font-size="15" fill="{t["muted"]}">./proyectos.sh --todos</text>',
        f'<line x1="440" y1="23" x2="{W - 2}" y2="23" stroke="{t["bar"]}" stroke-width="2" stroke-dasharray="2 6"/>',
        "</svg>"])


def card_svg(p, i, t, langs):
    """Una tarjeta por proyecto: en el README cada una va dentro de su propio enlace."""
    W, H, tw, th = 480, 410, 448, 196
    x, d = 16, 0.1 + i * 0.12
    thumb = b64img(ROOT / "assets" / "projects" / p["thumb"], tw, th)
    kw = len(p["kind"]) * 7 + 18
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="{escape(p["name"])}: {escape(p["desc"])} Abrir el repositorio.">', style(t),
         "<style>.arr{animation:nudge 1.6s ease-in-out infinite}@keyframes nudge{50%{transform:translateX(4px)}}"
         "@media (prefers-reduced-motion:reduce){.arr{animation:none}}</style>",
         f'<g class="c" style="animation-delay:{d:.2f}s">',
         f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="{t["card"]}" stroke="{t["cardb"]}" stroke-width="1.5"/>',
         f'<path d="M1.5 15a13.5 13.5 0 0 1 13.5-13.5h{W - 30}a13.5 13.5 0 0 1 13.5 13.5v23h-{W - 3}z" fill="{t["head"]}"/>',
         f'<text class="m" x="{x}" y="25" font-size="12.5" fill="{t["text"]}">▸ {escape(p["repo"])}</text>',
         f'<rect x="{W - x - kw}" y="10" width="{kw}" height="20" rx="10" fill="none" stroke="{t["accent"]}" stroke-opacity=".6"/>',
         f'<text class="m" x="{W - x - kw / 2}" y="24" font-size="11" text-anchor="middle" fill="{t["accent"]}">{p["kind"]}</text>',
         f'<clipPath id="t"><rect x="{x}" y="52" width="{tw}" height="{th}" rx="8"/></clipPath>',
         f'<image href="{thumb}" x="{x}" y="52" width="{tw}" height="{th}" clip-path="url(#t)" preserveAspectRatio="xMidYMid slice"/>',
         f'<rect x="{x + .5}" y="52.5" width="{tw - 1}" height="{th - 1}" rx="8" fill="none" stroke="{t["cardb"]}"/>',
         f'<text x="{x}" y="280" font-size="22" font-weight="700" fill="{t["title"]}">{escape(p["name"])}<tspan class="cur" fill="{t["accent"]}">_</tspan></text>',
         f'<text class="m" x="{W - x}" y="279" font-size="13" text-anchor="end" fill="{t["accent"]}">✓ <tspan fill="{t["text"]}">{escape(p["metric"])}</tspan></text>']
    for j, line in enumerate(wrap(p["desc"], 64)):
        o.append(f'<text x="{x}" y="{304 + j * 19}" font-size="14" fill="{t["text"]}">{escape(line)}</text>')
    o.append(lang_bar(x, 344, tw, top_langs(langs[p["repo"]]), t, d + 0.4))
    cx = x
    for tag in p["tags"]:
        w = len(tag) * 7.2 + 20
        o.append(f'<rect x="{cx:.0f}" y="378" width="{w:.0f}" height="22" rx="11" fill="{t["chip"]}"/>'
                 f'<text x="{cx + w / 2:.0f}" y="393" font-size="12" text-anchor="middle" fill="{t["chipt"]}">{escape(tag)}</text>')
        cx += w + 7
    o.append(f'<text class="m" x="{W - x - 20}" y="393" font-size="13" font-weight="700" text-anchor="end" fill="{t["accent"]}">Ver repositorio</text>'
             f'<text class="m arr" x="{W - x - 14}" y="393" font-size="13" font-weight="700" fill="{t["accent"]}">→</text>')
    o.append("</g></svg>")
    return chr(10).join(o)


# ------------------------------------------------------------------ destacado
def featured_svg(t, langs):
    f = FEATURED
    W, H = 1180, 470
    sx, sy, sw, sh = 28, 84, 600, 340
    shots = [b64img(HERE / "shots" / s, sw, sh, q=70) for s in f["shots"]]
    n, hold, fade = len(shots), 3.0, 0.8
    dur = n * hold
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Proyecto destacado: {escape(f["name"])}, {escape(f["repo"])}">', style(t),
         f'<defs><linearGradient id="fg" x1="0" x2="1"><stop offset="0" stop-color="{t["accent"]}"/><stop offset="1" stop-color="{t["blue"]}"/></linearGradient>'
         f'<clipPath id="shot"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="10"/></clipPath></defs>',
         f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="{t["card"]}" stroke="url(#fg)" stroke-width="2"/>',
         f'<text class="m" x="{sx}" y="40" font-size="12" font-weight="700" letter-spacing="3" fill="{t["star"]}">★ PROYECTO DESTACADO</text>',
         f'<text class="m" x="{sx + 210}" y="40" font-size="12" fill="{t["muted"]}">{escape(f["repo"])}</text>',
         f'<g class="live"><circle cx="{W - 120}" cy="36" r="4.5" fill="#22C55E"/></g>'
         f'<text class="m" x="{W - 28}" y="40" font-size="12" text-anchor="end" fill="#22C55E">DEMO EN LÍNEA</text>',
         f'<line x1="{sx}" y1="58" x2="{W - 28}" y2="58" stroke="{t["bar"]}"/>',
         f'<g clip-path="url(#shot)"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="{t["head"]}"/>']
    for i, img in enumerate(shots):
        a, b = i * hold / dur, (i + 1) * hold / dur
        fa, fb = max(a - fade / dur, 0), min(b + fade / dur, 1)
        if i == 0:
            kt, vals = f"0;{b:.3f};{fb:.3f};{1 - fade / dur:.3f};1", "1;1;0;0;1"
        else:
            kt, vals = f"0;{fa:.3f};{a:.3f};{b:.3f};{fb:.3f};1", "0;0;1;1;0;0"
        o.append(f'<image href="{img}" x="{sx}" y="{sy}" width="{sw}" height="{sh}" preserveAspectRatio="xMidYMin slice" opacity="{1 if i == 0 else 0}">'
                 f'<animate attributeName="opacity" dur="{dur}s" repeatCount="indefinite" keyTimes="{kt}" values="{vals}"/></image>')
    o.append("</g>")
    o.append(f'<rect x="{sx + .5}" y="{sy + .5}" width="{sw - 1}" height="{sh - 1}" rx="10" fill="none" stroke="{t["cardb"]}"/>')
    # leyenda de la captura
    for i, cap in enumerate(f["captions"]):
        a, b = i * hold / dur, (i + 1) * hold / dur
        kt = f"0;{max(a - .001, 0):.3f};{a:.3f};{b - .001:.3f};{b:.3f};1" if i else f"0;{b - .001:.3f};{b:.3f};1"
        vals = "0;0;1;1;0;0" if i else "1;1;0;0"
        o.append(f'<text class="m" x="{sx}" y="{sy + sh + 22}" font-size="11.5" fill="{t["muted"]}" opacity="{1 if i == 0 else 0}">◂ {escape(cap)} ▸'
                 f'<animate attributeName="opacity" dur="{dur}s" repeatCount="indefinite" keyTimes="{kt}" values="{vals}"/></text>')
    # puntos del carrusel
    for i in range(n):
        a, b = i * hold / dur, (i + 1) * hold / dur
        kt = f"0;{max(a - .001, 0):.3f};{a:.3f};{b - .001:.3f};{b:.3f};1" if i else f"0;{b - .001:.3f};{b:.3f};1"
        vals = "0;0;1;1;0;0" if i else "1;1;0;0"
        cx = sx + sw - (n - i) * 16
        o.append(f'<circle cx="{cx}" cy="{sy + sh + 18}" r="4" fill="{t["bar"]}"/>'
                 f'<circle cx="{cx}" cy="{sy + sh + 18}" r="4" fill="{t["accent"]}" opacity="{1 if i == 0 else 0}">'
                 f'<animate attributeName="opacity" dur="{dur}s" repeatCount="indefinite" keyTimes="{kt}" values="{vals}"/></circle>')
    # columna derecha
    rx = sx + sw + 36
    o.append(f'<g class="c" style="animation-delay:.2s"><text x="{rx}" y="{sy + 22}" font-size="26" font-weight="800" fill="{t["title"]}">{escape(f["name"])}'
             f'<tspan class="cur" fill="{t["accent"]}">_</tspan></text></g>')
    for j, line in enumerate(f["desc"]):
        o.append(f'<g class="c" style="animation-delay:{.35 + j * .08:.2f}s"><text x="{rx}" y="{sy + 56 + j * 19}" font-size="13.5" fill="{t["text"]}">{escape(line)}</text></g>')
    ky = sy + 128
    kw = (W - 28 - rx - 3 * 10) // 4
    for j, (num, lab) in enumerate(f["kpis"]):
        kx = rx + j * (kw + 10)
        o.append(f'<g class="c" style="animation-delay:{.6 + j * .12:.2f}s">'
                 f'<rect x="{kx}" y="{ky}" width="{kw}" height="66" rx="10" fill="{t["head"]}" stroke="{t["cardb"]}"/>'
                 f'<text class="m" x="{kx + 14}" y="{ky + 32}" font-size="24" font-weight="800" fill="url(#fg)">{escape(num)}</text>'
                 f'<text x="{kx + 14}" y="{ky + 52}" font-size="11" fill="{t["text"]}">{escape(lab)}</text></g>')
    cy, chx = ky + 96, rx
    o.append(f'<g class="c" style="animation-delay:1.1s">')
    for tag in f["stack"]:
        tw_ = len(tag) * 7 + 20
        if chx + tw_ > W - 28:
            chx, cy = rx, cy + 28
        o.append(f'<rect x="{chx:.0f}" y="{cy}" width="{tw_:.0f}" height="22" rx="11" fill="{t["chip"]}"/>'
                 f'<text x="{chx + tw_ / 2:.0f}" y="{cy + 15}" font-size="11.5" text-anchor="middle" fill="{t["chipt"]}">{escape(tag)}</text>')
        chx += tw_ + 7
    o.append("</g>")
    o.append(f'<g class="c" style="animation-delay:1.3s">{lang_bar(rx, cy + 46, W - 28 - rx, top_langs(langs[f["repo"]]), t, 1.5)}</g>')
    o.append(f'<text class="m" x="{rx}" y="{sy + sh + 22}" font-size="11.5" fill="{t["muted"]}">Proyecto en equipo · repositorio oficial en dual-devs0</text>')
    o.append("</svg>")
    return "\n".join(o)


def save(name, svg):
    p = ROOT / "assets" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(svg, encoding="utf-8")
    print(f"{name}: {len(svg.encode()) / 1024:.0f} KB")


if __name__ == "__main__":
    langs = fetch_languages() if "--fetch" in sys.argv else json.loads(LANGS.read_text(encoding="utf-8"))
    for name, t in THEMES.items():
        save(f"cards/heading-{name}.svg", heading_svg(t))
        for i, p in enumerate(PROJECTS):
            save(f"cards/{slug(p)}-{name}.svg", card_svg(p, i, t, langs))
        save(f"featured-{name}.svg", featured_svg(t, langs))
