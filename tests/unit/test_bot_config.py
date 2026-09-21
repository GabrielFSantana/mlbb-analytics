"""Testes da configuracao do bot."""

from __future__ import annotations

from bot.core.config import BotSettings


def test_ids_opcionais_vazios_no_env_nao_quebram_o_boot():
    """Regressao: `DISCORD_GUILD_ID=` vazio, como vem no .env.example."""
    configurado = BotSettings(
        _env_file=None,
        discord_guild_id="",  # type: ignore[arg-type]
        discord_meta_channel_id="",  # type: ignore[arg-type]
    )
    assert configurado.discord_guild_id is None
    assert configurado.discord_meta_channel_id is None


def test_api_v1_monta_a_url_versionada():
    configurado = BotSettings(_env_file=None, backend_api_url="http://backend:8000/")
    assert configurado.api_v1 == "http://backend:8000/api/v1"
