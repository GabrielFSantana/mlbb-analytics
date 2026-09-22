"""Comando /meta."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.logging import get_logger
from bot.services.api_client import BackendError, BackendUnavailableError, MLBBApiClient
from bot.ui.embeds import build_error_embed, build_meta_embed

logger = get_logger(__name__)

RANK_CHOICES = [
    app_commands.Choice(name="Todos os ranques", value="all"),
    app_commands.Choice(name="Epico", value="epic"),
    app_commands.Choice(name="Lenda", value="legend"),
    app_commands.Choice(name="Mitico", value="mythic"),
    app_commands.Choice(name="Honra", value="honor"),
    app_commands.Choice(name="Gloria", value="glory"),
]

LANE_CHOICES = [
    app_commands.Choice(name="Jungle", value="jungle"),
    app_commands.Choice(name="Gold", value="gold"),
    app_commands.Choice(name="Mid", value="mid"),
    app_commands.Choice(name="Exp", value="exp"),
    app_commands.Choice(name="Roam", value="roam"),
]


class MetaCog(commands.Cog):
    """Tier list do meta."""

    def __init__(self, bot: commands.Bot, api: MLBBApiClient) -> None:
        self.bot = bot
        self.api = api

    @app_commands.command(name="meta", description="Mostra o meta atual do MLBB")
    @app_commands.describe(
        lane="Lane especifica. Sem valor, mostra todas.",
        ranque="Faixa de ranque. Sem valor, usa o agregado geral.",
    )
    @app_commands.choices(lane=LANE_CHOICES, ranque=RANK_CHOICES)
    async def meta(
        self,
        interaction: discord.Interaction,
        lane: app_commands.Choice[str] | None = None,
        ranque: app_commands.Choice[str] | None = None,
    ) -> None:
        # A chamada ao backend pode passar dos 3s do limite do Discord.
        await interaction.response.defer()
        lane_value = lane.value if lane else None
        rank_value = ranque.value if ranque else None

        try:
            data = await self.api.get_meta(lane_value, rank=rank_value)
        except BackendUnavailableError:
            await interaction.followup.send(
                embed=build_error_embed(
                    "Backend indisponivel",
                    "Nao consegui falar com a API do MLBB Analytics. Tente de novo em instantes.",
                )
            )
            return
        except BackendError as exc:
            logger.error(
                "falha ao buscar meta",
                extra={"lane": lane_value, "rank": rank_value, "error": str(exc)},
            )
            await interaction.followup.send(
                embed=build_error_embed("Erro ao buscar o meta", str(exc))
            )
            return

        await interaction.followup.send(embed=build_meta_embed(data, lane=lane_value))


async def setup(bot: commands.Bot) -> None:
    """Entrypoint da extensao (chamado por `bot.load_extension`)."""
    api: MLBBApiClient = bot.api  # type: ignore[attr-defined]
    await bot.add_cog(MetaCog(bot, api))
