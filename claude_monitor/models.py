"""Estruturas de dados compartilhadas entre a lógica e as interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class UsageWindow:
    """Uma janela de limite (ex.: sessão de 5h, semana)."""

    key: str
    label: str
    percentage: float  # 0-100
    resets_at: datetime | None = None


@dataclass
class TokenTotals:
    """Tokens somados a partir dos logs locais do Claude Code."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    messages: int = 0

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
        )

    def add(self, usage: dict) -> None:
        self.input_tokens += int(usage.get("input_tokens") or 0)
        self.output_tokens += int(usage.get("output_tokens") or 0)
        self.cache_creation_tokens += int(usage.get("cache_creation_input_tokens") or 0)
        self.cache_read_tokens += int(usage.get("cache_read_input_tokens") or 0)
        self.messages += 1


@dataclass
class LocalUsage:
    """Consumo calculado localmente (não depende de rede)."""

    last_5h: TokenTotals = field(default_factory=TokenTotals)
    today: TokenTotals = field(default_factory=TokenTotals)
    last_7d: TokenTotals = field(default_factory=TokenTotals)
    by_model_5h: dict[str, TokenTotals] = field(default_factory=dict)
    files_scanned: int = 0


@dataclass
class Snapshot:
    """Resultado completo de uma atualização."""

    fetched_at: datetime
    windows: list[UsageWindow] = field(default_factory=list)
    source: str = ""  # "usage-api", "rate-limit-headers" ou ""
    subscription: str | None = None
    extra_credits: str | None = None
    local: LocalUsage | None = None
    error: str | None = None

    def window(self, key: str) -> UsageWindow | None:
        return next((w for w in self.windows if w.key == key), None)
