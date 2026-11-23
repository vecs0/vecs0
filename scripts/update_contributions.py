"""Descarga el calendario público de contribuciones y genera un mapa SVG animado.

Uso: python scripts/update_contributions.py [usuario] [carpeta_salida]
Solo usa la biblioteca estándar y no necesita token: lee
https://github.com/users/<usuario>/contributions, la misma página que usa el perfil.
Escribe <salida>/contributions.json y <salida>/contrib-heatmap.svg.
"""
import json
import re
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

USER = sys.argv[1] if len(sys.argv) > 1 else "vecs0"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "dist"

PALETTE = ["#161B22", "#0C2D6B", "#1D4ED8", "#3B82F6", "#60A5FA", "#BFDBFE"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = {1: "lun", 3: "mié", 5: "vie"}


def fetch(user):
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "profile-heatmap-script"},
    )
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    cells = re.findall(
        r'data-date="(\d{4}-\d\d-\d\d)" id="contribution-day-component-(\d+)-(\d+)" data-level="(\d)"', html)
    tips = {
        (r, c): t for r, c, t in re.findall(
            r'<tool-tip[^>]*for="contribution-day-component-(\d+)-(\d+)"[^>]*>([^<]+)</tool-tip>', html)
    }
    if not cells:
        raise SystemExit("No se encontró el calendario: GitHub cambió el HTML.")
    days = []
    for d, r, c, lvl in cells:
        m = re.match(r"(\d+) contribution", tips.get((r, c), ""))
        days.append({"date": d, "count": int(m.group(1)) if m else 0, "level": int(lvl)})
    days.sort(key=lambda x: x["date"])
    return days


def stats(days):
    total = sum(d["count"] for d in days)
    active = sum(1 for d in days if d["count"])
    best = max(days, key=lambda d: d["count"])
    longest = cur = 0
    for d in days:
        cur = cur + 1 if d["count"] else 0
        longest = max(longest, cur)
    current = 0
    for d in reversed(days):
        if d["count"]:
            current += 1
        elif current or d["date"] != days[-1]["date"]:
            break
    return {"total": total, "active_days": active, "longest_streak": longest,
            "current_streak": current, "best_day": best}


def render(days, st):
    cell, gap = 13, 3
    left, top = 44, 46
    first = date.fromisoformat(days[0]["date"])
    start = first - timedelta(days=(first.weekday() + 1) % 7)  # domingo
    weeks = (date.fromisoformat(days[-1]["date"]) - start).days // 7 + 1
    W = left + weeks * (cell + gap) + 24
    H = top + 7 * (cell + gap) + 70
    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Mapa de contribuciones de {USER}: {st["total"]} en el último año">',
        "<style>text{font-family:'Segoe UI',-apple-system,Helvetica,Arial,sans-serif;fill:#8B949E;font-size:11px}"
        ".h{fill:#E6EDF3;font-size:14px;font-weight:600}.s{fill:#E6EDF3;font-weight:600}"
        ".q{opacity:0;animation:in .4s ease-out forwards}"
        "@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
        "@media (prefers-reduced-motion:reduce){.q{animation:none;opacity:1}}</style>",
        f'<rect width="{W}" height="{H}" rx="12" fill="#0B1220" stroke="#1E3A8A"/>',
        f'<text class="h" x="{left}" y="26">{st["total"]} contribuciones en el último año</text>',
    ]
    last_month = None
    for d in days:
        dt = date.fromisoformat(d["date"])
        w = (dt - start).days // 7
        r = (dt.weekday() + 1) % 7
        x, y = left + w * (cell + gap), top + r * (cell + gap)
        if r == 0 and dt.month != last_month and dt.day <= 7:
            o.append(f'<text x="{x}" y="{top - 8}">{MESES[dt.month - 1]}</text>')
            last_month = dt.month
        delay = (w + r) * 0.012
        title = f'{d["count"]} el {dt.day} {MESES[dt.month - 1]} {dt.year}'
        o.append(f'<rect class="q" style="animation-delay:{delay:.2f}s" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{PALETTE[min(d["level"], 4)]}"><title>{title}</title></rect>')
    for r, name in DIAS.items():
        o.append(f'<text x="10" y="{top + r * (cell + gap) + 10}">{name}</text>')
    fy = top + 7 * (cell + gap) + 30
    bd = st["best_day"]
    bdt = date.fromisoformat(bd["date"])
    items = [("Días activos", st["active_days"]), ("Racha más larga", f'{st["longest_streak"]} d'),
             ("Racha actual", f'{st["current_streak"]} d'), ("Mejor día", f'{bd["count"]} · {bdt.day} {MESES[bdt.month - 1]}')]
    x = left
    for label, val in items:
        o.append(f'<text x="{x}" y="{fy}">{label}</text><text class="s" x="{x}" y="{fy + 18}">{val}</text>')
        x += 150
    lx = W - 24 - 5 * (cell + gap) - 70
    o.append(f'<text x="{lx}" y="{fy + 12}">Menos</text>')
    for i in range(5):
        o.append(f'<rect x="{lx + 38 + i * (cell + gap)}" y="{fy + 2}" width="{cell}" height="{cell}" rx="3" fill="{PALETTE[i]}"/>')
    o.append(f'<text x="{lx + 38 + 5 * (cell + gap) + 4}" y="{fy + 12}">Más</text>')
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    days = fetch(USER)
    st = stats(days)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "contributions.json").write_text(json.dumps({"user": USER, "stats": st, "days": days}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "contrib-heatmap.svg").write_text(render(days, st), encoding="utf-8")
    print(json.dumps(st, ensure_ascii=False))
