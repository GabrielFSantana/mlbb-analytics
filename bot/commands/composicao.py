"""Comando /composicao: como as duplas do seu time se comportam juntas.

Diferente de `/draft`, que responde "o que pegar agora", este comando olha
para um time ja montado e diz o que a fonte MEDIU sobre cada dupla dele.
Com um heroi so, vira "com quem esse heroi forma boas duplas".
"""

from __future__ import annotations

import io

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.logging import get_logger
from bot.services.api_client import BackendError, BackendUnavailableError, MLBBApiClient
from bot.ui.cards import render_composition_card
from bot.ui.embeds import build_composition_embed, build_error_embed

logger = get_logger(__name__)

FORMAT_CHOICES = [
    app_commands.Choice(name="Imagem", value="imagem"),
    app_commands.Choice(name="Texto", value="texto"),
]

#: Uma partida tem cinco de cada lado.
MAX_HEROIS = 5


def separar_nomes(texto: str) -> list[str]:
    """Quebra "Leomord, Kagura" na lista de nomes."""
    return [parte.strip() for parte in texto.split(",") if parte.strip()][:MAX_HEROIS]


class ComposicaoCog(commands.Cog):
    """Leitura de composicao pela sinergia medida."""

    def __init__(self, bot: commands.Bot, api: MLBBApiClient) -> None:
        self.bot = bot
        self.api = api

    @app_commands.command(
        name="composicao",
        description="Quanto cada dupla do seu time desloca a taxa de vitoria",
    )
    @app_commands.describe(
        herois=(
            "Ate cinco herois, separados por virgula. Com um so, mostra as "
            "melhores e piores duplas dele."
        ),
        formato="Imagem (padrao) ou texto.",
    )
    @app_commands.choices(formato=FORMAT_CHOICES)
    async def composicao(
        self,
        interaction: discord.Interaction,
        herois: str,
        formato: app_commands.Choice[str] | None = None,
    ) -> None:
        # A consulta busca uma linha da matriz por heroi na primeira vez;
        # sem o defer, o Discord expira antes da resposta.
        await interaction.response.defer()

        lista = separar_nomes(herois)
        if not lista:
            await interaction.followup.send(
                embed=build_error_embed(
                    "Informe ao menos um heroi",
                    "Use virgula para separar, por exemplo: `Kagura, Tigreal, Beatrix`.",
                )
            )
            return

        try:
            dados = await self.api.get_composition(lista)
        except BackendUnavailableError:
            await interaction.followup.send(
                embed=build_error_embed(
                    "Backend indisponivel",
                    "Nao consegui falar com a API do MLBB Analytics. Tente de novo em instantes.",
                )
            )
            return
        except BackendError as exc:
            logger.error("falha na composicao", extra={"error": str(exc)})
            await interaction.followup.send(
                embed=build_error_embed("Erro ao ler a composicao", str(exc))
            )
            return

        if (formato.value if formato else "imagem") == "imagem":
            try:
                png = await render_composition_card(dados)
            except Exception as exc:  # noqa: BLE001 - card e opcional
                logger.warning(
                    "falha ao renderizar card de composicao", extra={"error": str(exc)}
                )
                png = None
            if png:
                await interaction.followup.send(
                    file=discord.File(io.BytesIO(png), "composicao.png")
                )
                return

        await interaction.followup.send(embed=build_composition_embed(dados))


async def setup(bot: commands.Bot) -> None:
    api: MLBBApiClient = bot.api  # type: ignore[attr-defined]
    await bot.add_cog(ComposicaoCog(bot, api))
