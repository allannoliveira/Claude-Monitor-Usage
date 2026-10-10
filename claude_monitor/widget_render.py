"""Desenho do widget da barra de tarefas (somente Pillow, sem Win32).

Cada estilo recebe as linhas (5h / 7d), a altura disponível em pixels físicos
e a escala de DPI, e devolve uma imagem RGBA com fundo transparente.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .formatting import compact_until, level

STYLES = {
    "segmentos": "Segmentos",
    "barra": "Barra contínua",
    "compacto": "Compacto",
}
STYLE_ORDER = list(STYLES)

ACCENT = (232, 113, 78)  # laranja Claude
LEVEL_COLORS = {"ok": (46, 204, 113), "warn": (241, 196, 15), "crit": (231, 76, 60)}


@dataclass
class Row:
    label: str
    percentage: float | None
    resets_at: datetime | None


@dataclass
class Palette:
    text: tuple
    dim: tuple
    track: tuple


DARK = Palette(text=(240, 240, 240), dim=(165, 165, 165), track=(85, 85, 85))
LIGHT = Palette(text=(20, 20, 20), dim=(90, 90, 90), track=(190, 190, 190))


def next_style(style: str) -> str:
    index = STYLE_ORDER.index(style) if style in STYLE_ORDER else -1
    return STYLE_ORDER[(index + 1) % len(STYLE_ORDER)]


@lru_cache(maxsize=16)
def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = (["seguisb.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"] if bold else []) + [
        "segoeui.ttf", "DejaVuSans.ttf", "arial.ttf",
    ]
    dirs = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/TTF"),
    ]
    for name in names:
        for folder in dirs:
            path = folder / name
            if path.is_file():
                try:
                    return ImageFont.truetype(str(path), size)
                except OSError:
                    continue
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow antigo
        return ImageFont.load_default()


def _pct_text(row: Row) -> str:
    return "--" if row.percentage is None else f"{row.percentage:.0f}%"


def _reset_text(row: Row) -> str:
    return f" · {compact_until(row.resets_at)}" if row.resets_at else ""


def _text_block(d: ImageDraw.ImageDraw, x: int, cy: int, row: Row, pal: Palette,
                font, bold_font) -> None:
    pct = _pct_text(row)
    d.text((x, cy), pct, fill=pal.text, font=bold_font, anchor="lm")
    d.text((x + bold_font.getlength(pct), cy), _reset_text(row), fill=pal.dim, font=font, anchor="lm")


def render(rows: list[Row], style: str, height: int, scale: float, light: bool = False) -> Image.Image:
    pal = LIGHT if light else DARK
    s = max(scale, 0.5)
    font = _font(round(12 * s))
    bold = _font(round(12 * s), bold=True)
    pad = round(6 * s)
    label_w = max(font.getlength(r.label) for r in rows) if rows else 0
    text_reserve = bold.getlength("100%") + font.getlength(" · 23h")
    centers = [round(height * 0.29), round(height * 0.71)] if len(rows) > 1 else [height // 2]

    if style == "barra":
        bar_w, bar_h = round(96 * s), max(3, round(6 * s))
        x_bar = pad + label_w + round(6 * s)
        x_text = x_bar + bar_w + round(8 * s)
    elif style == "compacto":
        dot = max(4, round(8 * s))
        x_label = pad + dot + round(5 * s)
        x_text = x_label + label_w + round(6 * s)
    else:  # segmentos
        n, seg_w, seg_h, gap = 10, round(9 * s), round(12 * s), max(1, round(2 * s))
        x_bar = pad + label_w + round(6 * s)
        x_text = x_bar + n * seg_w + (n - 1) * gap + round(8 * s)

    width = int(x_text + text_reserve + pad)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    for row, cy in zip(rows, centers):
        pct = row.percentage
        lvl_color = LEVEL_COLORS[level(pct)] if pct is not None else pal.track

        if style == "compacto":
            d.ellipse((pad, cy - dot // 2, pad + dot, cy - dot // 2 + dot), fill=lvl_color)
            d.text((x_label, cy), row.label, fill=pal.dim, font=font, anchor="lm")
        else:
            d.text((pad, cy), row.label, fill=pal.dim, font=font, anchor="lm")

        if style == "barra":
            top = cy - bar_h // 2
            d.rounded_rectangle((x_bar, top, x_bar + bar_w, top + bar_h), radius=bar_h // 2, fill=pal.track)
            if pct:
                fill_w = max(bar_h, round(bar_w * min(pct, 100) / 100))
                d.rounded_rectangle((x_bar, top, x_bar + fill_w, top + bar_h), radius=bar_h // 2, fill=lvl_color)
        elif style != "compacto":
            filled = 0 if pct is None else max(0, min(n, round(pct / 10)))
            if pct and pct > 0 and filled == 0:
                filled = 1
            color = LEVEL_COLORS["crit"] if pct is not None and pct >= 90 else ACCENT
            top = cy - seg_h // 2
            for i in range(n):
                x0 = x_bar + i * (seg_w + gap)
                d.rounded_rectangle((x0, top, x0 + seg_w - 1, top + seg_h - 1),
                                    radius=max(1, round(2 * s)),
                                    fill=color if i < filled else pal.track)

        _text_block(d, round(x_text), cy, row, pal, font, bold)

    return img


def system_uses_light_theme() -> bool:
    """Tema da barra de tarefas do Windows (claro/escuro)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 1
    except (ImportError, OSError):
        return False
