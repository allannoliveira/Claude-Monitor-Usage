"""Fachada única usada pelas interfaces (tray e terminal)."""

from __future__ import annotations

from datetime import datetime, timezone

from .local_logs import collect_local_usage
from .models import Snapshot
from .usage_api import UsageError, cli_refresh_enabled, fetch_api_usage


def get_snapshot(include_local: bool = True, allow_header_probe: bool = True) -> Snapshot:
    snap = Snapshot(fetched_at=datetime.now(timezone.utc))

    try:
        api = fetch_api_usage(
            allow_cli_refresh=cli_refresh_enabled(),
            allow_header_probe=allow_header_probe,
        )
        snap.windows = api.windows
        snap.source = api.source
        snap.extra_credits = api.extra_credits
        snap.subscription = api.subscription
    except UsageError as exc:
        snap.error = str(exc)
    except Exception as exc:  # nunca derrubar a UI por um erro inesperado
        snap.error = f"Erro inesperado: {exc!r}"

    if include_local:
        try:
            snap.local = collect_local_usage()
        except Exception as exc:
            snap.error = (snap.error + " | " if snap.error else "") + f"Logs locais: {exc!r}"

    return snap
