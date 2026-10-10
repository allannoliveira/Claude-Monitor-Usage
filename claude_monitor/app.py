"""Interface de linha de comando: ``claude-monitor [tray|cli] [opções]``."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="claude-monitor",
        description="Monitor de uso e limites do Claude Code (bandeja do sistema ou terminal).",
    )
    parser.add_argument(
        "mode", nargs="?", choices=("tray", "cli"), default="tray",
        help="tray = ícone na barra de tarefas (padrão); cli = exibe no terminal",
    )
    parser.add_argument("-w", "--watch", action="store_true", help="(cli) atualiza continuamente")
    parser.add_argument(
        "-i", "--interval", type=int, default=None,
        help="segundos entre atualizações (padrão: 300 no tray, 60 no --watch)",
    )
    parser.add_argument("--json", action="store_true", help="(cli) imprime o resultado em JSON")
    parser.add_argument("--no-local", action="store_true", help="não ler os logs locais (.jsonl)")
    parser.add_argument("--no-anim", action="store_true", help="(tray) não animar o ícone .gif")
    parser.add_argument("--no-bars", action="store_true", help="(tray) não desenhar as barrinhas no ícone")
    parser.add_argument("--no-widget", action="store_true", help="(tray) não mostrar o widget na barra de tarefas")
    args = parser.parse_args(argv)

    # Garante acentos e caracteres de barra no console do Windows.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    if args.mode == "cli":
        from . import cli
        return cli.run(
            watch=args.watch,
            interval=args.interval or 60,
            as_json=args.json,
            include_local=not args.no_local,
        )

    try:
        from . import tray
    except Exception as exc:  # backend gráfico ausente (ex.: Linux sem AppIndicator)
        print(f"Não foi possível iniciar o modo tray: {exc}\nUse: claude-monitor cli", file=sys.stderr)
        return 2
    return tray.run(interval=args.interval or 300, include_local=not args.no_local,
                    animate=False if args.no_anim else None,
                    show_bars=False if args.no_bars else None,
                    widget=False if args.no_widget else None)


def main_tray() -> int:
    """Entrada ``claude-monitor-tray`` (gui-script: sem janela de console no Windows)."""
    return main(["tray", *sys.argv[1:]])
