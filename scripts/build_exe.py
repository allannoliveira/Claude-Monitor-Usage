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


def make_ico() -> Path:
    """Gera o .ico do executável: boneco em assets/ se existir, senão o ícone genérico."""
    BUILD.mkdir(exist_ok=True)
    ico = BUILD / "icon.ico"
    frame = None
    for name in ("boneco.ico", "boneco.png", "boneco.gif"):
        src = ASSETS / name
        if src.is_file():
            with Image.open(src) as img:
                img.seek(0)
                frame = img.convert("RGBA")
            break
    if frame is None:
        sys.path.insert(0, str(ROOT))
        from claude_monitor.tray import fallback_icon
        frame = fallback_icon()
    side = max(frame.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(frame, ((side - frame.width) // 2, (side - frame.height) // 2), frame)
    canvas = canvas.resize((256, 256), Image.Resampling.NEAREST)
    canvas.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (256, 256)])
    return ico


def main() -> int:
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
        "--windowed", "--name", "claude-monitor", "--icon", str(make_ico()),
        "--hidden-import", "pystray._win32",
    ]
    if ASSETS.is_dir() and any(ASSETS.iterdir()):
        cmd += ["--add-data", f"{ASSETS}{sep}claude_monitor/assets"]
    cmd.append(str(ROOT / "main.py"))
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
