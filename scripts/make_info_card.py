"""Genera assets/info-card.svg: tarjeta estilo neofetch con animación de entrada.

Uso: python scripts/make_info_card.py   (STATIC=1 genera un cuadro fijo, sin animación)
Solo usa la biblioteca estándar. Editá FIELDS para cambiar el contenido.
"""
import os
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "assets" / "info-card.svg"
STATIC = os.environ.get("STATIC") == "1"

USER = "vecs0@github"
FIELDS = [
    ("Rol", "Full Stack & Mobile Developer"),
    ("Ubicación", "Paraguay"),
    ("Estudio", "Ingeniería en Informática"),
    None,
    ("Web", "Next.js · React · TypeScript"),
    ("Mobile", "React Native · Expo · SQLite"),
    ("Backend", "FastAPI · Flask · PostgreSQL"),
    ("Nube", "Supabase · Vercel · Render"),
    None,
    ("Proyectos", "6 públicos · demos, APK y .exe"),
    ("Tests", "428 mobile · 399 backend"),
    ("Busco", "rol full stack o mobile"),
]
PALETTE = ["#1E293B", "#F87171", "#34D399", "#FBBF24", "#3B82F6", "#A78BFA", "#22D3EE", "#E2E8F0"]

W, H = 588, 510
X, KEY_W, LH = 30, 112, 30


def build():
    css = """
text{font-family:'Cascadia Code',Consolas,'SFMono-Regular',Menlo,monospace;font-size:15px}
.k{fill:#60A5FA;font-weight:700}.v{fill:#E2E8F0}.p{fill:#34D399}.d{fill:#334155}.t{fill:#94A3B8;font-size:13px}
"""
    if not STATIC:
        css += """
.l{opacity:0;animation:in .45s ease-out forwards}
@keyframes in{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:none}}
.c{animation:blink 1s steps(1) infinite}
@keyframes blink{50%{opacity:0}}
@media (prefers-reduced-motion:reduce){.l{animation:none;opacity:1}.c{animation:none}}
"""
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Ficha: Victor Cabrera, Full Stack y Mobile Developer en Paraguay">',
        f"<style>{css}</style>",
        f'<rect width="{W}" height="{H}" rx="12" fill="#0B1220" stroke="#1E3A8A"/>',
        f'<path d="M0 12a12 12 0 0 1 12-12h{W - 24}a12 12 0 0 1 12 12v22H0z" fill="#13203B"/>',
        '<circle cx="20" cy="17" r="5" fill="#F87171"/><circle cx="38" cy="17" r="5" fill="#FBBF24"/><circle cx="56" cy="17" r="5" fill="#34D399"/>',
        f'<text class="t" x="{W / 2}" y="22" text-anchor="middle">~ / perfil</text>',
    ]
    y, i = 70, 0

    def line(body):
        nonlocal i
        delay = "" if STATIC else f' style="animation-delay:{0.25 + i * 0.12:.2f}s"'
        out.append(f'<g class="l"{delay}>{body}</g>')
        i += 1

    line(f'<text x="{X}" y="{y}"><tspan class="p">$</tspan><tspan class="v"> neofetch</tspan></text>')
    y += LH + 4
    line(f'<text x="{X}" y="{y}" class="k">{escape(USER)}</text>')
    y += 12
    line(f'<rect x="{X}" y="{y}" width="{len(USER) * 9}" height="2" rx="1" class="d" fill="#334155"/>')
    y += LH - 2
    for f in FIELDS:
        if f is None:
            y += 10
            continue
        k, v = f
        line(f'<text x="{X}" y="{y}"><tspan class="k">{escape(k)}</tspan></text>'
             f'<text x="{X + KEY_W}" y="{y}" class="v">{escape(v)}</text>')
        y += LH
    y += 8
    blocks = "".join(f'<rect x="{X + n * 30}" y="{y - 14}" width="24" height="16" rx="3" fill="{c}"/>' for n, c in enumerate(PALETTE))
    line(blocks)
    y += 36
    cursor = f'<rect class="c" x="{X + 22}" y="{y - 13}" width="9" height="16" fill="#E2E8F0"/>'
    line(f'<text x="{X}" y="{y}" class="p">$</text>{cursor}')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"ok: {OUT}")
