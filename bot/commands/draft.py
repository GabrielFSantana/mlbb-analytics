"""Comando /draft: o que pegar contra o que o inimigo ja escolheu."""

from __future__ import annotations

import io

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.logging import get_logger
from bot.services.api_client import BackendError, BackendUnavailableError, MLBBApiClient
from bot.ui.cards import render_draft_card
from bot.ui.embeds import build_draft_embed, build_error_embed

logger = get_logger(__name__)

FORMAT_CHOICES = [
    app_commands.Choice(name="Imagem", value="imagem"),
    app_commands.Choice(name="Texto", value="texto"),
]

LANE_CHOICES = [
    app_commands.Choice(name="Jungle", value="jungle"),
    app_commands.Choice(name="Gold", value="gold"),
    app_commands.Choice(name="Mid", value="mid"),
    app_commands.Choice(name="Exp", value="exp"),
    app_commands.Choice(name="Roam", value="roam"),
]

RANK_CHOICES = [
    app_commands.Choice(name="Todos os ranques", value="all"),
    app_commands.Choice(name="Epico", value="epic"),
    app_commands.Choice(name="Lenda", value="legend"),
    app_commands.Choice(name="Mitico", value="mythic"),
    app_commands.Choice(name="Honra", value="honor"),
    app_commands.Choice(name="Gloria", value="glory"),
]

#: Uma partida tem cinco de cada lado; mais que isso e engano de digitacao.
MAX_HEROIS_POR_TIME = 5


def separar_nomes(texto: str | None) -> list[str]:
    """Quebra "Leomord, Kagura" na lista de nomes."""
    if not texto:
        return []
    return [parte.strip() for parte in texto.split(",") if parte.strip()][:MAX_HEROIS_POR_TIME]


class DraftCog(commands.Cog):
    """Assistente de escolha no draft."""

    def __init__(self, bot: commands.Bot, api: MLBBApiClient) -> None:
        self.bot = bot
        self.api = api

    @app_commands.command(
        name="draft",
        description="Sugere o que pegar contra os herois que o inimigo ja escolheu",
    )
    @app_commands.describe(
        inimigos="Herois do time inimigo, separados por virgula",
        aliados="Herois do seu time, separados por virgula (opcional)",
        lane="Lane para a qual voce vai pegar",
        ranque="Faixa de ranque. Sem valor, usa o agregado geral.",
        formato="Imagem (padrao) ou texto.",
    )
    @app_commands.choices(lane=LANE_CHOICES, ranque=RANK_CHOICES, formato=FORMAT_CHOICES)
    async def draft(
        self,
        interaction: discord.Interaction,
        inimigos: str,
        aliados: str | None = None,
        lane: app_commands.Choice[str] | None = None,
        ranque: app_commands.Choice[str] | None = None,
        formato: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer()

        lista_inimigos = separar_nomes(inimigos)
        if not lista_inimigos:
            await interaction.followup.send(
                embed=build_error_embed(
                    "Informe ao menos um heroi",
                    "Use virgula para separar, por exemplo: `Leomord, Kagura`.",
                )
            )
            return

        try:
            dados = await self.api.get_draft(
                lista_inimigos,
                separar_nomes(aliados),
                lane.value if lane else None,
                ranque.value if ranque else None,
            )
        except BackendUnavailableError:
            await interaction.followup.send(
                embed=build_error_embed(
                    "Backend indisponivel",
                    "Nao consegui falar com a API do MLBB Analytics. Tente de novo em instantes.",
                )
            )
            return
        except BackendError as exc:
            logger.error("falha no draft", extra={"error": str(exc)})
            await interaction.followup.send(
                embed=build_error_embed("Erro ao montar o draft", str(exc))
            )
            return

        if (formato.value if formato else "imagem") == "imagem":
            try:
                png = await render_draft_card(dados)
            except Exception as exc:  # noqa: BLE001 - card e opcional
                logger.warning("falha ao renderizar card de draft", extra={"error": str(exc)})
                png = None
            if png:
                await interaction.followup.send(file=discord.File(io.BytesIO(png), "draft.png"))
                return

        await interaction.followup.send(embed=build_draft_embed(dados))


async def setup(bot: commands.Bot) -> None:
    api: MLBBApiClient = bot.api  # type: ignore[attr-defined]
    await bot.add_cog(DraftCog(bot, api))
