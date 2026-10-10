"""Modo bandeja do sistema (pystray + Pillow)."""

from __future__ import annotations

import os
import sys
import threading

import pystray
from PIL import Image, ImageDraw

from . import character, settings
from .formatting import human_tokens, level, local_time, text_bar, time_until
from .models import Snapshot
from .service import get_snapshot
from .widget_render import STYLES, Row
from .win_tray import promote_tray_icon

ICON_SIZE = 64          # tamanho final do ícone (o Windows reduz para 16-32 px)
MIN_FRAME_MS = 50
DOT_COLORS = {"ok": (46, 204, 113), "warn": (241, 196, 15), "crit": (231, 76, 60)}
BAR_TRACK = (70, 70, 70, 230)
BAR_OUTLINE = (255, 255, 255, 255)

Frame = tuple[Image.Image, int]  # (imagem RGBA quadrada, duração em ms)


# ------------------------------------------------------------------ ícone
def fallback_icon() -> Image.Image:
    """Ícone genérico desenhado em memória: um bonequinho simples."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, 62, 62), fill=(217, 119, 87, 255))          # fundo laranja
    d.ellipse((22, 10, 42, 30), fill=(255, 255, 255, 255))        # cabeça
    d.rounded_rectangle((16, 32, 48, 56), radius=10, fill=(255, 255, 255, 255))  # corpo
    return img


def _fit(img: Image.Image, width: int, height: int, pixel_art: bool) -> Image.Image:
    """Redimensiona mantendo proporção e centraliza num quadro width x height.

    Pixel art (GIF/paleta ou imagens pequenas) usa NEAREST para não borrar.
    """
    img = img.convert("RGBA")
    scale = min(width / img.width, height / img.height)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    resample = Image.Resampling.NEAREST if pixel_art else Image.Resampling.LANCZOS
    img = img.resize(size, resample)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.paste(img, ((width - img.width) // 2, (height - img.height) // 2), img)
    return canvas


def character_frames(mood: str) -> list[Frame]:
    """Quadros do personagem para o ícone da bandeja (quadrado 64x64)."""
    return [(_fit(img, ICON_SIZE, ICON_SIZE, True), ms)
            for img, ms in character.frames(mood, ICON_SIZE)]


def load_base_icon() -> Image.Image:
    return fallback_icon()


def _draw_bar(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int], pct: float | None) -> None:
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=BAR_TRACK, outline=BAR_OUTLINE, width=1)
    if pct is None:
        return
    inner_h = (y1 - 1) - (y0 + 1)
    fill_h = round(inner_h * max(0.0, min(pct, 100.0)) / 100)
    if pct > 0 and fill_h == 0:
        fill_h = 1
    if fill_h:
        d.rectangle((x0 + 1, y1 - 1 - fill_h, x1 - 1, y1 - 1), fill=DOT_COLORS[level(pct)] + (255,))


def compose_icon(sprite: Image.Image, pixel_art: bool, bars: list[float | None] | None,
                 show_bars: bool) -> Image.Image:
    """Monta o ícone final: personagem/ícone à esquerda + barrinhas verticais à direita
    (sessão 5h e semanal), coloridas verde/amarelo/vermelho e preenchidas de
    baixo para cima conforme o percentual."""
    if not show_bars or not bars:
        return _fit(sprite, ICON_SIZE, ICON_SIZE, pixel_art)

    bar_w, gap = 9, 2
    bars_w = len(bars) * bar_w + (len(bars) - 1) * gap
    sprite_w = ICON_SIZE - bars_w - 1
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    img.paste(_fit(sprite, sprite_w, ICON_SIZE, pixel_art), (0, 0))
    d = ImageDraw.Draw(img)
    x = ICON_SIZE - bars_w
    for pct in bars:
        _draw_bar(d, (x, 2, x + bar_w - 1, ICON_SIZE - 2), pct)
        x += bar_w + gap
    return img


# ------------------------------------------------------------------ app
class TrayApp:
    def __init__(self, interval: int = 300, include_local: bool = True,
                 animate: bool = True, show_bars: bool = False, widget: bool = True,
                 widget_style: str = "segmentos", character_on: bool = True):
        self.interval = max(60, interval)
        self.include_local = include_local
        self.snapshot: Snapshot | None = None
        self.animate = animate
        self.show_bars = show_bars
        self.character_enabled = character_on
        self.mood = "feliz"
        self.widget_enabled = widget and sys.platform == "win32"
        self.widget_style = widget_style if widget_style in STYLES else "segmentos"
        self.widget = None
        self.pixel_art = True
        self.frames: list[Frame] = self._icon_frames()
        self._bars: list[float | None] | None = None
        self._rendered: list[Frame] = []
        self._render()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.icon = pystray.Icon(
            "claude-usage-monitor",
            icon=self._rendered[0][0],
            # Tooltip inicial fixo: o Windows usa isso para identificar o ícone.
            title="Claude Code Monitor",
            menu=pystray.Menu(self._menu_items),
        )

    # -------------------------------------------------------------- preferências
    def _save_settings(self) -> None:
        settings.save({
            "widget": self.widget_enabled,
            "widget_style": self.widget_style,
            "icon_bars": self.show_bars,
            "animate": self.animate,
            "character": self.character_enabled,
        })

    # -------------------------------------------------------------- render
    def _icon_frames(self) -> list[Frame]:
        """O personagem fica no widget; a bandeja só o mostra se não houver widget."""
        if self.character_enabled and self.widget is None:
            return character_frames(self.mood)
        return [(fallback_icon(), 0)]

    def _rebuild_icon(self) -> None:
        self.frames = self._icon_frames()
        self._render()
        if not (self.animate and len(self._rendered) > 1):
            self._show_static()

    def _push_widget(self) -> None:
        if self.widget:
            self.widget.update(self._widget_rows(),
                               self.mood if self.character_enabled else None, self.animate)

    def _render(self) -> None:
        """Pré-renderiza todos os quadros com as barrinhas atuais."""
        self._rendered = [
            (compose_icon(img, self.pixel_art, self._bars, self.show_bars), ms)
            for img, ms in self.frames
        ]

    def _show_static(self) -> None:
        self.icon.icon = self._rendered[0][0]

    # Menu dinâmico: pystray chama esta função sempre que o menu é reconstruído.
    def _menu_items(self):
        items = [pystray.MenuItem(line, None, enabled=False) for line in self._lines()]
        items += [pystray.Menu.SEPARATOR,
                  pystray.MenuItem("Atualizar", self._on_refresh, default=True)]
        if sys.platform == "win32":
            styles = [
                pystray.MenuItem(label, self._style_action(key), radio=True,
                                 checked=lambda item, key=key: self.widget_style == key)
                for key, label in STYLES.items()
            ]
            items += [
                pystray.MenuItem("Widget na barra de tarefas", self._on_toggle_widget,
                                 checked=lambda item: self.widget_enabled),
                pystray.MenuItem("Estilo do widget", pystray.Menu(*styles)),
            ]
        items.append(pystray.MenuItem(
            lambda item: f"Personagem com emoções ({character.MOOD_LABELS[self.mood]})",
            self._on_toggle_character, checked=lambda item: self.character_enabled))
        items.append(pystray.MenuItem("Animar personagem", self._on_toggle_animation,
                                      checked=lambda item: self.animate,
                                      enabled=lambda item: self.character_enabled))
        items.append(pystray.MenuItem("Barrinhas no ícone", self._on_toggle_bars,
                                      checked=lambda item: self.show_bars))
        items.append(pystray.MenuItem("Sair", self._on_quit))
        return items

    def _lines(self) -> list[str]:
        snap = self.snapshot
        if snap is None:
            return ["Carregando…"]
        lines: list[str] = []
        for w in snap.windows:
            lines.append(
                f"{w.label}: {w.percentage:.0f}%  {text_bar(w.percentage)}  "
                f"(reseta em {time_until(w.resets_at)}, {local_time(w.resets_at)})"
            )
        if snap.extra_credits:
            lines.append(f"Créditos extras: {snap.extra_credits}")
        if snap.local:
            t5, td = snap.local.last_5h, snap.local.today
            lines.append(
                f"Tokens 5h: {human_tokens(t5.total)} "
                f"(in {human_tokens(t5.input_tokens)} / out {human_tokens(t5.output_tokens)}) · {t5.messages} msgs"
            )
            lines.append(f"Tokens hoje: {human_tokens(td.total)} · {td.messages} msgs")
        if snap.error:
            lines.append(f"⚠ {snap.error[:120]}")
        lines.append(f"Atualizado às {local_time(snap.fetched_at)}")
        return lines

    def _tooltip(self) -> str:
        snap = self.snapshot
        if snap is None:
            return "Claude Code Monitor"
        parts = [f"{w.label.split(' (')[0]} {w.percentage:.0f}%" for w in snap.windows[:2]]
        if not parts and snap.local:
            parts.append(f"5h: {human_tokens(snap.local.last_5h.total)} tokens")
        if not parts:
            parts.append("erro ao consultar")
        return ("Claude Code · " + " | ".join(parts))[:127]  # limite do Windows

    def _widget_rows(self) -> list[Row]:
        snap = self.snapshot
        session = snap.window("five_hour") if snap else None
        weekly = snap.window("seven_day") if snap else None
        return [
            Row("5h", session.percentage if session else None, session.resets_at if session else None),
            Row("7d", weekly.percentage if weekly else None, weekly.resets_at if weekly else None),
        ]

    # -------------------------------------------------------------- widget
    def _start_widget(self) -> None:
        if self.widget is not None or not self.widget_enabled:
            return
        try:
            from .taskbar_widget import TaskbarWidget
            self.widget = TaskbarWidget(
                style=self.widget_style,
                on_style=self._on_widget_style,
                on_refresh=self.refresh,
                on_hide=self._hide_widget,
                on_quit=lambda: self._on_quit(self.icon, None),
            )
            self.widget.start()
            self._push_widget()
        except Exception as exc:
            print(f"[aviso] widget da barra indisponível: {exc!r}")
            self.widget = None
        self._rebuild_icon()

    def _stop_widget(self) -> None:
        if self.widget is not None:
            widget, self.widget = self.widget, None
            widget.close()
            if not self._stop.is_set():
                self._rebuild_icon()  # personagem volta para a bandeja

    def _hide_widget(self) -> None:
        self.widget_enabled = False
        self._save_settings()
        # close() precisa rodar fora da thread do widget (ela está no menu dele)
        threading.Thread(target=self._stop_widget, daemon=True).start()
        self.icon.update_menu()

    def _on_widget_style(self, style: str) -> None:
        self.widget_style = style
        self._save_settings()
        self.icon.update_menu()

    def _style_action(self, key: str):
        def action(icon, item):
            self.widget_style = key
            if self.widget:
                self.widget.set_style(key)
            self._save_settings()
        return action

    def _on_toggle_widget(self, icon, item) -> None:
        self.widget_enabled = not self.widget_enabled
        if self.widget_enabled:
            self._start_widget()
        else:
            self._stop_widget()
        self._save_settings()

    # -------------------------------------------------------------- dados
    def refresh(self) -> None:
        if not self._lock.acquire(blocking=False):
            return  # já existe uma atualização em andamento
        try:
            self.snapshot = get_snapshot(self.include_local)
            session = self.snapshot.window("five_hour")
            weekly = self.snapshot.window("seven_day")
            if session or weekly:
                self._bars = [session.percentage if session else None,
                              weekly.percentage if weekly else None]
            else:
                self._bars = None
            peak = max((p for p in self._bars or [] if p is not None), default=None)
            self.mood = character.mood_for(peak)
            self._rebuild_icon()
            self._push_widget()
            self.icon.title = self._tooltip()
            self.icon.update_menu()
        finally:
            self._lock.release()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            self._stop.wait(self.interval)

    def _animate_loop(self) -> None:
        index = 0
        while not self._stop.is_set():
            frames = self._rendered
            if not self.animate or len(frames) < 2:
                self._stop.wait(0.5)
                continue
            index %= len(frames)
            image, duration = frames[index]
            self.icon.icon = image
            index += 1
            self._stop.wait(duration / 1000)

    def _promote_loop(self) -> None:
        # O Explorer cria a entrada do ícone no registro alguns segundos depois
        # que ele aparece; tenta algumas vezes até conseguir.
        for _ in range(10):
            if self._stop.wait(3) or promote_tray_icon():
                return

    # -------------------------------------------------------------- menu
    def _on_toggle_bars(self, icon, item) -> None:
        self.show_bars = not self.show_bars
        self._render()
        if not self.animate:
            self._show_static()
        self._save_settings()

    def _on_toggle_animation(self, icon, item) -> None:
        self.animate = not self.animate
        if not self.animate:
            self._show_static()
        self._push_widget()
        self._save_settings()

    def _on_toggle_character(self, icon, item) -> None:
        self.character_enabled = not self.character_enabled
        self._rebuild_icon()
        self._push_widget()
        self._save_settings()

    def _on_refresh(self, icon, item) -> None:
        threading.Thread(target=self.refresh, daemon=True).start()

    def _on_quit(self, icon, item) -> None:
        self._stop.set()
        threading.Thread(target=self._stop_widget, daemon=True).start()
        icon.stop()

    def _setup(self, icon) -> None:
        icon.visible = True
        self._start_widget()
        threading.Thread(target=self._loop, daemon=True).start()
        threading.Thread(target=self._promote_loop, daemon=True).start()
        threading.Thread(target=self._animate_loop, daemon=True).start()

    def run(self) -> None:
        self.icon.run(setup=self._setup)


def run(interval: int = 300, include_local: bool = True, animate: bool | None = None,
        show_bars: bool | None = None, widget: bool | None = None) -> int:
    """Parâmetros ``None`` usam as preferências salvas (settings.json)."""
    if sys.platform == "win32":
        from .taskbar_widget import enable_dpi_awareness
        enable_dpi_awareness()  # antes de criar qualquer janela
    prefs = settings.load()
    animate = prefs["animate"] if animate is None else animate
    animate = animate and not os.environ.get("CLAUDE_MONITOR_NO_ANIMATION")
    TrayApp(
        interval=interval,
        include_local=include_local,
        animate=animate,
        show_bars=prefs["icon_bars"] if show_bars is None else show_bars,
        widget=prefs["widget"] if widget is None else widget,
        widget_style=prefs["widget_style"],
        character_on=prefs["character"],
    ).run()
    return 0
