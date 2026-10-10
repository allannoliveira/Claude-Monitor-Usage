"""Discipulinho: personagem com emoções que reage ao uso do Claude Code.

O humor vem do MAIOR percentual entre a sessão (5h) e a semana (7d):

    0–10%   dormindo  (Zzz subindo)
    10–50%  feliz     (pisca de vez em quando)
    50–75%  focado    (lendo a Bíblia)
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
    "focado": "Focado 📖",
    "bravo": "Bravo 😠",
    "chorando": "Chorando 😭",
}

GRID_W, GRID_H = 30, 24   # grade da pixel art (o personagem ocupa x 0..23)
FRAME_MS = 300

Frame = tuple[Image.Image, int]

def mood_for(percentage: float | None) -> str:
    if percentage is None:
        return "feliz"
    for limit, mood in MOOD_THRESHOLDS:
        if percentage < limit:
            return mood
    return MOOD_MAX


# ------------------------------------------------------------------ Discipulinho
# Pixel art 24x24 (+6 colunas à direita para Zzz/fumaça), redesenhado a partir
# da arte "Mascotes - Árvore da Vida". Cada letra do mapa é uma cor de PAL.

PAL = {
    "O": (52, 32, 22, 255),     # contorno
    "H": (112, 64, 38, 255),    # cabelo
    "h": (152, 96, 56, 255),    # cabelo claro
    "d": (82, 46, 28, 255),     # cabelo escuro
    "S": (234, 178, 126, 255),  # pele
    "s": (208, 148, 100, 255),  # pele sombra
    "T": (238, 226, 198, 255),  # túnica
    "t": (204, 188, 156, 255),  # túnica sombra
    "R": (122, 78, 44, 255),    # alça da bolsa
    "B": (34, 26, 22, 255),     # livro
    "b": (70, 56, 48, 255),     # livro borda
    "G": (230, 170, 54, 255),   # cruz dourada
}

BASE = [
    "........................",  # 0
    "..........OO.O..........",  # 1
    ".......OOOhhOhOOO.......",  # 2
    ".....OOhhHHHHHHHhOO.....",  # 3
    "....OhHHHHHHHhHHHHHO....",  # 4
    "...OHHHHHHHHHHHHHHHHO...",  # 5
    "...OHHHHHdHHHHdHHHHHO...",  # 6
    "..OHHdHHHHHHHHHHHHdHHO..",  # 7
    "..OHHHHHHHHHHHHHHHHHHO..",  # 8
    "..OHHHdHHdHHHHdHHdHHHO..",  # 9
    "..OHHSHHSSHHSSSHHSSHHO..",  # 10  franja
    ".OsHSSSSSSSSSSSSSSSSHsO.",  # 11  orelhas
    ".OsHSSSSSSSSSSSSSSSSHsO.",  # 12
    "..OSSSSSSSSSSSSSSSSSSO..",  # 13
    "..OSSSSSSSSSSSSSSSSSSO..",  # 14
    "...OSSSSSSSSSSSSSSSSO...",  # 15
    "....OSSSSSSSSSSSSSSO....",  # 16
    ".....OOOsSSSSSSsOOO.....",  # 17
    "....OOTTTOsSSsOTTTOO....",  # 18  gola em V
    "...OTTTTTTOssOTTTTTTO...",  # 19
    "..OTTRTTTTTOOTTTTTTTTO..",  # 20
    "..OTTTRTTTTTTTTTTTTTTO..",  # 21
    ".OTTTTTRTTTTTTTTTTTTTTO.",  # 22
    ".OTtTTTTRTTTTTTTTTTTtTO.",  # 23
]
assert all(len(r) == 24 for r in BASE), [len(r) for r in BASE]

BOOK = [  # Bíblia fechada segurada no peito (x=15, y=18)
    "OOOOOO",
    "ObBBBO",
    "ObBGBO",
    "ObGGGO",
    "ObBGBO",
    "OOOOOO",
]


def _stamp(img: Image.Image, rows: list[str], x0: int, y0: int, dx: int = 0, dy: int = 0) -> None:
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != "." and ch in PAL:
                X, Y = x0 + x + dx, y0 + y + dy
                if 0 <= X < img.width and 0 <= Y < img.height:
                    img.putpixel((X, Y), PAL[ch])


def _base(dx: int = 0, dy: int = 0, book: bool = True) -> Image.Image:
    """Discipulinho sem expressão (os humores desenham olhos e boca por cima)."""
    img = Image.new("RGBA", (GRID_W, GRID_H), (0, 0, 0, 0))
    _stamp(img, BASE, 0, 0, dx, dy)
    if book:
        _stamp(img, BOOK, 15, 18, dx, dy)
        for x, y in [(14, 21), (14, 22), (13, 22)]:  # mãozinha segurando o livro
            img.putpixel((x + dx, min(GRID_H - 1, y + dy)), PAL["S"])
    return img


def _draw(mood: str, f: int) -> Image.Image:
    E = PAL["O"]
    MOUTH = (176, 70, 62, 255)
    BLUSH = (242, 140, 118, 255)
    TEAR = (96, 176, 255, 255)
    WHITE = (255, 255, 255, 255)

    def eyes(d, dy=0, dx=0, h=3, top=12, shine=True):
        for ex in (7, 15):
            d.rectangle((ex + dx, top + dy, ex + 1 + dx, top + h - 1 + dy), E)
            if shine:
                d.point((ex + dx, top + dy), WHITE)

    if mood == "dormindo":
        dy = 1 if f in (1, 2) else 0                               # respirando
        img = _base(dy=dy)
        d = ImageDraw.Draw(img)
        for ex in (6, 14):                                          # olhos fechados ‿
            for x, y in [(ex, 13), (ex + 1, 14), (ex + 2, 14), (ex + 3, 13)]:
                d.point((x, y + dy), E)
        d.rectangle((11, 16 + dy, 12, 17 + dy), MOUTH)              # boquinha "o"
        z = (170, 190, 255, 255)

        def Z(x, y, n):
            d.line((x, y, x + n - 1, y), z)
            for i in range(1, n - 1):
                d.point((x + n - 1 - i, y + i), z)
            d.line((x, y + n - 1, x + n - 1, y + n - 1), z)
        rise = f % 4
        Z(22, 9 - rise, 4)
        Z(25, 4 - rise // 2, 5)
        return img

    if mood == "feliz":
        dy = -1 if f in (1, 2) else 0                               # pulinho
        img = _base(dy=dy)
        d = ImageDraw.Draw(img)
        if f == 3:                                                  # piscada ^ ^
            for ex in (6, 14):
                for x, y in [(ex, 14), (ex + 1, 13), (ex + 2, 13), (ex + 3, 14)]:
                    d.point((x, y + dy), E)
        else:
            eyes(d, dy)
        d.line((10, 16 + dy, 13, 16 + dy), E)                       # sorriso aberto
        d.line((11, 17 + dy, 12, 17 + dy), MOUTH)
        d.point((10, 17 + dy), E); d.point((13, 17 + dy), E)
        for x in (5, 6, 17, 18):
            d.point((x, 15 + dy), BLUSH)
        return img

    if mood == "focado":                                            # lendo a Bíblia
        img = _base(book=False)
        d = ImageDraw.Draw(img)
        look = (0, 1, 1, 0)[f % 4]                                  # olhos acompanhando o texto
        eyes(d, dx=look - 1 if look else 0, h=2, top=13, shine=False)
        d.line((6, 12, 8, 12), PAL["d"]); d.line((14, 12, 16, 12), PAL["d"])
        d.line((10, 16, 13, 16), PAL["s"])
        page = (250, 246, 232, 255)
        line = (176, 166, 146, 255)
        d.rectangle((4, 18, 19, 23), fill=PAL["B"])                 # capa
        d.rectangle((5, 19, 11, 23), fill=page)
        d.rectangle((12, 19, 18, 23), fill=page)
        for y in (20, 22):
            d.line((6, y, 10, y), line); d.line((13, y, 17, y), line)
        d.line((11, 19, 11, 23), (220, 212, 192, 255))
        if f % 4 == 2:                                              # virando a página
            d.polygon([(14, 19), (18, 19), (18, 21)], fill=(236, 230, 212, 255))
        for x, y in [(3, 21), (3, 22), (20, 21), (20, 22)]:         # mãozinhas
            d.point((x, y), PAL["S"])
        return img

    if mood == "bravo":
        dx = (-1, 1, 0, 1)[f % 4]                                   # tremendo
        img = _base(dx=dx)
        d = ImageDraw.Draw(img)
        angry_red = (226, 84, 64, 255)
        for x0 in (4, 17):                                          # bochechas vermelhas
            d.rectangle((x0 + dx, 15, x0 + 2 + dx, 16), angry_red)
        for x, y in [(5, 11), (6, 11), (6, 12), (7, 12), (8, 12), (8, 13)]:   # sobrancelhas em V (grossas)
            d.point((x + dx, y), E)
        for x, y in [(18, 11), (17, 11), (17, 12), (16, 12), (15, 12), (15, 13)]:
            d.point((x + dx, y), E)
        d.rectangle((7 + dx, 14, 8 + dx, 15), E)                    # olhos apertados
        d.rectangle((15 + dx, 14, 16 + dx, 15), E)
        d.line((10 + dx, 17, 13 + dx, 17), E)                       # dentes cerrados
        d.line((10 + dx, 16, 13 + dx, 16), E)
        d.line((11 + dx, 16, 12 + dx, 16), (250, 250, 250, 255))
        red = (222, 48, 40, 255)                                    # 💢
        for x, y in [(19, 2), (21, 2), (20, 3), (19, 4), (21, 4)]:
            d.point((x + dx, y), red)
        up = f % 3
        steam = (228, 228, 228, 235)
        d.rounded_rectangle((23, 6 - up, 27, 8 - up), radius=1, fill=steam)
        if up < 2:
            d.rounded_rectangle((25, 1 + up, 29, 3 + up), radius=1, fill=steam)
        return img

    # chorando
    img = _base()
    d = ImageDraw.Draw(img)
    for ex in (6, 14):                                              # olhos apertados ∩
        for x, y in [(ex, 14), (ex + 1, 13), (ex + 2, 13), (ex + 3, 14)]:
            d.point((x, y), E)
    d.line((6, 12, 8, 11), PAL["d"]); d.line((17, 12, 15, 11), PAL["d"])  # sobrancelhas tristes
    d.rectangle((10, 16, 13, 17), fill=E)                           # boca berrando
    d.line((11, 17, 12, 17), MOUTH)
    for tx in (7, 16):                                              # cachoeira de lágrimas
        length = 1 + (f % 4) * 2
        d.line((tx, 15, tx, min(15 + length, 22)), TEAR)
        if f % 2:
            d.point((tx + (-1 if tx < 12 else 1), 17), TEAR)
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
