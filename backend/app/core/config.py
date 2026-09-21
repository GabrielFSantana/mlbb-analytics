"""Configuracao centralizada do backend, carregada de variaveis de ambiente."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracao da API.

    Valores vem do ambiente ou do arquivo `.env` na raiz do repositorio.
    Campos desconhecidos sao ignorados de proposito: o mesmo `.env` e
    compartilhado com o bot, que tem chaves que a API nao usa.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    project_name: str = "MLBB Analytics API"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://mlbb:mlbb@localhost:5432/mlbb"
    db_echo: bool = False
    # Segundos ate desistir de abrir a conexao TCP com o Postgres.
    db_connect_timeout: int = 5

    # Fonte de dados MLBB. Ver app/providers/factory.py.
    mlbb_provider: str = "mock"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuracao (memoizada) do processo."""
    return Settings()


settings = get_settings()
