"""Consulta dos limites oficiais da conta, portando a lógica de
CodeZeno/Claude-Code-Usage-Monitor (``src/poller/claude.rs``):

1. Lê o token OAuth de ``~/.claude/.credentials.json`` (chave ``claudeAiOauth``).
2. Se o token expirou, roda ``claude -p .`` para o CLI renová-lo e relê o arquivo.
3. Chama ``GET https://api.anthropic.com/api/oauth/usage`` (janelas
   ``five_hour``, ``seven_day``, ``seven_day_opus`` etc.).
4. Se esse endpoint não estiver disponível para a conta, faz uma chamada mínima
   (1 token, Haiku) à Messages API e lê os headers
   ``anthropic-ratelimit-unified-*``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from . import paths
from .models import UsageWindow

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
MESSAGES_URL = "https://api.anthropic.com/v1/messages"
OAUTH_BETA = "oauth-2025-04-20"
FALLBACK_MODEL = "claude-haiku-4-5"
USER_AGENT = "claude-usage-tray/1.0"
TIMEOUT = 20

# Rótulos amigáveis para buckets conhecidos; desconhecidos viram "Seven Day X".
KNOWN_LABELS = {
    "five_hour": "Sessão (5h)",
    "seven_day": "Semanal (todos os modelos)",
    "seven_day_opus": "Semanal (Opus)",
    "seven_day_sonnet": "Semanal (Sonnet)",
    "seven_day_oauth_apps": "Semanal (apps OAuth)",
}
ORDER = list(KNOWN_LABELS)


class UsageError(Exception):
    """Erro com mensagem já pronta para o usuário."""


@dataclass
class Credentials:
    access_token: str
    expires_at_ms: int | None
    subscription: str | None

    @property
    def expired(self) -> bool:
        return self.expires_at_ms is not None and time.time() * 1000 >= self.expires_at_ms


@dataclass
class ApiUsage:
    windows: list[UsageWindow]
    source: str
    extra_credits: str | None = None
    subscription: str | None = None


# ---------------------------------------------------------------- credenciais
def read_credentials() -> Credentials:
    path = paths.credentials_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise UsageError(
            f"Credenciais não encontradas em {path}. Rode `claude` e faça login."
        ) from None
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"Não foi possível ler {path}: {exc}") from None

    oauth = data.get("claudeAiOauth") or {}
    token = oauth.get("accessToken")
    if not token:
        raise UsageError(f"{path} não contém um token OAuth. Faça login no `claude`.")
    expires = oauth.get("expiresAt")
    return Credentials(
        access_token=token,
        expires_at_ms=int(expires) if isinstance(expires, (int, float)) else None,
        subscription=oauth.get("subscriptionType"),
    )


def _refresh_via_cli() -> None:
    """Pede ao Claude Code para renovar o token (mesma estratégia do original)."""
    exe = shutil.which("claude") or shutil.which("claude.cmd")
    if not exe:
        return
    kwargs: dict = {"capture_output": True, "timeout": 90}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        subprocess.run([exe, "-p", "."], check=False, **kwargs)
    except (OSError, subprocess.SubprocessError):
        pass


def get_valid_credentials(allow_cli_refresh: bool = True) -> Credentials:
    creds = read_credentials()
    if creds.expired and allow_cli_refresh:
        _refresh_via_cli()
        creds = read_credentials()
    if creds.expired:
        raise UsageError("Token OAuth expirado. Abra o `claude` para renovar o login.")
    return creds


# ---------------------------------------------------------------- HTTP
def _request(url: str, token: str, body: dict | None = None):
    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-beta": OAUTH_BETA,
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        headers["anthropic-version"] = "2023-06-01"
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def _parse_iso(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _from_unix(value) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _label(key: str) -> str:
    return KNOWN_LABELS.get(key, key.replace("_", " ").title())


def parse_usage_body(body: dict) -> tuple[list[UsageWindow], str | None]:
    """Converte a resposta de ``/api/oauth/usage`` em janelas.

    Aceita o formato clássico (chaves ``five_hour``/``seven_day``...) e o
    formato novo com array ``limits`` (``kind``, ``percent``, ``scope``).
    """
    windows: dict[str, UsageWindow] = {}

    for key, value in body.items():
        if isinstance(value, dict) and isinstance(value.get("utilization"), (int, float)):
            windows[key] = UsageWindow(
                key=key,
                label=_label(key),
                percentage=float(value["utilization"]),
                resets_at=_parse_iso(value.get("resets_at")),
            )

    for entry in body.get("limits") or []:
        if not isinstance(entry, dict):
            continue
        pct = entry.get("percent", entry.get("utilization"))
        kind = str(entry.get("kind") or "").strip()
        if not kind or not isinstance(pct, (int, float)) or pct < 0:
            continue
        scope = entry.get("scope") or {}
        model = (scope.get("model") or {}) if isinstance(scope, dict) else {}
        model_name = model.get("display_name") or model.get("id")
        legacy_key = {"session": "five_hour", "weekly_all": "seven_day"}.get(kind)
        key = legacy_key if (legacy_key and not scope) else f"{kind}_{model_name or 'scoped'}"
        if key in windows:
            continue
        label = _label(key) if legacy_key and not scope else (
            f"{kind.replace('_', ' ').title()} ({model_name})" if model_name else _label(kind)
        )
        windows[key] = UsageWindow(key, label, float(pct), _parse_iso(entry.get("resets_at")))

    ordered = sorted(
        windows.values(),
        key=lambda w: (ORDER.index(w.key) if w.key in ORDER else len(ORDER), w.key),
    )

    credits = None
    spend = body.get("spend") or body.get("extra_usage")
    if isinstance(spend, dict) and (spend.get("enabled") or spend.get("is_enabled")):
        used, limit = spend.get("used"), spend.get("limit")
        if isinstance(used, dict) and isinstance(limit, dict):
            def major(a):
                return a.get("amount_minor", 0) / 10 ** int(a.get("exponent", 0))
            credits = f"{major(used):.2f} / {major(limit):.2f}"

    return ordered, credits


def _fetch_usage_endpoint(token: str) -> ApiUsage | None:
    try:
        with _request(USAGE_URL, token) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise UsageError("Credenciais rejeitadas (401/403). Faça login novamente no `claude`.")
        if exc.code == 429 or exc.code >= 500:
            raise UsageError(f"API de uso indisponível no momento (HTTP {exc.code}).")
        return None  # 404 etc.: conta sem suporte -> fallback
    except (urllib.error.URLError, TimeoutError) as exc:
        raise UsageError(f"Falha de rede: {getattr(exc, 'reason', exc)}") from None
    except json.JSONDecodeError:
        return None

    windows, credits = parse_usage_body(body)
    if not windows:
        return None
    return ApiUsage(windows=windows, source="usage-api", extra_credits=credits)


def _fetch_via_headers(token: str) -> ApiUsage:
    body = {"model": FALLBACK_MODEL, "max_tokens": 1, "messages": [{"role": "user", "content": "."}]}
    try:
        resp = _request(MESSAGES_URL, token, body)
        headers, status = resp.headers, resp.status
        resp.close()
    except urllib.error.HTTPError as exc:  # 429 ainda traz os headers
        headers, status = exc.headers, exc.code
    except (urllib.error.URLError, TimeoutError) as exc:
        raise UsageError(f"Falha de rede: {getattr(exc, 'reason', exc)}") from None

    if status in (401, 403):
        raise UsageError("Credenciais rejeitadas (401/403). Faça login novamente no `claude`.")

    prefix = "anthropic-ratelimit-unified-"
    if not any(h.lower().startswith(prefix) for h in headers.keys()):
        raise UsageError(f"Não foi possível obter os limites (HTTP {status}).")

    def f(name):
        try:
            return float(headers.get(prefix + name))
        except (TypeError, ValueError):
            return None

    windows = []
    claim = headers.get(prefix + "representative-claim")
    rejected = headers.get(prefix + "status") == "rejected"
    for key, short in (("five_hour", "5h"), ("seven_day", "7d")):
        util = f(f"{short}-utilization")
        reset = _from_unix(headers.get(prefix + f"{short}-reset"))
        if util is None and reset is None and claim != key:
            continue
        pct = (util or 0.0) * 100
        if rejected and claim == key and pct == 0:
            pct = 100.0
        windows.append(UsageWindow(key, _label(key), pct, reset))
    return ApiUsage(windows=windows, source="rate-limit-headers")


def fetch_api_usage(allow_cli_refresh: bool = True, allow_header_probe: bool = True) -> ApiUsage:
    creds = get_valid_credentials(allow_cli_refresh)
    usage = _fetch_usage_endpoint(creds.access_token)
    if usage is None:
        if not allow_header_probe:
            raise UsageError("Endpoint de uso indisponível para esta conta.")
        usage = _fetch_via_headers(creds.access_token)
    usage.subscription = creds.subscription
    return usage


def cli_refresh_enabled() -> bool:
    return os.environ.get("CLAUDE_MONITOR_NO_CLI_REFRESH", "") == ""
