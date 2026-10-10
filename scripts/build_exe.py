"""Gera ``dist/claude-monitor.exe`` (Windows, sem console) com PyInstaller.

Uso: ``pip install pyinstaller`` e depois ``python scripts/build_exe.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"


def make_ico() -> Path:
    """Gera o .ico do executável a partir do personagem (humor "feliz")."""
    sys.path.insert(0, str(ROOT))
    from claude_monitor import character

    BUILD.mkdir(exist_ok=True)
    ico = BUILD / "icon.ico"
    frame = character._draw("feliz", 0).crop((0, 0, character.GRID_H, character.GRID_H))
    frame.resize((256, 256), Image.Resampling.NEAREST).save(
        ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (256, 256)])
    return ico


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
        "--windowed", "--name", "claude-monitor", "--icon", str(make_ico()),
        "--hidden-import", "pystray._win32",
    ]
    cmd.append(str(ROOT / "main.py"))
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
