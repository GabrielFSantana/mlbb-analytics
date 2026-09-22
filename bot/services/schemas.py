"""Espelho tipado das respostas da API consumidas pelo bot.

Sao deliberadamente tolerantes (`extra="ignore"`): campos novos na API nao
podem quebrar o bot em producao.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Hero(ApiModel):
    id: int
    name: str
    slug: str
    role: str
    image_url: str | None = None


class MetaEntry(ApiModel):
    hero: Hero
    lane: str
    tier: str
    score: float
    score_delta: float | None = None
    previous_tier: str | None = None
    win_rate: float | None = None
    win_rate_delta: float | None = None


class MetaResponse(ApiModel):
    lane: str | None = None
    rank_filter: str = "all"
    patch: str | None = None
    collected_at: datetime | None = None
    previous_collected_at: datetime | None = None
    source: str
    is_mock: bool
    entries: list[MetaEntry] = []
    rising: list[MetaEntry] = []
    falling: list[MetaEntry] = []


class MetaUpdate(ApiModel):
    """O que mudou entre a coleta atual e a anterior."""

    collected_at: datetime
    previous_collected_at: datetime
    patch: str | None = None
    source: str
    is_mock: bool
    rising: list[MetaEntry] = []
    falling: list[MetaEntry] = []
    promoted: list[MetaEntry] = []
    demoted: list[MetaEntry] = []
    biggest_win_rate_gain: list[MetaEntry] = []


class HeroStats(ApiModel):
    win_rate: float
    pick_rate: float
    ban_rate: float
    matches: int | None = None
    patch: str
    collected_at: datetime
    source: str


class HeroLanePosition(ApiModel):
    lane: str
    tier: str
    score: float
    score_delta: float | None = None


class HeroDetail(Hero):
    latest_stats: HeroStats | None = None
    rank_filter: str = "all"
    lanes: list[HeroLanePosition] = []
    patch: str | None = None
    source: str | None = None
    is_mock: bool = False


class HeroCounters(ApiModel):
    hero: Hero
    strong_against: list[Hero] = []
    weak_against: list[Hero] = []
    good_with: list[Hero] = []
    source: str | None = None
    is_mock: bool = False


class Patch(ApiModel):
    id: int
    version: str
    released_at: date | None = None
    notes_url: str | None = None
    summary: str | None = None
    is_current: bool


class BuildItem(ApiModel):
    name: str
    image_url: str | None = None
    position: int


class HeroBuild(ApiModel):
    variant: int
    win_rate: float
    pick_rate: float
    emblem: str | None = None
    battle_spell: str | None = None
    items: list[BuildItem] = []


class HeroBuilds(ApiModel):
    hero: Hero
    lane: str | None = None
    builds: list[HeroBuild] = []
    collected_at: datetime | None = None
    source: str
    is_mock: bool = False
    source_available: bool = True


class DraftCandidate(ApiModel):
    hero: Hero
    lane: str
    tier: str
    meta_score: float
    draft_score: float
    counters: list[Hero] = []
    countered_by: list[Hero] = []
    synergies: list[Hero] = []


class DraftResponse(ApiModel):
    enemies: list[Hero] = []
    allies: list[Hero] = []
    lane: str | None = None
    rank_filter: str = "all"
    suggestions: list[DraftCandidate] = []
    counter_picks: list[DraftCandidate] = []
    unknown_terms: list[str] = []
    collected_at: datetime | None = None
    patch: str | None = None
    source: str
    is_mock: bool = False


class PlayerProgress(ApiModel):
    display_name: str
    discord_user_id: int
    stars: int
    percent: float
    reported_at: datetime
    stars_gained: int | None = None
    days_measured: float | None = None
    stars_per_day: float | None = None
    projected_at: datetime | None = None
    reached: bool = False


class TeamProgress(ApiModel):
    goal: int
    players: list[PlayerProgress] = []
    total_stars: int = 0
    average_stars: float = 0.0
    players_reached: int = 0
    team_stars_gained: int | None = None
    window_days: int = 7
    self_reported: bool = True
