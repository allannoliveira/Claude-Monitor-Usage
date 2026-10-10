"""Gera as animações do README em ``docs/`` usando o mesmo desenho do app.

Uso: ``python scripts/make_docs_gifs.py``

- docs/demo_barra.gif   uso subindo de 5% a 100% numa barra de tarefas simulada
- docs/humores.gif      os 5 humores do Discipulinho animados
- docs/estilos.gif      os 3 estilos do widget lado a lado
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from claude_monitor import character  # noqa: E402
from claude_monitor.widget_render import STYLES, Row, _font, render  # noqa: E402

DOCS = ROOT / "docs"
SCALE = 2                       # renderiza em 2x para ficar nítido no GitHub
BAR_H = 48 * SCALE              # altura da barra de tarefas simulada
TASKBAR = (32, 32, 32, 255)
TEXT = (235, 235, 235)
FRAME_MS = character.FRAME_MS
NOW = datetime.now(timezone.utc)


def rows(pct: float) -> list[Row]:
    return [Row("5h", pct, NOW + timedelta(hours=3, minutes=20)),
            Row("7d", max(1, pct * 0.35), NOW + timedelta(days=5, hours=2))]


def widget(pct: float, style: str, frame: int) -> Image.Image:
    sprites = character.frames(character.mood_for(pct), BAR_H)
    sprite = sprites[frame % len(sprites)][0]
    return render(rows(pct), style, BAR_H, SCALE, light=False, character=sprite)


def tray_area() -> Image.Image:
    """Lado direito de uma barra do Windows 11 (seta, ícones e relógio)."""
    img = Image.new("RGBA", (150 * SCALE, BAR_H), TASKBAR)
    d = ImageDraw.Draw(img)
    s = SCALE
    d.line((10 * s, 27 * s, 15 * s, 21 * s, 20 * s, 27 * s), fill=TEXT, width=2 * s // 2 + 1)  # ^
    for i, color in enumerate([(232, 113, 78), (120, 160, 230)]):
        x = 32 * s + i * 22 * s
        d.rounded_rectangle((x, 16 * s, x + 14 * s, 30 * s), radius=3 * s, fill=color)
    small = _font(11 * s)
    d.text((140 * s, 17 * s), "22:48", fill=TEXT, font=small, anchor="rm")
    d.text((140 * s, 33 * s), "09/10/2026", fill=TEXT, font=small, anchor="rm")
    return img


def save_gif(frames: list[Image.Image], durations: list[int], path: Path) -> None:
    pal = [f.convert("RGB").quantize(colors=255, method=Image.Quantize.MEDIANCUT) for f in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=durations,
                loop=0, optimize=True, disposal=2)
    print(f"{path.relative_to(ROOT)}  {frames[0].size}  {len(frames)} quadros")


def demo_barra() -> None:
    """Uso subindo: as barras enchem e o humor muda."""
    steps = [5, 8, 25, 40, 55, 68, 80, 90, 97, 100]
    tray = tray_area()
    width = max(widget(p, "segmentos", 0).width for p in steps)
    left_pad = 30 * SCALE
    total_w = left_pad + width + 8 * SCALE + tray.width
    frames, durations = [], []
    for pct in steps:
        for f in range(6):  # ~1,8 s por etapa, mostrando a animação do humor
            canvas = Image.new("RGBA", (total_w, BAR_H), TASKBAR)
            w = widget(pct, "segmentos", f)
            canvas.alpha_composite(w, (left_pad + width - w.width, 0))
            canvas.alpha_composite(tray, (total_w - tray.width, 0))
            frames.append(canvas)
            durations.append(FRAME_MS)
    durations[-1] = 1500
    save_gif(frames, durations, DOCS / "demo_barra.gif")


def humores() -> None:
    k = 5
    cell_w, cell_h = character.GRID_W * k, character.GRID_H * k
    label_h = 34
    bg = (245, 242, 235, 255)
    names = {"dormindo": "0–10% Dormindo", "feliz": "10–50% Feliz", "focado": "50–75% Focado",
             "bravo": "75–95% Bravo", "chorando": "≥95% Chorando"}
    font = _font(17, bold=True)
    frames = []
    for f in range(8):
        canvas = Image.new("RGBA", (len(character.MOODS) * (cell_w + 12) + 12, cell_h + label_h + 12), bg)
        d = ImageDraw.Draw(canvas)
        for i, mood in enumerate(character.MOODS):
            x = 12 + i * (cell_w + 12)
            d.text((x + cell_w // 2, 18), names[mood], fill=(60, 40, 30), font=font, anchor="mm")
            sprite = character._draw(mood, f % 4).resize((cell_w, cell_h), Image.Resampling.NEAREST)
            canvas.alpha_composite(sprite, (x, label_h))
        frames.append(canvas)
    save_gif(frames, [FRAME_MS] * len(frames), DOCS / "humores.gif")


def estilos() -> None:
    pct = 62
    font = _font(13 * SCALE // 2 + 6, bold=True)
    label_h = 30
    cells = [(label, widget(pct, key, 0).width) for key, label in STYLES.items()]
    gap = 24
    total_w = sum(w for _, w in cells) + gap * (len(cells) + 1)
    frames = []
    for f in range(4):
        canvas = Image.new("RGBA", (total_w, BAR_H + label_h + 10), TASKBAR)
        d = ImageDraw.Draw(canvas)
        x = gap
        for key, label in STYLES.items():
            w = widget(pct, key, f)
            d.text((x + w.width // 2, 16), label, fill=TEXT, font=font, anchor="mm")
            canvas.alpha_composite(w, (x, label_h))
            x += w.width + gap
        frames.append(canvas)
    save_gif(frames, [FRAME_MS] * len(frames), DOCS / "estilos.gif")


if __name__ == "__main__":
    DOCS.mkdir(exist_ok=True)
    character.clear_cache()
    demo_barra()
    humores()
    estilos()
