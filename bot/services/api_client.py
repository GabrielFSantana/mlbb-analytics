"""Cliente HTTP do backend.

O bot nunca fala com o banco: a API e a unica fonte. Todas as falhas de rede
viram `BackendUnavailableError`, para que os comandos possam responder algo
util em vez de estourar um traceback no Discord.
"""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from urllib.parse import quote

import httpx

from bot.core.config import settings
from bot.core.logging import get_logger
from bot.services.schemas import (
    HeroBuilds,
    HeroCounters,
    HeroDetail,
    MetaResponse,
    MetaUpdate,
    Patch,
)

logger = get_logger(__name__)


class BackendError(Exception):
    """Erro ao falar com a API."""


class BackendUnavailableError(BackendError):
    """A API nao respondeu (timeout, conexao recusada, 5xx)."""


class MLBBApiClient:
    """Wrapper fino sobre httpx.AsyncClient."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self._base_url = (base_url or settings.backend_api_url).rstrip("/")
        self._timeout = timeout or settings.backend_timeout_seconds
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> MLBBApiClient:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, **params: object) -> object:
        if self._client is None:
            await self.start()
        assert self._client is not None
        try:
            response = await self._client.get(path, params=params or None)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "backend respondeu erro",
                extra={"path": path, "status": exc.response.status_code},
            )
            if exc.response.status_code >= 500:
                raise BackendUnavailableError(f"API retornou {exc.response.status_code}") from exc
            raise BackendError(f"API retornou {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            logger.error("backend inacessivel", extra={"path": path, "error": str(exc)})
            raise BackendUnavailableError(str(exc)) from exc
        return response.json()

    async def get_meta(self, lane: str | None = None, *, limit: int | None = None) -> MetaResponse:
        path = f"/api/v1/meta/{lane}" if lane else "/api/v1/meta"
        params: dict[str, object] = {}
        if limit is not None:
            params["limit"] = limit
        payload = await self._get(path, **params)
        return MetaResponse.model_validate(payload)

    async def get_hero(self, termo: str) -> HeroDetail:
        """Detalhe de um heroi por nome ou slug."""
        payload = await self._get(f"/api/v1/heroes/by-name/{quote(termo)}")
        return HeroDetail.model_validate(payload)

    async def get_hero_counters(self, termo: str) -> HeroCounters:
        """Counters e sinergias de um heroi."""
        payload = await self._get(f"/api/v1/heroes/by-name/{quote(termo)}/counters")
        return HeroCounters.model_validate(payload)

    async def get_hero_builds(self, termo: str, lane: str | None = None) -> HeroBuilds:
        """Builds recomendadas de um heroi."""
        params: dict[str, object] = {}
        if lane:
            params["lane"] = lane
        payload = await self._get(f"/api/v1/builds/{quote(termo)}", **params)
        return HeroBuilds.model_validate(payload)

    async def get_current_patch(self) -> Patch | None:
        payload = await self._get("/api/v1/patches/current")
        if payload is None:
            return None
        return Patch.model_validate(payload)

    async def get_pending_update(self) -> MetaUpdate | None:
        """Atualizacao de meta ainda nao publicada, se houver."""
        payload = await self._get("/api/v1/meta/updates/pending")
        if payload is None:
            return None
        return MetaUpdate.model_validate(payload)

    async def ack_update(self, collected_at: datetime, source: str) -> None:
        """Confirma a publicacao, para a mesma coleta nao sair duas vezes."""
        if self._client is None:
            await self.start()
        assert self._client is not None
        try:
            response = await self._client.post(
                "/api/v1/meta/updates/ack",
                json={"collected_at": collected_at.isoformat(), "source": source},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("falha ao confirmar publicacao", extra={"error": str(exc)})
            raise BackendUnavailableError(str(exc)) from exc

    async def health(self) -> dict[str, object]:
        payload = await self._get("/health")
        return dict(payload)  # type: ignore[arg-type]
