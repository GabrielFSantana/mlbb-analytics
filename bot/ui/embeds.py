"""Construcao dos embeds do Discord.

Funcoes puras: recebem os schemas da API e devolvem `discord.Embed`, sem
tocar em rede ou estado global. Isso mantem a formatacao testavel.
"""

from __future__ import annotations

from datetime import datetime

import discord

from bot.services.schemas import (
    HeroCounters,
    HeroDetail,
    MetaEntry,
    MetaResponse,
    MetaUpdate,
    Patch,
)

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


# ---------------------------------------------------------------------
# Atualizacoes automaticas de meta (Fase 2)
# ---------------------------------------------------------------------

COLOR_UPDATE = discord.Colour.from_rgb(88, 166, 255)


def _linha_movimento(entry: MetaEntry) -> str:
    """Linha das secoes de alta/queda: heroi, lane e variacao."""
    lane = LANE_LABELS.get(entry.lane, entry.lane)
    delta = entry.score_delta or 0.0
    wr = ""
    if entry.win_rate_delta is not None:
        wr = f" · {entry.win_rate_delta * 100:+.1f}pp WR"
    return f"**{entry.hero.name}** ({lane}) {delta:+.1f} pts{wr}"


def _linha_tier(entry: MetaEntry) -> str:
    lane = LANE_LABELS.get(entry.lane, entry.lane)
    return f"**{entry.hero.name}** ({lane}) {entry.previous_tier} → {entry.tier}"


def _linha_win_rate(entry: MetaEntry) -> str:
    delta = (entry.win_rate_delta or 0.0) * 100
    atual = f" (agora {entry.win_rate * 100:.1f}%)" if entry.win_rate is not None else ""
    return f"**{entry.hero.name}** {delta:+.2f}pp{atual}"


def build_meta_update_embed(update: MetaUpdate) -> discord.Embed:
    """Monta a mensagem publicada no canal de atualizacoes."""
    periodo = (
        f"{_format_timestamp(update.previous_collected_at)} → "
        f"{_format_timestamp(update.collected_at)}"
    )
    embed = discord.Embed(
        title="🔥 META UPDATE",
        colour=COLOR_MOCK if update.is_mock else COLOR_UPDATE,
        description=MOCK_WARNING if update.is_mock else f"Mudancas no periodo {periodo}.",
    )

    secoes: list[tuple[str, list[MetaEntry], object]] = [
        ("📈 Subiu", update.rising, _linha_movimento),
        ("📉 Caiu", update.falling, _linha_movimento),
        ("⬆️ Subiu de tier", update.promoted, _linha_tier),
        ("⬇️ Caiu de tier", update.demoted, _linha_tier),
        ("🔥 Maior crescimento de WR", update.biggest_win_rate_gain, _linha_win_rate),
    ]
    for nome, entradas, formatador in secoes:
        if not entradas:
            continue
        embed.add_field(
            name=nome,
            value="\n".join(formatador(e) for e in entradas[:MAX_TREND_ENTRIES]),
            inline=False,
        )

    patch = update.patch or "desconhecido"
    rodape = [f"Patch: {patch}", f"Fonte: {update.source}"]
    if update.is_mock:
        rodape.append("DADOS MOCK")
    embed.set_footer(text=" • ".join(rodape))
    return embed


# ---------------------------------------------------------------------
# /hero, /counter e /patch (Fase 3b)
# ---------------------------------------------------------------------

ROLE_LABELS: dict[str, str] = {
    "tank": "Tank",
    "fighter": "Lutador",
    "assassin": "Assassino",
    "mage": "Mago",
    "marksman": "Atirador",
    "support": "Suporte",
}

COLOR_HERO = discord.Colour.from_rgb(155, 109, 255)
COLOR_PATCH = discord.Colour.from_rgb(90, 190, 140)


def _rodape_fonte(patch: str | None, source: str | None, is_mock: bool) -> str:
    partes = [f"Patch: {patch or 'desconhecido'}"]
    if source:
        partes.append(f"Fonte: {source}")
    if is_mock:
        partes.append("DADOS MOCK")
    return " • ".join(partes)


def build_hero_embed(hero: HeroDetail) -> discord.Embed:
    """Ficha do heroi: classe, estatisticas e posicao no meta por lane."""
    embed = discord.Embed(
        title=f"🦸 {hero.name}",
        colour=COLOR_MOCK if hero.is_mock else COLOR_HERO,
        description=MOCK_WARNING if hero.is_mock else None,
    )
    if hero.image_url:
        embed.set_thumbnail(url=hero.image_url)

    embed.add_field(name="Classe", value=ROLE_LABELS.get(hero.role, hero.role), inline=True)

    if hero.latest_stats:
        s = hero.latest_stats
        embed.add_field(
            name="Estatisticas",
            value=(
                f"🏆 Win rate: **{s.win_rate * 100:.2f}%**\n"
                f"🎯 Pick rate: {s.pick_rate * 100:.2f}%\n"
                f"🚫 Ban rate: {s.ban_rate * 100:.2f}%"
            ),
            inline=True,
        )
    else:
        embed.add_field(name="Estatisticas", value="Sem coleta ainda.", inline=True)

    if hero.lanes:
        linhas = []
        for pos in hero.lanes:
            lane = LANE_LABELS.get(pos.lane, pos.lane)
            variacao = f" ({pos.score_delta:+.1f})" if pos.score_delta is not None else ""
            emoji = TIER_EMOJI.get(pos.tier, "▫️")
            linhas.append(f"{emoji} **{pos.tier}** · {lane} · {pos.score:.1f} pts{variacao}")
        embed.add_field(name="Posicao no meta", value="\n".join(linhas), inline=False)

    embed.set_footer(text=_rodape_fonte(hero.patch, hero.source, hero.is_mock))
    return embed


def build_counters_embed(dados: HeroCounters) -> discord.Embed:
    """Contra quem o heroi vai bem, mal, e com quem combina."""
    embed = discord.Embed(
        title=f"⚔️ {dados.hero.name} — counters",
        colour=COLOR_MOCK if dados.is_mock else COLOR_HERO,
        description=MOCK_WARNING if dados.is_mock else None,
    )
    if dados.hero.image_url:
        embed.set_thumbnail(url=dados.hero.image_url)

    secoes = [
        ("✅ Forte contra", dados.strong_against),
        ("❌ Fraco contra", dados.weak_against),
        ("🤝 Combina com", dados.good_with),
    ]
    tem_algo = False
    for nome, herois in secoes:
        if not herois:
            continue
        tem_algo = True
        embed.add_field(
            name=nome,
            value="\n".join(f"• {h.name}" for h in herois),
            inline=True,
        )

    if not tem_algo:
        embed.description = (
            f"{embed.description}\n\n" if embed.description else ""
        ) + "A fonte nao publicou relacoes para este heroi."

    embed.set_footer(text=_rodape_fonte(None, dados.source, dados.is_mock))
    return embed


def build_patch_embed(patch: Patch | None) -> discord.Embed:
    """Patch vigente segundo a fonte de dados."""
    if patch is None:
        return discord.Embed(
            title="🗓️ Patch atual",
            description="Ainda nao ha patch registrado. Rode uma coleta primeiro.",
            colour=COLOR_PATCH,
        )

    embed = discord.Embed(
        title=f"🗓️ Patch {patch.version}",
        colour=COLOR_PATCH,
        description=patch.summary,
    )
    if patch.released_at:
        embed.add_field(
            name="Lancamento",
            value=patch.released_at.strftime("%d/%m/%Y"),
            inline=True,
        )
    if patch.notes_url:
        embed.add_field(name="Notas", value=f"[Abrir]({patch.notes_url})", inline=True)
    embed.set_footer(text="Versao informada pela fonte de dados configurada.")
    return embed
