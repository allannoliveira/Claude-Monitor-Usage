"""Personagem com emoções que reage ao uso do Claude Code.

O humor vem do MAIOR percentual entre a sessão (5h) e a semana (7d):

    0–10%   dormindo  (Zzz subindo)
    10–50%  feliz     (pisca de vez em quando)
    50–75%  focado    (gota de suor)
    75–95%  bravo     (treme e solta fumaça)
    ≥95%    chorando  (lágrimas escorrendo)

Arte própria (opcional): coloque ``<humor>.gif`` ou ``<humor>.png`` em
``<pasta de configuração>/personagem/`` (ex.: ``%APPDATA%\\claude-monitor\\personagem\\bravo.gif``)
e ela substitui o desenho gerado por código para aquele humor.
"""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageSequence

from . import paths

# (limite superior exclusivo, humor) — o último vale para todo o resto
MOOD_THRESHOLDS = [(10, "dormindo"), (50, "feliz"), (75, "focado"), (95, "bravo")]
MOOD_MAX = "chorando"
MOODS = [m for _, m in MOOD_THRESHOLDS] + [MOOD_MAX]
MOOD_LABELS = {
    "dormindo": "Dormindo 😴",
    "feliz": "Feliz 🙂",
    "focado": "Focado 😐",
    "bravo": "Bravo 😠",
    "chorando": "Chorando 😭",
}

GRID_W, GRID_H = 30, 24   # grade da pixel art (o personagem ocupa x 0..23)
FRAME_MS = 300

Frame = tuple[Image.Image, int]

# paleta
ORANGE = (232, 113, 78, 255)
ORANGE_HI = (247, 160, 125, 255)
ANGRY = (222, 74, 56, 255)
ANGRY_HI = (240, 120, 100, 255)
OUTLINE = (120, 48, 30, 255)
DARK = (36, 22, 18, 255)
WHITE = (255, 255, 255, 255)
BLUSH = (247, 140, 120, 255)
TEAR = (96, 176, 255, 255)
STEAM = (225, 225, 225, 230)
LEAF = (98, 186, 92, 255)
ZCOLOR = (190, 205, 255, 255)


def mood_for(percentage: float | None) -> str:
    if percentage is None:
        return "feliz"
    for limit, mood in MOOD_THRESHOLDS:
        if percentage < limit:
            return mood
    return MOOD_MAX


# ------------------------------------------------------------------ desenho
def _px(d: ImageDraw.ImageDraw, points, color, dx=0, dy=0) -> None:
    for x, y in points:
        d.point((x + dx, y + dy), fill=color)


def _body(d, dx, dy, color, highlight, squash=0) -> None:
    d.ellipse((2 + dx, 6 + dy + squash, 21 + dx, 23 + dy), fill=color, outline=OUTLINE)
    _px(d, [(6, 9 + squash), (7, 9 + squash), (6, 10 + squash)], highlight, dx, dy)
    # pezinhos
    d.rectangle((6 + dx, 22 + dy, 8 + dx, 23 + dy), fill=OUTLINE)
    d.rectangle((15 + dx, 22 + dy, 17 + dx, 23 + dy), fill=OUTLINE)


def _sprout(d, dx, dy, sway=0) -> None:
    _px(d, [(11, 4), (11, 5)], LEAF, dx, dy)
    _px(d, [(12 + sway, 3), (13 + sway, 3), (13 + sway, 2)], LEAF, dx, dy)
    _px(d, [(10 - sway, 3), (9 - sway, 2)], LEAF, dx, dy)


def _z(d, x, y, size, color=ZCOLOR) -> None:
    """Letra Z em pixel art (size >= 4 para a diagonal aparecer)."""
    n = size - 1
    d.line((x, y, x + n, y), fill=color)
    for i in range(1, n):
        d.point((x + n - i, y + i), fill=color)
    d.line((x, y + n, x + n, y + n), fill=color)


def _draw(mood: str, f: int) -> Image.Image:
    img = Image.new("RGBA", (GRID_W, GRID_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if mood == "dormindo":
        squash = f % 2  # respiração
        _body(d, 0, 0, ORANGE, ORANGE_HI, squash)
        _sprout(d, 0, squash)
        for ex in (6, 13):  # olhos fechados ‿
            _px(d, [(ex, 14), (ex + 1, 15), (ex + 2, 15), (ex + 3, 14)], DARK)
        _px(d, [(11, 19), (12, 19)], DARK)  # boquinha
        # Zzz subindo e voltando
        rise = f % 4
        _z(d, 21, 13 - rise, 4)
        _z(d, 25, 6 - rise, 5)
        if rise < 3:
            _z(d, 22, 2 + (2 - rise) // 2, 4, (150, 170, 240, 200))

    elif mood == "feliz":
        dy = -1 if f in (1, 2) else 0  # pulinho
        _body(d, 0, dy, ORANGE, ORANGE_HI)
        _sprout(d, 0, dy, sway=1 if f == 1 else 0)
        if f == 3:  # piscada
            _px(d, [(7, 14 + dy), (8, 14 + dy), (14, 14 + dy), (15, 14 + dy)], DARK)
        else:
            d.rectangle((7, 12 + dy, 8, 14 + dy), fill=DARK)
            d.rectangle((14, 12 + dy, 15, 14 + dy), fill=DARK)
            _px(d, [(7, 12 + dy), (14, 12 + dy)], WHITE)
        _px(d, [(9, 17), (10, 18), (11, 18), (12, 18), (13, 17)], DARK, 0, dy)  # sorriso
        _px(d, [(4, 16), (5, 16), (17, 16), (18, 16)], BLUSH, 0, dy)

    elif mood == "focado":
        _body(d, 0, 0, ORANGE, ORANGE_HI)
        _sprout(d, 0, 0)
        d.line((6, 10, 9, 10), fill=DARK)    # sobrancelhas retas
        d.line((13, 10, 16, 10), fill=DARK)
        d.rectangle((7, 12, 8, 13), fill=DARK)
        d.rectangle((14, 12, 15, 13), fill=DARK)
        d.line((9, 18, 13, 18), fill=DARK)   # boca reta
        y = 6 + (f % 4)                      # gota de suor descendo
        _px(d, [(20, y), (19, y + 1), (20, y + 1), (19, y + 2), (20, y + 2), (21, y + 2),
                (19, y + 3), (20, y + 3), (21, y + 3), (20, y + 4)], TEAR)
        _px(d, [(19, y + 2)], WHITE)

    elif mood == "bravo":
        dx = (-1, 1, 0, 1)[f % 4]            # tremendo
        _body(d, dx, 0, ANGRY, ANGRY_HI)
        # sobrancelhas em V
        _px(d, [(5, 9), (6, 9), (7, 10), (8, 11), (9, 11)], DARK, dx)
        _px(d, [(17, 9), (16, 9), (15, 10), (14, 11), (13, 11)], DARK, dx)
        d.rectangle((7 + dx, 13, 8 + dx, 14), fill=DARK)
        d.rectangle((14 + dx, 13, 15 + dx, 14), fill=DARK)
        _px(d, [(9, 19), (10, 18), (11, 18), (12, 18), (13, 19)], DARK, dx)  # careta
        # veia de raiva
        _px(d, [(17, 6), (19, 6), (18, 7), (17, 8), (19, 8)], DARK, dx)
        # fumaça saindo da cabeça
        up = f % 3
        for sx in (2, 17):  # nuvenzinhas de vapor
            d.rounded_rectangle((sx + dx, 3 - up, sx + 4 + dx, 5 - up), radius=1, fill=STEAM)
            d.rectangle((sx + 1 + dx, 2 - up, sx + 3 + dx, 2 - up), fill=STEAM)
        if up < 2:
            d.rounded_rectangle((23, 1 + up, 28, 4 + up), radius=1, fill=STEAM)

    else:  # chorando
        _body(d, 0, 0, ORANGE, ORANGE_HI)
        _sprout(d, 0, 1)  # brotinho murcho
        for ex in (6, 13):  # olhos apertados ∩
            _px(d, [(ex, 14), (ex + 1, 13), (ex + 2, 13), (ex + 3, 14)], DARK)
        d.rectangle((10, 17, 12, 20), fill=DARK)     # boca aberta (berrando)
        _px(d, [(11, 20)], (200, 80, 80, 255))
        # cachoeira de lágrimas
        for tx in (6, 16):
            length = 3 + (f % 4) * 2
            d.line((tx, 15, tx, min(15 + length, 22)), fill=TEAR)
            if f % 2:
                _px(d, [(tx - 1, 17), (tx + 1, 19)], TEAR)
        if f % 4 >= 2:  # poça
            d.line((3, 23, 8, 23), fill=TEAR)
            d.line((14, 23, 19, 23), fill=TEAR)
    return img


def _custom_frames(mood: str) -> list[Frame] | None:
    folder = paths.user_config_dir() / "personagem"
    for ext in ("gif", "png"):
        path = folder / f"{mood}.{ext}"
        if not path.is_file():
            continue
        try:
            with Image.open(path) as img:
                frames = [
                    (frame.convert("RGBA"), max(50, int(frame.info.get("duration") or FRAME_MS)))
                    for frame in ImageSequence.Iterator(img)
                ]
            return frames or None
        except Exception as exc:
            print(f"[aviso] personagem {path} inválido: {exc}. Usando o desenho padrão.")
    return None


@lru_cache(maxsize=32)
def frames(mood: str, height: int) -> tuple[Frame, ...]:
    """Quadros do humor, escalados (sem suavização) para a altura pedida."""
    raw = _custom_frames(mood) or [(_draw(mood, i), FRAME_MS) for i in range(4)]
    out = []
    for img, ms in raw:
        factor = max(1, height // img.height) if img.height <= height else height / img.height
        size = (max(1, round(img.width * factor)), max(1, round(img.height * factor)))
        resample = Image.Resampling.NEAREST if factor >= 1 else Image.Resampling.LANCZOS
        out.append((img.resize(size, resample), ms))
    return tuple(out)


def clear_cache() -> None:
    frames.cache_clear()
