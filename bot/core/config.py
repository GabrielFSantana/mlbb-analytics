"""Configuracao do bot, carregada do mesmo `.env` do backend."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Configuracao do processo do bot.

    O bot nao acessa o banco: tudo passa pela API, que e a unica dona do
    schema. Por isso `DATABASE_URL` nao aparece aqui.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_token: str = Field(default="", description="Token do bot no Discord.")
    discord_guild_id: int | None = Field(
        default=None,
        description="Se definido, os slash commands sao sincronizados so nesse servidor "
        "(propagacao imediata, em vez de ate 1h do sync global).",
    )
    discord_meta_channel_id: int | None = Field(
        default=None, description="Canal de atualizacoes automaticas de meta (Fase 2)."
    )

    backend_api_url: str = "http://localhost:8000"
    backend_timeout_seconds: float = 10.0

    log_level: str = "INFO"
    app_env: str = "development"

    # --- Publicacao automatica de meta (Fase 2) -----------------------
    meta_updates_enabled: bool = True
    # De quanto em quanto tempo o bot pergunta a API se ha novidade.
    meta_poll_minutes: int = 30

    @field_validator("discord_guild_id", "discord_meta_channel_id", mode="before")
    @classmethod
    def _empty_string_as_none(cls, value: object) -> object:
        """Trata `DISCORD_GUILD_ID=` (vazio no .env) como ausente.

        Sem isso o boot quebra com erro de parse de inteiro, que e
        exatamente o estado em que o `.env.example` chega ao desenvolvedor.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def api_v1(self) -> str:
        return f"{self.backend_api_url.rstrip('/')}/api/v1"


@lru_cache
def get_settings() -> BotSettings:
    return BotSettings()


settings = get_settings()
