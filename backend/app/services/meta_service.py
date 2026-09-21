"""Montagem da tier list de meta a partir dos snapshots armazenados."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.scoring import tier_rank
from app.models.enums import Lane, RankFilter
from app.models.meta_snapshot import MetaSnapshot
from app.providers.factory import get_provider
from app.repositories.meta_repository import MetaRepository
from app.repositories.stats_repository import HeroStatsRepository
from app.schemas.hero import HeroRead
from app.schemas.meta import MetaEntry, MetaResponse

# Quantos herois aparecem nas secoes "em alta" / "em queda".
TREND_LIMIT = 5

# Variacao minima de score para um heroi ser considerado em alta/queda.
# Evita listar ruido de arredondamento como se fosse movimento de meta.
TREND_MIN_DELTA = 0.5


class MetaService:
    """Le snapshots do banco e devolve a visao pronta para API e bot."""

    def __init__(self, db: Session) -> None:
        self.meta = MetaRepository(db)
        self.stats = HeroStatsRepository(db)

    def get_meta(self, *, lane: Lane | None = None, limit: int | None = None) -> MetaResponse:
        provider = get_provider()
        latest_at = self.meta.latest_collected_at(lane=lane)

        if latest_at is None:
            # Banco ainda sem coleta: resposta vazia e honesta, nao um erro.
            return MetaResponse(
                lane=lane,
                source=provider.name,
                is_mock=provider.is_mock,
                entries=[],
            )

        previous_at = self.meta.previous_collected_at(latest_at, lane=lane)
        current = self.meta.list_at(latest_at, lane=lane)
        previous_index = self._index_by_hero_lane(
            self.meta.list_at(previous_at, lane=lane, with_hero=False) if previous_at else []
        )
        win_rates = self._win_rate_index(latest_at)
        previous_win_rates = self._win_rate_index(previous_at) if previous_at else {}

        entries = [
            self._to_entry(snapshot, previous_index, win_rates, previous_win_rates)
            for snapshot in current
        ]
        entries.sort(key=lambda entry: (tier_rank(entry.tier), -entry.score))

        rising, falling = self._split_trends(entries)
        if limit is not None:
            entries = entries[:limit]

        return MetaResponse(
            lane=lane,
            patch=current[0].patch if current else None,
            collected_at=latest_at,
            previous_collected_at=previous_at,
            source=current[0].source if current else provider.name,
            is_mock=provider.is_mock,
            entries=entries,
            rising=rising,
            falling=falling,
        )

    # -- helpers --------------------------------------------------------

    @staticmethod
    def _index_by_hero_lane(
        snapshots: list[MetaSnapshot],
    ) -> dict[tuple[int, str], MetaSnapshot]:
        return {(snapshot.hero_id, str(snapshot.lane)): snapshot for snapshot in snapshots}

    def _win_rate_index(self, collected_at: datetime | None) -> dict[int, float]:
        if collected_at is None:
            return {}
        readings = self.stats.list_at(collected_at, rank_filter=RankFilter.ALL)
        return {reading.hero_id: reading.win_rate for reading in readings}

    def _to_entry(
        self,
        snapshot: MetaSnapshot,
        previous_index: dict[tuple[int, str], MetaSnapshot],
        win_rates: dict[int, float],
        previous_win_rates: dict[int, float],
    ) -> MetaEntry:
        previous = previous_index.get((snapshot.hero_id, str(snapshot.lane)))
        win_rate = win_rates.get(snapshot.hero_id)
        previous_win_rate = previous_win_rates.get(snapshot.hero_id)

        win_rate_delta = None
        if win_rate is not None and previous_win_rate is not None:
            win_rate_delta = round(win_rate - previous_win_rate, 5)

        return MetaEntry(
            hero=HeroRead.model_validate(snapshot.hero),
            lane=snapshot.lane,
            tier=snapshot.tier,
            score=snapshot.score,
            score_delta=round(snapshot.score - previous.score, 2) if previous else None,
            previous_tier=previous.tier if previous else None,
            win_rate=win_rate,
            win_rate_delta=win_rate_delta,
        )

    @staticmethod
    def _split_trends(entries: list[MetaEntry]) -> tuple[list[MetaEntry], list[MetaEntry]]:
        with_delta = [entry for entry in entries if entry.score_delta is not None]
        rising = sorted(
            (entry for entry in with_delta if (entry.score_delta or 0) >= TREND_MIN_DELTA),
            key=lambda entry: entry.score_delta or 0,
            reverse=True,
        )[:TREND_LIMIT]
        falling = sorted(
            (entry for entry in with_delta if (entry.score_delta or 0) <= -TREND_MIN_DELTA),
            key=lambda entry: entry.score_delta or 0,
        )[:TREND_LIMIT]
        return rising, falling
