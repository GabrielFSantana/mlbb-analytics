"""Healthcheck.

Fica fora do prefixo versionado de proposito: orquestradores (docker
compose, k8s) nao devem depender da versao da API para saber se o processo
esta vivo.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import settings
from app.core.logging import get_logger
from app.providers.factory import get_provider
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])
logger = get_logger(__name__)

API_VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse, summary="Estado da aplicacao")
def health(db: DbSession) -> HealthResponse:
    """Retorna 200 mesmo com o banco fora do ar.

    O campo `database` e quem diz se a dependencia respondeu; assim o
    healthcheck distingue "processo morto" de "banco indisponivel".
    """
    database = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - depende de falha de infra
        logger.warning("healthcheck: banco indisponivel", extra={"error": str(exc)})
        database = "unavailable"

    provider = get_provider()
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        app_env=settings.app_env,
        version=API_VERSION,
        database=database,
        provider=provider.name,
        provider_is_mock=provider.is_mock,
        checked_at=datetime.now(UTC),
    )
