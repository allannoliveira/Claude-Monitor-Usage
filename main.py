"""Atalho para rodar sem instalar: ``python main.py [tray|cli] [opções]``."""

import sys

from claude_monitor.app import main

if __name__ == "__main__":
    sys.exit(main())
