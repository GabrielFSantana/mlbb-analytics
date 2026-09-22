"""Provider de demonstracao, baseado em um arquivo JSON versionado.

Os numeros vem de `app/data/mock_meta.json` e SAO FICTICIOS. Este provider
existe para permitir desenvolver a plataforma inteira (API, jobs, bot) sem
depender de uma fonte externa que ainda nao foi definida - e para servir de
referencia de implementacao para o primeiro provider real.

O arquivo carrega duas leituras por heroi (atual e anterior), de modo que o
calculo de tendencia ja seja exercitado pelo mesmo codigo que rodara em
producao.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

from app.core.logging import get_logger
from app.domain.scoring import calculate_score, score_to_tier
from app.models.enums import HeroRole, Lane, RankFilter, RelationType
from app.providers.base import MLBBDataProvider
from app.providers.schemas import (
    HeroBuildData,
    HeroData,
    HeroRelationData,
    HeroStatsData,
    ItemData,
    MetaEntryData,
    PatchData,
)

logger = get_logger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "mock_meta.json"


@lru_cache(maxsize=1)
def _load_dataset(path: str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        return json.load(fh)


class MockDataProvider(MLBBDataProvider):
    """Fonte de dados ficticios para desenvolvimento e demonstracao."""

    name: ClassVar[str] = "mock"
    is_mock: ClassVar[bool] = True
    source_description: ClassVar[str] = (
        "Arquivo estatico app/data/mock_meta.json. Numeros inventados; "
        "nomes e classes dos herois sao reais."
    )

    def __init__(self, data_file: Path | None = None) -> None:
        self._data_file = data_file or DATA_FILE

    @property
    def _data(self) -> dict[str, Any]:
        return _load_dataset(str(self._data_file))

    def current_patch(self) -> str:
        return str(self._data["patch"])

    # -- catalogo -------------------------------------------------------

    def get_heroes(self) -> list[HeroData]:
        return [
            HeroData(
                name=hero["name"],
                slug=hero["slug"],
                role=HeroRole(hero["role"]),
                # Nao ha URL de imagem confiavel para dados mock: preencher
                # isso seria inventar um endpoint de terceiro.
                image_url=None,
            )
            for hero in self._data["heroes"]
        ]

    # -- estatisticas ---------------------------------------------------

    def get_hero_stats(
        self,
        *,
        patch: str | None = None,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> list[HeroStatsData]:
        data = self._data
        target_patch = patch or self.current_patch()
        if target_patch != self.current_patch():
            logger.warning(
                "mock provider nao possui o patch solicitado",
                extra={"requested_patch": target_patch, "available": self.current_patch()},
            )
            return []

        current_at = datetime.fromisoformat(data["collected_at"])
        previous_at = datetime.fromisoformat(data["previous_collected_at"])

        readings: list[HeroStatsData] = []
        for hero in data["heroes"]:
            readings.append(self._build_stats(hero, hero, current_at, target_patch, rank_filter))
            readings.append(
                self._build_stats(hero, hero["previous"], previous_at, target_patch, rank_filter)
            )
        return readings

    @staticmethod
    def _build_stats(
        hero: dict[str, Any],
        values: dict[str, Any],
        collected_at: datetime,
        patch: str,
        rank_filter: RankFilter,
    ) -> HeroStatsData:
        return HeroStatsData(
            hero_slug=hero["slug"],
            win_rate=values["win_rate"],
            pick_rate=values["pick_rate"],
            ban_rate=values["ban_rate"],
            matches=values.get("matches", hero.get("matches")),
            rank_filter=rank_filter,
            patch=patch,
            collected_at=collected_at,
        )

    # -- meta -----------------------------------------------------------

    def get_meta(
        self,
        *,
        lane: Lane | None = None,
        patch: str | None = None,
    ) -> list[MetaEntryData]:
        data = self._data
        target_patch = patch or self.current_patch()
        if target_patch != self.current_patch():
            return []

        current_at = datetime.fromisoformat(data["collected_at"])
        previous_at = datetime.fromisoformat(data["previous_collected_at"])

        entries: list[MetaEntryData] = []
        for hero in data["heroes"]:
            for raw_lane in hero["lanes"]:
                hero_lane = Lane(raw_lane)
                if lane is not None and hero_lane != lane:
                    continue
                entries.append(self._build_entry(hero, hero, hero_lane, current_at, target_patch))
                entries.append(
                    self._build_entry(
                        hero, hero["previous"], hero_lane, previous_at, target_patch
                    )
                )
        return entries

    @staticmethod
    def _build_entry(
        hero: dict[str, Any],
        values: dict[str, Any],
        lane: Lane,
        collected_at: datetime,
        patch: str,
    ) -> MetaEntryData:
        score = calculate_score(values["win_rate"], values["pick_rate"], values["ban_rate"])
        return MetaEntryData(
            hero_slug=hero["slug"],
            lane=lane,
            tier=score_to_tier(score),
            score=score,
            patch=patch,
            collected_at=collected_at,
        )

    # -- relacoes -------------------------------------------------------

    def get_hero_relations(self) -> list[HeroRelationData]:
        """Relacoes ficticias, deterministas, definidas no arquivo de mock."""
        relacoes: list[HeroRelationData] = []
        for hero in self._data["heroes"]:
            for tipo, alvos in (hero.get("relations") or {}).items():
                for alvo in alvos:
                    relacoes.append(
                        HeroRelationData(
                            hero_slug=hero["slug"],
                            related_hero_slug=alvo,
                            relation_type=RelationType(tipo),
                        )
                    )
        return relacoes

    # -- itens e builds -------------------------------------------------

    def get_items(self) -> list[ItemData]:
        return [ItemData(**item) for item in self._data.get("items", [])]

    def get_hero_builds(
        self,
        hero_slug: str,
        lane: Lane,
        *,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> list[HeroBuildData]:
        """Builds ficticias porem deterministas, derivadas do indice do heroi."""
        data = self._data
        herois = data["heroes"]
        indices = {h["slug"]: i for i, h in enumerate(herois)}
        if hero_slug not in indices:
            return []

        heroi = herois[indices[hero_slug]]
        if lane.value not in heroi["lanes"]:
            return []

        itens = [item["external_id"] for item in data.get("items", [])]
        emblemas = data.get("emblems", [])
        feiticos = data.get("battle_spells", [])
        base = indices[hero_slug]
        coletado_em = datetime.fromisoformat(data["collected_at"])

        builds: list[HeroBuildData] = []
        for variante in range(3):
            deslocamento = base + variante
            builds.append(
                HeroBuildData(
                    hero_slug=hero_slug,
                    lane=lane,
                    variant=variante,
                    win_rate=round(min(0.62, heroi["win_rate"] + variante * 0.01), 5),
                    pick_rate=round(max(0.001, heroi["pick_rate"] / (variante + 1)), 5),
                    item_ids=tuple(
                        itens[(deslocamento + i) % len(itens)] for i in range(3)
                    ),
                    emblem=emblemas[deslocamento % len(emblemas)] if emblemas else None,
                    battle_spell=feiticos[deslocamento % len(feiticos)] if feiticos else None,
                    rank_filter=rank_filter,
                    collected_at=coletado_em,
                )
            )
        return builds

    # -- patches --------------------------------------------------------

    def get_patches(self) -> list[PatchData]:
        return [PatchData(**patch) for patch in self._data.get("patches", [])]
