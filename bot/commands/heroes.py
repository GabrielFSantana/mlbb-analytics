"""Comandos /hero, /counter e /patch."""

from __future__ import annotations

import io

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.logging import get_logger
from bot.services.api_client import (
    BackendError,
    BackendUnavailableError,
    MLBBApiClient,
)
from bot.ui.cards import render_build_card, render_counters_card, render_hero_card
from bot.ui.embeds import (
    build_builds_embed,
    build_counters_embed,
    build_error_embed,
    build_hero_embed,
    build_patch_embed,
)

logger = get_logger(__name__)

FORMAT_CHOICES = [
    app_commands.Choice(name="Imagem", value="imagem"),
    app_commands.Choice(name="Texto", value="texto"),
]

RANK_CHOICES = [
    app_commands.Choice(name="Todos os ranques", value="all"),
    app_commands.Choice(name="Epico", value="epic"),
    app_commands.Choice(name="Lenda", value="legend"),
    app_commands.Choice(name="Mitico", value="mythic"),
    app_commands.Choice(name="Honra", value="honor"),
    app_commands.Choice(name="Gloria", value="glory"),
]

NAO_ENCONTRADO = (
    "Nao achei esse heroi. Confira a grafia — tente o nome como aparece no jogo, "
    "por exemplo `Yi Sun-shin` ou `X.Borg`."
)


class HeroesCog(commands.Cog):
    """Consulta de herois, counters e patch."""

    def __init__(self, bot: commands.Bot, api: MLBBApiClient) -> None:
        self.bot = bot
        self.api = api

    async def _responder(
        self,
        interaction: discord.Interaction,
        formato: app_commands.Choice[str] | None,
        renderizador,
        dados,
        nome_arquivo: str,
        embed_alternativo,
    ) -> None:
        """Envia o card; cai para o embed se a renderizacao nao sair.

        A imagem e um detalhe de apresentacao: ela nunca pode fazer o comando
        deixar de responder.
        """
        if (formato.value if formato else "imagem") == "imagem":
            try:
                png = await renderizador(dados)
            except Exception as exc:  # noqa: BLE001 - card e opcional
                logger.warning(
                    "falha ao renderizar card",
                    extra={"arquivo": nome_arquivo, "error": str(exc)},
                )
                png = None
            if png:
                await interaction.followup.send(
                    file=discord.File(io.BytesIO(png), nome_arquivo)
                )
                return
        await interaction.followup.send(embed=embed_alternativo(dados))

    async def _responder_erro(
        self,
        interaction: discord.Interaction,
        exc: BackendError,
        contexto: str,
    ) -> None:
        if isinstance(exc, BackendUnavailableError):
            embed = build_error_embed(
                "Backend indisponivel",
                "Nao consegui falar com a API do MLBB Analytics. Tente de novo em instantes.",
            )
        elif "404" in str(exc):
            embed = build_error_embed("Heroi nao encontrado", NAO_ENCONTRADO)
        else:
            logger.error(contexto, extra={"error": str(exc)})
            embed = build_error_embed("Erro na consulta", str(exc))
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="hero", description="Ficha de um heroi: stats e posicao no meta")
    @app_commands.describe(
        nome="Nome do heroi, como aparece no jogo",
        ranque="Faixa de ranque. Sem valor, usa o agregado geral.",
        formato="Imagem (padrao) ou texto.",
    )
    @app_commands.choices(ranque=RANK_CHOICES, formato=FORMAT_CHOICES)
    async def hero(
        self,
        interaction: discord.Interaction,
        nome: str,
        ranque: app_commands.Choice[str] | None = None,
        formato: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer()
        try:
            dados = await self.api.get_hero(nome, rank=ranque.value if ranque else None)
        except BackendError as exc:
            await self._responder_erro(interaction, exc, "falha ao buscar heroi")
            return

        await self._responder(
            interaction,
            formato,
            render_hero_card,
            dados,
            f"hero-{dados.slug}.png",
            build_hero_embed,
        )

    @app_commands.command(
        name="counter",
        description="Contra quem o heroi vai bem, contra quem vai mal, e com quem combina",
    )
    @app_commands.describe(
        nome="Nome do heroi, como aparece no jogo",
        formato="Imagem (padrao) ou texto.",
    )
    @app_commands.choices(formato=FORMAT_CHOICES)
    async def counter(
        self,
        interaction: discord.Interaction,
        nome: str,
        formato: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer()
        try:
            dados = await self.api.get_hero_counters(nome)
        except BackendError as exc:
            await self._responder_erro(interaction, exc, "falha ao buscar counters")
            return
        await self._responder(
            interaction,
            formato,
            render_counters_card,
            dados,
            f"counter-{dados.hero.slug}.png",
            build_counters_embed,
        )

    @app_commands.command(
        name="build",
        description="Itens centrais, emblema e feitico mais usados no heroi",
    )
    @app_commands.describe(
        nome="Nome do heroi, como aparece no jogo",
        lane="Lane especifica. Sem valor, usa aquela em que o heroi esta mais forte.",
        formato="Imagem (padrao) ou texto.",
    )
    @app_commands.choices(
        formato=FORMAT_CHOICES,
        lane=[
            app_commands.Choice(name="Jungle", value="jungle"),
            app_commands.Choice(name="Gold", value="gold"),
            app_commands.Choice(name="Mid", value="mid"),
            app_commands.Choice(name="Exp", value="exp"),
            app_commands.Choice(name="Roam", value="roam"),
        ]
    )
    async def build(
        self,
        interaction: discord.Interaction,
        nome: str,
        lane: app_commands.Choice[str] | None = None,
        formato: app_commands.Choice[str] | None = None,
    ) -> None:
        await interaction.response.defer()
        try:
            dados = await self.api.get_hero_builds(nome, lane.value if lane else None)
        except BackendError as exc:
            await self._responder_erro(interaction, exc, "falha ao buscar builds")
            return
        await self._responder(
            interaction,
            formato,
            render_build_card,
            dados,
            f"build-{dados.hero.slug}.png",
            build_builds_embed,
        )

    @app_commands.command(name="patch", description="Patch atual do jogo segundo a fonte")
    async def patch(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            dados = await self.api.get_current_patch()
        except BackendError as exc:
            await self._responder_erro(interaction, exc, "falha ao buscar patch")
            return
        await interaction.followup.send(embed=build_patch_embed(dados))


async def setup(bot: commands.Bot) -> None:
    api: MLBBApiClient = bot.api  # type: ignore[attr-defined]
    await bot.add_cog(HeroesCog(bot, api))
