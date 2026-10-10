"""Formatação de números, tempos e barras (sem dependência de UI)."""

from __future__ import annotations

from datetime import datetime, timezone


def human_tokens(value: int) -> str:
    for limit, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "k")):
        if value >= limit:
            return f"{value / limit:.1f}{suffix}"
    return str(value)


def time_until(when: datetime | None, now: datetime | None = None) -> str:
    if when is None:
        return "—"
    now = now or datetime.now(timezone.utc)
    seconds = int((when - now).total_seconds())
    if seconds <= 0:
        return "agora"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes:02d}min"
    return f"{minutes}min"


def compact_until(when: datetime | None, now: datetime | None = None) -> str:
    """Versão curta para o widget: ``35m``, ``2h``, ``4d``."""
    if when is None:
        return "—"
    now = now or datetime.now(timezone.utc)
    seconds = int((when - now).total_seconds())
    if seconds <= 0:
        return "0m"
    if seconds < 3600:
        return f"{max(1, seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def local_time(when: datetime | None) -> str:
    if when is None:
        return "—"
    local = when.astimezone()
    today = datetime.now().astimezone().date()
    fmt = "%H:%M" if local.date() == today else "%d/%m %H:%M"
    return local.strftime(fmt)


def text_bar(percentage: float, width: int = 10) -> str:
    filled = max(0, min(width, round(percentage / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def level(percentage: float) -> str:
    """'ok', 'warn' ou 'crit' — usado para cores no terminal e no ícone."""
    if percentage >= 90:
        return "crit"
    if percentage >= 70:
        return "warn"
    return "ok"
