"""Espelho tipado das respostas da API consumidas pelo bot.

Sao deliberadamente tolerantes (`extra="ignore"`): campos novos na API nao
podem quebrar o bot em producao.
"""

from __future__ import annotations

from datetime import datetime

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
