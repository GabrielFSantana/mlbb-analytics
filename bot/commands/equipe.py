"""Comandos da meta de estrelas do time."""

from __future__ import annotations

import io

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.logging import get_logger
from bot.services.api_client import BackendError, BackendUnavailableError, MLBBApiClient
from bot.ui.cards import render_progress_card
from bot.ui.embeds import build_error_embed, build_progress_embed, build_star_report_embed

logger = get_logger(__name__)

#: Teto de sanidade no reporte. Serve para pegar digitacao errada (1420 em
#: vez de 142), nao para julgar o ranque de ninguem.
MAX_ESTRELAS = 2000


class EquipeCog(commands.Cog):
    """Acompanhamento coletivo da meta de estrelas."""

    def __init__(self, bot: commands.Bot, api: MLBBApiClient) -> None:
        self.bot = bot
        self.api = api

    @app_commands.command(
        name="estrelas",
        description="Registra quantas estrelas voce tem agora",
    )
    @app_commands.describe(
        quantidade="Suas estrelas atuais",
        nota="Observacao opcional (ex.: 'subi 5 hoje')",
    )
    async def estrelas(
        self,
        interaction: discord.Interaction,
        quantidade: app_commands.Range[int, 0, MAX_ESTRELAS],
        nota: str | None = None,
    ) -> None:
        await interaction.response.defer()
        try:
            progresso = await self.api.report_stars(
                interaction.user.id,
                interaction.user.display_name,
                quantidade,
                nota,
            )
        except BackendUnavailableError:
            await interaction.followup.send(
                embed=build_error_embed(
                    "Backend indisponivel",
                    "Nao consegui registrar agora. Tente de novo em instantes.",
                )
            )
            return
        except BackendError as exc:
            logger.error("falha ao registrar estrelas", extra={"error": str(exc)})
            await interaction.followup.send(
                embed=build_error_embed("Erro ao registrar", str(exc))
            )
            return

        await interaction.followup.send(embed=build_star_report_embed(progresso))

    @app_commands.command(
        name="progresso",
        description="Mostra o progresso do time rumo a meta de estrelas",
    )
    @app_commands.describe(
        meta="Meta de estrelas. Sem valor, usa a configurada no projeto.",
        formato="Imagem (padrao) ou texto.",
    )
    @app_commands.choices(
        formato=[
            app_commands.Choice(name="Imagem", value="imagem"),
            app_commands.Choice(name="Texto", value="texto"),
        ]
    )
    async def progresso(
        self,
        interaction: discord.Interaction,
        meta: app_commands.Range[int, 1, MAX_ESTRELAS] | None = None,
        formato: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer()
        try:
            dados = await self.api.get_team_progress(meta)
        except BackendError as exc:
            embed = (
                build_error_embed(
                    "Backend indisponivel",
                    "Nao consegui falar com a API. Tente de novo em instantes.",
                )
                if isinstance(exc, BackendUnavailableError)
                else build_error_embed("Erro ao buscar o progresso", str(exc))
            )
            await interaction.followup.send(embed=embed)
            return

        if (formato.value if formato else "imagem") == "imagem":
            try:
                png = await render_progress_card(dados)
            except Exception as exc:  # noqa: BLE001 - card e opcional
                logger.warning("falha ao renderizar progresso", extra={"error": str(exc)})
                png = None
            if png:
                await interaction.followup.send(
                    file=discord.File(io.BytesIO(png), "progresso.png")
                )
                return

        await interaction.followup.send(embed=build_progress_embed(dados))


async def setup(bot: commands.Bot) -> None:
    api: MLBBApiClient = bot.api  # type: ignore[attr-defined]
    await bot.add_cog(EquipeCog(bot, api))
