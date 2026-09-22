"""Ponto de entrada do bot do Discord."""

from __future__ import annotations

import asyncio
import sys

import discord
from discord.ext import commands

from bot.core.config import settings
from bot.core.logging import get_logger, setup_logging
from bot.services.api_client import MLBBApiClient

logger = get_logger(__name__)

# Extensoes carregadas no boot. Novos comandos entram aqui.
EXTENSIONS: tuple[str, ...] = (
    "bot.commands.meta",
    "bot.commands.heroes",
    "bot.commands.draft",
    "bot.commands.meta_updates",
)


class MLBBBot(commands.Bot):
    """Bot da plataforma.

    Usa apenas slash commands, entao nao precisa do intent privilegiado de
    conteudo de mensagem.
    """

    def __init__(self) -> None:
        # `when_mentioned` em vez de um prefixo de texto: sem isso a
        # discord.py avisa a cada boot que falta o intent de message content,
        # que um bot so de slash commands nao usa.
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.default(),
        )
        self.api = MLBBApiClient()

    async def setup_hook(self) -> None:
        await self.api.start()

        for extension in EXTENSIONS:
            await self.load_extension(extension)
            logger.info("extensao carregada", extra={"extension": extension})

        if settings.discord_guild_id:
            await self._sync_guild(settings.discord_guild_id)
        else:
            synced = await self.tree.sync()
            logger.warning(
                "DISCORD_GUILD_ID nao definido: sync global pode levar ate 1h",
                extra={"commands": len(synced)},
            )

    async def _sync_guild(self, guild_id: int) -> None:
        """Registra os comandos na guild configurada.

        Sync por guild propaga na hora; o global pode levar ate 1 hora. Se o
        bot nao estiver na guild, o Discord responde 403/404 - caso comum
        quando o `.env` aponta para um servidor ao qual o bot ainda nao foi
        convidado. Em vez de derrubar o processo, explicamos o que fazer e
        caimos para o sync global.
        """
        guild = discord.Object(id=guild_id)
        try:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        except discord.HTTPException as exc:
            logger.error(
                "nao foi possivel registrar os comandos na guild: o bot provavelmente "
                "nao foi adicionado a esse servidor. Convide-o pela URL de OAuth2 da "
                "aplicacao (scopes bot + applications.commands) ou corrija "
                "DISCORD_GUILD_ID no .env",
                extra={"guild_id": guild_id, "status": exc.status},
            )
            synced = await self.tree.sync()
            logger.warning(
                "usando sync global como alternativa: pode levar ate 1h para aparecer",
                extra={"commands": len(synced)},
            )
            return

        logger.info(
            "comandos sincronizados na guild",
            extra={"guild_id": guild_id, "commands": len(synced)},
        )

    async def on_ready(self) -> None:
        logger.info(
            "bot conectado",
            extra={"user": str(self.user), "guilds": len(self.guilds)},
        )
        await self.change_presence(activity=discord.Game(name="/meta"))

    async def close(self) -> None:
        await self.api.close()
        await super().close()


async def run() -> None:
    if not settings.discord_token:
        logger.error("DISCORD_TOKEN ausente: preencha o .env antes de subir o bot")
        raise SystemExit(1)

    bot = MLBBBot()
    async with bot:
        await bot.start(settings.discord_token)


def main() -> None:
    setup_logging(settings.log_level, json_output=settings.app_env == "production")
    try:
        asyncio.run(run())
    except KeyboardInterrupt:  # pragma: no cover - encerramento manual
        logger.info("bot encerrado pelo usuario")
        sys.exit(0)


if __name__ == "__main__":
    main()
