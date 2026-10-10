"""Resolução de caminhos multiplataforma (Windows / Linux / macOS).

Tudo usa ``pathlib`` + ``Path.home()``, que resolve corretamente
``C:\\Users\\<voce>`` no Windows e ``/home/<voce>`` no Linux.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

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


def user_config_dir() -> Path:
    """Pasta de configuração do app: ``%APPDATA%\\claude-monitor`` no Windows,
    ``$XDG_CONFIG_HOME/claude-monitor`` (ou ``~/.config/claude-monitor``) no Linux."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", "").strip()
        return (Path(base) if base else Path.home() / "AppData" / "Roaming") / "claude-monitor"
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    return (Path(xdg).expanduser() if xdg else Path.home() / ".config") / "claude-monitor"
