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

    # --- Fonte comunitaria (provider "rone_arena") --------------------
    mlbb_api_base_url: str = "https://arena.rone.dev"
    mlbb_api_timeout: float = 30.0
    # Janela agregada das estatisticas. A fonte aceita 1, 3, 7, 15 ou 30.
    # 7 dias equilibra reagir a mudanca de patch e nao oscilar com ruido.
    mlbb_stats_window_days: int = 7
    # Cache curto: evita repetir a mesma chamada dentro de uma sincronizacao
    # sem congelar o dado entre execucoes.
    mlbb_api_cache_seconds: float = 300.0

    # Builds sao buscadas sob demanda; este e o tempo que o resultado
    # gravado continua valendo antes de consultar a fonte de novo.
    builds_cache_hours: int = 24

    # Sinergia medida tambem e buscada sob demanda, um heroi por consulta.
    # Mesma logica das builds: a fonte remede junto com o patch, entao um
    # dia de validade e generoso e economiza a chamada mais cara.
    synergy_cache_hours: int = 24

    # --- Meta de estrelas do time -------------------------------------
    # Alvo padrao do acompanhamento. Pode ser sobrescrito por consulta.
    team_star_goal: int = 200

    # --- Coleta automatica (Fase 2) -----------------------------------
    sync_enabled: bool = True
    # Horas (UTC) em que a coleta roda. A fonte agrega por dia, entao duas
    # execucoes diarias ja cobrem atraso de publicacao sem martelar a API.
    sync_hours: str = "6,18"
    # Roda uma coleta no boot se o banco ainda nao tem dados do dia.
    sync_on_startup: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuracao (memoizada) do processo."""
    return Settings()


settings = get_settings()
