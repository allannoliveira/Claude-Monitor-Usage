"""Modo terminal com ``rich``."""

from __future__ import annotations

import json
import time

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from .formatting import human_tokens, level, local_time, time_until
from .models import Snapshot, TokenTotals
from .service import get_snapshot

COLORS = {"ok": "green", "warn": "yellow", "crit": "red"}


def _limits_table(snap: Snapshot) -> Table:
    table = Table(expand=True, show_edge=False, pad_edge=False)
    table.add_column("Limite", style="bold")
    table.add_column("Uso", ratio=2)
    table.add_column("%", justify="right")
    table.add_column("Reseta em", justify="right")
    table.add_column("Horário", justify="right", style="dim")
    for w in snap.windows:
        color = COLORS[level(w.percentage)]
        bar = ProgressBar(total=100, completed=min(w.percentage, 100), complete_style=color)
        table.add_row(
            w.label,
            bar,
            Text(f"{w.percentage:.0f}%", style=color),
            time_until(w.resets_at),
            local_time(w.resets_at),
        )
    return table


def _tokens_table(snap: Snapshot) -> Table:
    local = snap.local
    table = Table(expand=True, show_edge=False, pad_edge=False)
    table.add_column("Período", style="bold")
    for col in ("Entrada", "Saída", "Cache (criação)", "Cache (leitura)", "Total", "Msgs"):
        table.add_column(col, justify="right")

    def row(name: str, t: TokenTotals) -> None:
        table.add_row(
            name,
            human_tokens(t.input_tokens),
            human_tokens(t.output_tokens),
            human_tokens(t.cache_creation_tokens),
            human_tokens(t.cache_read_tokens),
            Text(human_tokens(t.total), style="bold cyan"),
            str(t.messages),
        )

    row("Últimas 5h", local.last_5h)
    row("Hoje", local.today)
    row("Últimos 7d", local.last_7d)
    for model, totals in sorted(local.by_model_5h.items(), key=lambda kv: -kv[1].total):
        row(f"  └ {model.removeprefix('claude-')}", totals)
    return table


def render(snap: Snapshot) -> Group:
    parts = []
    if snap.windows:
        subtitle = f"plano: {snap.subscription}" if snap.subscription else None
        parts.append(
            Panel(
                _limits_table(snap),
                title="[bold]Limites do Claude Code[/]",
                subtitle=subtitle,
                border_style="magenta",
            )
        )
    if snap.extra_credits:
        parts.append(Text(f"Créditos extras usados: {snap.extra_credits}", style="yellow"))
    if snap.local is not None:
        parts.append(
            Panel(
                _tokens_table(snap),
                title="[bold]Tokens (logs locais)[/]",
                subtitle=f"{snap.local.files_scanned} arquivos lidos",
                border_style="blue",
            )
        )
    if snap.error:
        parts.append(Panel(snap.error, title="Aviso", border_style="red"))
    parts.append(
        Text(
            f"Atualizado às {local_time(snap.fetched_at)}"
            + (f" · fonte: {snap.source}" if snap.source else ""),
            style="dim",
        )
    )
    return Group(*parts)


def snapshot_to_dict(snap: Snapshot) -> dict:
    def totals(t: TokenTotals) -> dict:
        return {**t.__dict__, "total": t.total}

    data = {
        "fetched_at": snap.fetched_at.isoformat(),
        "source": snap.source,
        "subscription": snap.subscription,
        "error": snap.error,
        "extra_credits": snap.extra_credits,
        "windows": [
            {
                "key": w.key,
                "label": w.label,
                "percentage": w.percentage,
                "resets_at": w.resets_at.isoformat() if w.resets_at else None,
            }
            for w in snap.windows
        ],
    }
    if snap.local:
        data["local"] = {
            "last_5h": totals(snap.local.last_5h),
            "today": totals(snap.local.today),
            "last_7d": totals(snap.local.last_7d),
            "by_model_5h": {m: totals(t) for m, t in snap.local.by_model_5h.items()},
        }
    return data


def run(watch: bool = False, interval: int = 60, as_json: bool = False,
        include_local: bool = True) -> int:
    if as_json:
        print(json.dumps(snapshot_to_dict(get_snapshot(include_local)), ensure_ascii=False, indent=2))
        return 0

    console = Console()
    if not watch:
        with console.status("Consultando uso…"):
            snap = get_snapshot(include_local)
        console.print(render(snap))
        return 0 if snap.windows or snap.local else 1

    with Live(console=console, refresh_per_second=1, screen=False) as live:
        live.update(Text("Consultando uso…"))
        try:
            while True:
                live.update(render(get_snapshot(include_local)))
                time.sleep(max(15, interval))
        except KeyboardInterrupt:
            pass
    return 0
