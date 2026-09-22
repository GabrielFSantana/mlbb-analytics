"""Sincronizacao: provider -> banco.

Este e o unico ponto da aplicacao que escreve dados vindos de uma fonte
externa. O job periodico da Fase 2 chamara exatamente este servico.

A escrita e idempotente: uma leitura ja gravada (mesmo heroi, patch, ranque e
`collected_at`) e ignorada, entao rodar a sincronizacao duas vezes nao
duplica historico.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.exceptions import ProviderNotSupportedError
from app.core.logging import get_logger
from app.models.enums import RankFilter
from app.models.hero_relation import HeroRelation
from app.models.hero_stats import HeroStats
from app.models.meta_snapshot import MetaSnapshot
from app.providers.base import MLBBDataProvider
from app.providers.factory import get_provider
from app.repositories.build_repository import ItemRepository
from app.repositories.hero_repository import HeroRepository
from app.repositories.meta_repository import MetaRepository
from app.repositories.patch_repository import PatchRepository
from app.repositories.relation_repository import HeroRelationRepository
from app.repositories.stats_repository import HeroStatsRepository

logger = get_logger(__name__)

#: Faixas coletadas por padrao. `ALL` e o agregado; as demais permitem
#: responder "como esta o meta no MEU ranque", que e a pergunta real.
DEFAULT_RANK_FILTERS: tuple[RankFilter, ...] = (
    RankFilter.ALL,
    RankFilter.EPIC,
    RankFilter.LEGEND,
    RankFilter.MYTHIC,
    RankFilter.HONOR,
    RankFilter.GLORY,
)


@dataclass(slots=True)
class SyncResult:
    """Resumo do que a sincronizacao gravou."""

    provider: str
    heroes: int = 0
    stats: int = 0
    meta_snapshots: int = 0
    patches: int = 0
    relations: int = 0
    items: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "heroes": self.heroes,
            "stats": self.stats,
            "meta_snapshots": self.meta_snapshots,
            "patches": self.patches,
            "relations": self.relations,
            "items": self.items,
            "skipped": self.skipped,
            "warnings": self.warnings,
        }


class SyncService:
    def __init__(self, db: Session, provider: MLBBDataProvider | None = None) -> None:
        self.db = db
        self.provider = provider or get_provider()
        self.heroes = HeroRepository(db)
        self.stats = HeroStatsRepository(db)
        self.meta = MetaRepository(db)
        self.patches = PatchRepository(db)
        self.relations = HeroRelationRepository(db)
        self.items = ItemRepository(db)

    def sync_all(
        self,
        *,
        rank_filters: tuple[RankFilter, ...] = DEFAULT_RANK_FILTERS,
    ) -> SyncResult:
        """Importa catalogo, patches, estatisticas e meta em uma transacao.

        Uma coleta por faixa de ranque: o meta em Gloria e bem diferente do
        agregado geral, e o custo e uma requisicao por faixa por dia.
        """
        result = SyncResult(provider=self.provider.name)

        self._sync_heroes(result)
        self.db.flush()  # garante ids dos herois novos antes dos FKs abaixo

        self._sync_patches(result)
        index = self.heroes.slug_index()
        for rank_filter in rank_filters:
            self._sync_stats(result, index, rank_filter)
            self._sync_meta(result, index, rank_filter)
        self._sync_relations(result, index)
        self._sync_items(result)

        self.db.commit()
        logger.info("sincronizacao concluida", extra=result.as_dict())
        return result

    # -- etapas ---------------------------------------------------------

    def _sync_heroes(self, result: SyncResult) -> None:
        for hero_data in self.provider.get_heroes():
            self.heroes.upsert(
                name=hero_data.name,
                slug=hero_data.slug,
                role=hero_data.role,
                image_url=hero_data.image_url,
            )
            result.heroes += 1

    def _sync_patches(self, result: SyncResult) -> None:
        try:
            patches = self.provider.get_patches()
        except ProviderNotSupportedError:
            result.warnings.append(f"{self.provider.name} nao fornece patches")
            return
        for patch_data in patches:
            self.patches.upsert(
                version=patch_data.version,
                released_at=patch_data.released_at,
                notes_url=patch_data.notes_url,
                summary=patch_data.summary,
                is_current=patch_data.is_current,
            )
            result.patches += 1

    def _sync_stats(
        self,
        result: SyncResult,
        index: dict[str, object],
        rank_filter: RankFilter,
    ) -> None:
        for reading in self.provider.get_hero_stats(rank_filter=rank_filter):
            hero = index.get(reading.hero_slug)
            if hero is None:
                result.warnings.append(f"stats de heroi desconhecido: {reading.hero_slug}")
                continue
            hero_id = hero.id  # type: ignore[attr-defined]
            if self.stats.exists(
                hero_id=hero_id,
                patch=reading.patch,
                rank_filter=reading.rank_filter,
                collected_at=reading.collected_at,
            ):
                result.skipped += 1
                continue
            self.stats.add(
                HeroStats(
                    hero_id=hero_id,
                    win_rate=reading.win_rate,
                    pick_rate=reading.pick_rate,
                    ban_rate=reading.ban_rate,
                    matches=reading.matches,
                    rank_filter=reading.rank_filter,
                    patch=reading.patch,
                    collected_at=reading.collected_at,
                    source=self.provider.name,
                )
            )
            result.stats += 1

    def _sync_items(self, result: SyncResult) -> None:
        """Catalogo de itens: uma chamada, necessaria para nomear as builds."""
        try:
            itens = self.provider.get_items()
        except ProviderNotSupportedError:
            result.warnings.append(f"{self.provider.name} nao fornece itens")
            return
        for item in itens:
            self.items.upsert(
                external_id=item.external_id,
                name=item.name,
                image_url=item.image_url,
                source=self.provider.name,
            )
            result.items += 1

    def _sync_relations(self, result: SyncResult, index: dict[str, object]) -> None:
        try:
            dados = self.provider.get_hero_relations()
        except ProviderNotSupportedError:
            result.warnings.append(f"{self.provider.name} nao fornece relacoes")
            return

        arestas: list[HeroRelation] = []
        vistas: set[tuple[int, int, str]] = set()
        for relacao in dados:
            heroi = index.get(relacao.hero_slug)
            alvo = index.get(relacao.related_hero_slug)
            if heroi is None or alvo is None:
                result.warnings.append(
                    f"relacao com heroi desconhecido: "
                    f"{relacao.hero_slug} -> {relacao.related_hero_slug}"
                )
                continue
            chave = (
                heroi.id,  # type: ignore[attr-defined]
                alvo.id,  # type: ignore[attr-defined]
                relacao.relation_type.value,
            )
            # A fonte pode repetir a mesma aresta; a constraint unica
            # rejeitaria o lote inteiro.
            if chave in vistas:
                continue
            vistas.add(chave)
            arestas.append(
                HeroRelation(
                    hero_id=chave[0],
                    related_hero_id=chave[1],
                    relation_type=relacao.relation_type,
                    source=self.provider.name,
                )
            )

        result.relations = self.relations.replace_for_source(self.provider.name, arestas)

    def _sync_meta(
        self,
        result: SyncResult,
        index: dict[str, object],
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> None:
        for entry in self.provider.get_meta(rank_filter=rank_filter):
            hero = index.get(entry.hero_slug)
            if hero is None:
                result.warnings.append(f"meta de heroi desconhecido: {entry.hero_slug}")
                continue
            hero_id = hero.id  # type: ignore[attr-defined]
            if self.meta.exists(
                hero_id=hero_id,
                lane=entry.lane,
                rank_filter=entry.rank_filter,
                patch=entry.patch,
                collected_at=entry.collected_at,
            ):
                result.skipped += 1
                continue
            self.meta.add(
                MetaSnapshot(
                    hero_id=hero_id,
                    lane=entry.lane,
                    rank_filter=entry.rank_filter,
                    tier=entry.tier,
                    score=entry.score,
                    patch=entry.patch,
                    collected_at=entry.collected_at,
                    source=self.provider.name,
                )
            )
            result.meta_snapshots += 1
