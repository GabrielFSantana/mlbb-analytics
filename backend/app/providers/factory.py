"""Selecao do provider ativo a partir da configuracao."""

from __future__ import annotations

from functools import cache

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.providers.base import MLBBDataProvider
from app.providers.mock import MockDataProvider

# Registre aqui novas implementacoes conforme forem aprovadas.
PROVIDERS: dict[str, type[MLBBDataProvider]] = {
    MockDataProvider.name: MockDataProvider,
}


@cache
def get_provider(name: str | None = None) -> MLBBDataProvider:
    """Instancia (memoizado) o provider configurado em `MLBB_PROVIDER`."""
    key = (name or settings.mlbb_provider).lower()
    try:
        provider_cls = PROVIDERS[key]
    except KeyError as exc:
        disponiveis = ", ".join(sorted(PROVIDERS))
        raise ProviderError(f"provider '{key}' desconhecido; disponiveis: {disponiveis}") from exc
    return provider_cls()
