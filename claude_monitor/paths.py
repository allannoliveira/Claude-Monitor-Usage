"""Resolução de caminhos multiplataforma (Windows / Linux / macOS).

Tudo usa ``pathlib`` + ``Path.home()``, que resolve corretamente
``C:\\Users\\<voce>`` no Windows e ``/home/<voce>`` no Linux.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ICON_CANDIDATES = ("boneco.gif", "boneco.png", "boneco.ico")


def claude_config_dir() -> Path:
    """Diretório de configuração do Claude Code.

    Respeita ``CLAUDE_CONFIG_DIR`` (mesma regra do Claude Code e do projeto de
    referência); caso contrário usa ``~/.claude``.
    """
    env = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".claude"


def credentials_file() -> Path:
    """Arquivo com o token OAuth gravado pelo ``claude`` CLI."""
    return claude_config_dir() / ".credentials.json"


def projects_dirs() -> list[Path]:
    """Pastas onde o Claude Code grava os logs de sessão (``*.jsonl``).

    Versões recentes usam ``~/.claude/projects``; algumas instalações Linux
    usam ``~/.config/claude/projects`` (XDG). Retorna as que existirem.
    """
    candidates = [claude_config_dir() / "projects"]
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    xdg_base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    candidates.append(xdg_base / "claude" / "projects")

    seen: set[Path] = set()
    result: list[Path] = []
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved not in seen and path.is_dir():
            seen.add(resolved)
            result.append(path)
    return result


def app_root() -> Path:
    """Raiz do projeto (ou pasta temporária do PyInstaller, se empacotado)."""
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        return Path(frozen_base)
    return Path(__file__).resolve().parent.parent


def user_config_dir() -> Path:
    """Pasta de configuração do app: ``%APPDATA%\\claude-monitor`` no Windows,
    ``$XDG_CONFIG_HOME/claude-monitor`` (ou ``~/.config/claude-monitor``) no Linux."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", "").strip()
        return (Path(base) if base else Path.home() / "AppData" / "Roaming") / "claude-monitor"
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    return (Path(xdg).expanduser() if xdg else Path.home() / ".config") / "claude-monitor"


def find_icon_file() -> Path | None:
    """Procura ``boneco.gif`` / ``boneco.png`` / ``boneco.ico``, nesta ordem:

    1. ``CLAUDE_MONITOR_ICON`` (caminho explícito);
    2. pasta de configuração do usuário (vale para a versão instalada);
    3. raiz do projeto / pasta atual (rodando direto do código-fonte);
    4. ``claude_monitor/assets`` (cópia embutida no pacote na instalação).
    """
    override = os.environ.get("CLAUDE_MONITOR_ICON", "").strip()
    if override:
        path = Path(override).expanduser()
        return path if path.is_file() else None

    package_assets = Path(__file__).resolve().parent / "assets"
    for root in (user_config_dir(), app_root(), Path.cwd(), package_assets):
        for name in ICON_CANDIDATES:
            path = root / name
            if path.is_file():
                return path
    return None
