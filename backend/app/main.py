"""Ponto de entrada da API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.endpoints import health
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import NotFoundError, ProviderError, ProviderNotSupportedError
from app.core.logging import get_logger, setup_logging
from app.jobs.scheduler import create_scheduler
from app.providers.factory import get_provider

setup_logging(settings.log_level, json_output=settings.is_production)
logger = get_logger(__name__)

DESCRIPTION = """
API da plataforma MLBB Analytics.

**Origem dos dados** - o Mobile Legends nao possui API publica oficial para
este uso. Toda leitura passa por um `MLBBDataProvider`. Enquanto o provider
configurado for de demonstracao, as respostas de meta trazem `is_mock: true`
e os numeros **nao refletem o jogo real**.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    provider = get_provider()
    logger.info(
        "api iniciando",
        extra={
            "app_env": settings.app_env,
            "provider": provider.name,
            "provider_is_mock": provider.is_mock,
        },
    )
    if provider.is_mock:
        logger.warning(
            "provider de demonstracao ativo: os dados servidos sao ficticios",
            extra={"source": provider.source_description},
        )

    scheduler = create_scheduler()
    try:
        yield
    finally:
        if scheduler is not None:
            # wait=False: nao seguramos o shutdown por uma coleta em curso.
            scheduler.shutdown(wait=False)
        logger.info("api encerrando")


app = FastAPI(
    title=settings.project_name,
    description=DESCRIPTION,
    version=health.API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.include_router(health.router)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.exception_handler(NotFoundError)
async def handle_not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ProviderNotSupportedError)
async def handle_provider_unsupported(_: Request, exc: ProviderNotSupportedError) -> JSONResponse:
    # 501: a operacao existe no contrato, mas a fonte atual nao a implementa.
    return JSONResponse(status_code=501, content={"detail": str(exc)})


@app.exception_handler(ProviderError)
async def handle_provider_error(_: Request, exc: ProviderError) -> JSONResponse:
    logger.error("falha no provider", extra={"error": str(exc)})
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": settings.project_name, "docs": "/docs", "health": "/health"}
