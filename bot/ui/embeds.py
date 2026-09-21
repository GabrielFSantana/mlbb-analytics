"""Construcao dos embeds do Discord.

Funcoes puras: recebem os schemas da API e devolvem `discord.Embed`, sem
tocar em rede ou estado global. Isso mantem a formatacao testavel.
"""

from __future__ import annotations

from datetime import datetime

import discord

from bot.services.schemas import MetaEntry, MetaResponse

LANE_LABELS: dict[str, str] = {
    "jungle": "JUNGLE",
    "gold": "GOLD LANE",
    "mid": "MID LANE",
    "exp": "EXP LANE",
    "roam": "ROAM",
}

# Ordem de exibicao dos tiers.
TIER_ORDER: tuple[str, ...] = ("S+", "S", "A", "B", "C", "D")

TIER_EMOJI: dict[str, str] = {
    "S+": "🥇",
    "S": "🥈",
    "A": "🥉",
    "B": "▫️",
    "C": "▫️",
    "D": "▫️",
}

COLOR_META = discord.Colour.from_rgb(240, 173, 78)
COLOR_MOCK = discord.Colour.from_rgb(150, 150, 150)

# Limites para nao estourar o teto de 1024 caracteres por campo do Discord.
MAX_HEROES_PER_TIER = 12
MAX_TREND_ENTRIES = 5

MOCK_WARNING = (
    "⚠️ **DADOS DE DEMONSTRACAO (MOCK).** O Mobile Legends nao possui API "
    "publica oficial para este uso; enquanto uma fonte real nao for "
    "integrada, estes numeros sao ficticios e **nao refletem o jogo**."
)

EMPTY_WARNING = (
    "Ainda nao ha coleta de meta no banco.\n"
    "Rode `python -m app.cli sync` no backend para popular os dados."
)


def lane_label(lane: str | None) -> str:
    if lane is None:
        return "TODAS AS LANES"
    return LANE_LABELS.get(lane, lane.upper())


def format_win_rate(entry: MetaEntry) -> str:
    if entry.win_rate is None:
        return ""
    return f" · {entry.win_rate * 100:.1f}% WR"


def format_hero_line(entry: MetaEntry, *, show_lane: bool) -> str:
    lane_suffix = f" ({LANE_LABELS.get(entry.lane, entry.lane)})" if show_lane else ""
    movement = ""
    if entry.previous_tier and entry.previous_tier != entry.tier:
        movement = f" · {entry.previous_tier}→{entry.tier}"
    return f"**{entry.hero.name}**{lane_suffix}{format_win_rate(entry)}{movement}"


def format_trend_line(entry: MetaEntry) -> str:
    delta = entry.score_delta or 0.0
    wr_delta = ""
    if entry.win_rate_delta is not None:
        wr_delta = f" · {entry.win_rate_delta * 100:+.1f}pp WR"
    lane = LANE_LABELS.get(entry.lane, entry.lane)
    return f"**{entry.hero.name}** ({lane}) {delta:+.1f} pts{wr_delta}"


def _footer(meta: MetaResponse) -> str:
    patch = meta.patch or "desconhecido"
    updated = _format_timestamp(meta.collected_at)
    parts = [f"Patch: {patch}", f"Atualizado: {updated}", f"Fonte: {meta.source}"]
    if meta.is_mock:
        parts.append("DADOS MOCK")
    return " • ".join(parts)


def _format_timestamp(value: datetime | None) -> str:
    if value is None:
        return "sem coleta"
    return value.strftime("%d/%m/%Y %H:%M UTC")


def build_meta_embed(meta: MetaResponse, *, lane: str | None = None) -> discord.Embed:
    """Monta o embed da tier list."""
    show_lane = lane is None
    embed = discord.Embed(
        title=f"🔥 META MLBB — {lane_label(lane)}",
        colour=COLOR_MOCK if meta.is_mock else COLOR_META,
        description=MOCK_WARNING if meta.is_mock else None,
    )

    if not meta.entries:
        embed.description = (
            f"{MOCK_WARNING}\n\n{EMPTY_WARNING}" if meta.is_mock else EMPTY_WARNING
        )
        embed.set_footer(text=_footer(meta))
        return embed

    for tier in TIER_ORDER:
        heroes = [entry for entry in meta.entries if entry.tier == tier]
        if not heroes:
            continue
        lines = [format_hero_line(entry, show_lane=show_lane) for entry in heroes]
        hidden = len(lines) - MAX_HEROES_PER_TIER
        shown = lines[:MAX_HEROES_PER_TIER]
        if hidden > 0:
            shown.append(f"_+{hidden} outros_")
        embed.add_field(
            name=f"{TIER_EMOJI.get(tier, '▫️')} {tier}",
            value="\n".join(shown),
            inline=False,
        )

    if meta.rising:
        embed.add_field(
            name="📈 Em alta",
            value="\n".join(format_trend_line(e) for e in meta.rising[:MAX_TREND_ENTRIES]),
            inline=False,
        )
    if meta.falling:
        embed.add_field(
            name="📉 Em queda",
            value="\n".join(format_trend_line(e) for e in meta.falling[:MAX_TREND_ENTRIES]),
            inline=False,
        )
    if not meta.rising and not meta.falling and meta.previous_collected_at is None:
        embed.add_field(
            name="📊 Tendencia",
            value="Disponivel a partir da segunda coleta.",
            inline=False,
        )

    embed.set_footer(text=_footer(meta))
    return embed


def build_error_embed(title: str, message: str) -> discord.Embed:
    return discord.Embed(
        title=f"⚠️ {title}",
        description=message,
        colour=discord.Colour.from_rgb(200, 80, 80),
    )
