"""Publicacoes automaticas no canal de atualizacoes.

Um unico laco cuida dos dois tipos de publicacao (meta e ranking
semanal): ambos perguntam a API se ha algo pendente, publicam e
confirmam. Dois lacos separados so duplicariam o tratamento de erro e o
cuidado com o canal.

Sobre as atualizacoes de meta:

O bot pergunta a API, em intervalo fixo, se existe uma coleta ainda nao
publicada. Havendo, publica no canal configurado e confirma - a confirmacao
e o que impede a mesma coleta de sair duas vezes, inclusive apos reinicio.

O estado de "ja publicado" vive no banco, do lado do backend, e nao na
memoria do bot, justamente para sobreviver a reinicios.
"""

from __future__ import annotations

import io

import discord
from discord.ext import commands, tasks

from bot.core.config import settings
from bot.core.logging import get_logger
from bot.services.api_client import BackendError, MLBBApiClient
from bot.ui.cards import render_weekly_ranking_card
from bot.ui.embeds import build_meta_update_embed, build_weekly_ranking_embed

logger = get_logger(__name__)


class MetaUpdatesCog(commands.Cog):
    """Loop que publica novidades do meta no canal de atualizacoes."""

    def __init__(self, bot: commands.Bot, api: MLBBApiClient) -> None:
        self.bot = bot
        self.api = api
        self.publicar_atualizacoes.change_interval(minutes=settings.meta_poll_minutes)

    async def cog_load(self) -> None:
        if not settings.meta_updates_enabled:
            logger.info("publicacao automatica desabilitada (META_UPDATES_ENABLED=false)")
            return
        if settings.discord_meta_channel_id is None:
            logger.warning(
                "DISCORD_META_CHANNEL_ID nao definido: as atualizacoes de meta "
                "nao serao publicadas"
            )
            return
        self.publicar_atualizacoes.start()

    async def cog_unload(self) -> None:
        self.publicar_atualizacoes.cancel()

    def _canal(self) -> discord.abc.Messageable | None:
        canal = self.bot.get_channel(settings.discord_meta_channel_id or 0)
        if canal is None:
            logger.error(
                "canal de atualizacoes nao encontrado; confira DISCORD_META_CHANNEL_ID "
                "e se o bot tem acesso a ele",
                extra={"channel_id": settings.discord_meta_channel_id},
            )
        return canal

    @tasks.loop(minutes=30)
    async def publicar_atualizacoes(self) -> None:
        await self._publicar_meta()
        await self._publicar_ranking_semanal()

    async def _publicar_meta(self) -> None:
        try:
            atualizacao = await self.api.get_pending_update()
        except BackendError as exc:
            # Backend fora do ar nao e motivo para derrubar o loop: a
            # proxima passagem tenta de novo.
            logger.warning("nao consegui consultar atualizacoes", extra={"error": str(exc)})
            return

        if atualizacao is None:
            return

        canal = self._canal()
        if canal is None:
            return

        try:
            await canal.send(embed=build_meta_update_embed(atualizacao))
        except discord.HTTPException as exc:
            # Sem ack: a proxima passagem tenta publicar de novo.
            logger.error(
                "falha ao publicar atualizacao no canal",
                extra={"error": str(exc), "status": exc.status},
            )
            return

        # So confirmamos depois da publicacao dar certo.
        await self.api.ack_update(atualizacao.collected_at, atualizacao.source)
        logger.info(
            "atualizacao de meta publicada",
            extra={
                "collected_at": atualizacao.collected_at.isoformat(),
                "source": atualizacao.source,
                "channel_id": canal.id,
            },
        )

    async def _publicar_ranking_semanal(self) -> None:
        try:
            ranking = await self.api.get_pending_weekly_ranking()
        except BackendError as exc:
            logger.warning("nao consegui consultar o ranking", extra={"error": str(exc)})
            return

        if ranking is None:
            return

        canal = self._canal()
        if canal is None:
            return

        try:
            png = await render_weekly_ranking_card(ranking)
            await canal.send(file=discord.File(io.BytesIO(png), "ranking-semanal.png"))
        except discord.HTTPException as exc:
            logger.error(
                "falha ao publicar o ranking no canal",
                extra={"error": str(exc), "status": exc.status},
            )
            return
        except Exception as exc:  # noqa: BLE001 - card e opcional
            # Card falhou: publicamos em texto em vez de perder a semana.
            logger.warning("falha ao renderizar o ranking", extra={"error": str(exc)})
            try:
                await canal.send(embed=build_weekly_ranking_embed(ranking))
            except discord.HTTPException:
                return

        await self.api.ack_weekly_ranking(ranking.week_label)
        logger.info(
            "ranking semanal publicado",
            extra={"semana": ranking.week_label, "channel_id": canal.id},
        )

    @publicar_atualizacoes.before_loop
    async def esperar_bot(self) -> None:
        """Nao consulta nada antes do bot estar conectado."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    api: MLBBApiClient = bot.api  # type: ignore[attr-defined]
    await bot.add_cog(MetaUpdatesCog(bot, api))
