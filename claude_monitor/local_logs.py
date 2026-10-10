"""Soma de tokens a partir dos logs locais do Claude Code.

Cada sessão vira um ``*.jsonl`` em ``~/.claude/projects/<projeto>/``. As linhas
``"type": "assistant"`` trazem ``message.usage``. O mesmo ``message.id`` aparece
várias vezes (streaming), então deduplicamos por ``message.id + requestId``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import paths
from .models import LocalUsage, TokenTotals


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _iter_files(max_age: timedelta) -> list[Path]:
    cutoff = (datetime.now(timezone.utc) - max_age).timestamp()
    files: list[Path] = []
    for root in paths.projects_dirs():
        for path in root.rglob("*.jsonl"):
            try:
                if path.stat().st_mtime >= cutoff:
                    files.append(path)
            except OSError:
                continue
    return files


def collect_local_usage(now: datetime | None = None) -> LocalUsage:
    now = now or datetime.now(timezone.utc)
    start_5h = now - timedelta(hours=5)
    start_7d = now - timedelta(days=7)
    start_today = now.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)

    # chave de dedupe -> (timestamp, usage, model); a última ocorrência vence
    entries: dict[str, tuple[datetime, dict, str]] = {}
    files = _iter_files(timedelta(days=7, hours=1))

    for path in files:
        try:
            handle = path.open("r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line in handle:
                if '"usage"' not in line:  # filtro barato antes do json.loads
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = row.get("message")
                if not isinstance(message, dict):
                    continue
                usage = message.get("usage")
                ts = _parse_ts(row.get("timestamp"))
                if not isinstance(usage, dict) or ts is None or ts < start_7d:
                    continue
                key = f"{message.get('id')}:{row.get('requestId')}"
                if key == "None:None":
                    key = f"{path}:{row.get('uuid')}"
                entries[key] = (ts, usage, message.get("model") or "desconhecido")

    result = LocalUsage(files_scanned=len(files))
    for ts, usage, model in entries.values():
        if model == "<synthetic>":
            continue
        result.last_7d.add(usage)
        if ts >= start_today:
            result.today.add(usage)
        if ts >= start_5h:
            result.last_5h.add(usage)
            result.by_model_5h.setdefault(model, TokenTotals()).add(usage)
    return result
