"""Gera ``dist/claude-monitor.exe`` (Windows, sem console) com PyInstaller.

Uso: ``pip install pyinstaller`` e depois ``python scripts/build_exe.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "claude_monitor" / "assets"
BUILD = ROOT / "build"


def make_ico() -> Path | None:
    """Converte o primeiro quadro do boneco em .ico para o executável."""
    for name in ("boneco.ico", "boneco.png", "boneco.gif"):
        src = ASSETS / name
        if src.is_file():
            BUILD.mkdir(exist_ok=True)
            ico = BUILD / "icon.ico"
            with Image.open(src) as img:
                img.seek(0)
                frame = img.convert("RGBA")
            side = max(frame.size)
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.paste(frame, ((side - frame.width) // 2, (side - frame.height) // 2), frame)
            canvas = canvas.resize((256, 256), Image.Resampling.NEAREST)
            canvas.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (256, 256)])
            return ico
    return None


def main() -> int:
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
        "--windowed", "--name", "claude-monitor",
        "--add-data", f"{ASSETS}{sep}claude_monitor/assets",
        "--hidden-import", "pystray._win32",
        str(ROOT / "main.py"),
    ]
    ico = make_ico()
    if ico:
        cmd[cmd.index("--name"):cmd.index("--name")] = ["--icon", str(ico)]
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
