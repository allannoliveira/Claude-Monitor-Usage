"""Preferências do usuário (estilo do widget etc.), salvas em JSON na pasta
de configuração do app (``%APPDATA%\\claude-monitor`` / ``~/.config/claude-monitor``)."""

from __future__ import annotations

import json

from . import paths

DEFAULTS = {
    "widget": True,                 # widget com barrinhas na barra de tarefas (Windows)
    "widget_style": "segmentos",    # segmentos | barra | compacto
    "icon_bars": False,             # barrinhas dentro do ícone da bandeja
    "animate": True,                # animar boneco.gif
}


def _file():
    return paths.user_config_dir() / "settings.json"


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        stored = json.loads(_file().read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            data.update({k: v for k, v in stored.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return data


def save(data: dict) -> None:
    try:
        path = _file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass  # preferências são opcionais; nunca derrubar o app por isso
