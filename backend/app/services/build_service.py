"""Builds recomendadas por heroi.

Estrategia de coleta
--------------------
As builds sao buscadas SOB DEMANDA, e nao na coleta diaria. Buscar o elenco
inteiro custaria uma requisicao por heroi e por lane - hoje passaria de 200
por execucao, numa fonte comunitaria sem rate limit documentado. Puxando so
quando alguem pergunta, gastamos requisicao apenas com os herois que as
pessoas realmente consultam.

O resultado fica no banco e e reaproveitado enquanto for mais novo que
`BUILDS_CACHE_HOURS`. Se a fonte cair, servimos o ultimo dado conhecido em
vez de falhar - dizendo quando ele foi coletado.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ProviderError, ProviderNotSupportedError
from app.core.logging import get_logger
from app.models.enums import Lane, RankFilter
from app.models.hero import Hero
from app.models.hero_build import HeroBuild, HeroBuildItem
from app.providers.factory import get_provider
from app.repositories.build_repository import HeroBuildRepository, ItemRepository
from app.repositories.hero_repository import HeroRepository
from app.repositories.meta_repository import MetaRepository
from app.schemas.build import BuildItemRead, HeroBuildRead, HeroBuildsResponse
from app.schemas.hero import HeroRead

logger = get_logger(__name__)


class BuildService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.heroes = HeroRepository(db)
        self.builds = HeroBuildRepository(db)
        self.items = ItemRepository(db)
        self.meta = MetaRepository(db)

    def get_builds(
        self,
        term: str,
        *,
        lane: Lane | None = None,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> HeroBuildsResponse:
        hero = self._find_hero(term)
        alvo = lane or self._default_lane(hero.id)
        if alvo is None:
            provider = get_provider()
            return HeroBuildsResponse(
                hero=HeroRead.model_validate(hero),
                lane=None,
                builds=[],
                source=provider.name,
                is_mock=provider.is_mock,
            )

        fonte_ok = True
        if self._precisa_atualizar(hero.id, alvo, rank_filter):
            fonte_ok = self._refresh(hero, alvo, rank_filter)

        registros = self.builds.list_for_hero_lane(hero.id, alvo, rank_filter=rank_filter)
        provider = get_provider()
        return HeroBuildsResponse(
            hero=HeroRead.model_validate(hero),
            lane=alvo,
            builds=[self._to_read(registro) for registro in registros],
            collected_at=registros[0].collected_at if registros else None,
            source=registros[0].source if registros else provider.name,
            is_mock=provider.is_mock,
            source_available=fonte_ok,
        )

    # -- helpers --------------------------------------------------------

    def _find_hero(self, term: str) -> Hero:
        normalized = term.strip().lower().replace(" ", "-")
        hero = self.heroes.get_by_slug(normalized) or self.heroes.get_by_name(term)
        if hero is None:
            raise NotFoundError("heroi", term)
        return hero

    def _default_lane(self, hero_id: int) -> Lane | None:
        """Lane onde o heroi esta mais forte na coleta mais recente.

        Sem isso, `/build <heroi>` teria de exigir a lane mesmo quando o
        heroi joga em uma so.
        """
        fonte = self.meta.latest_source()
        ultima = self.meta.latest_collected_at(source=fonte)
        if ultima is None:
            return None
        posicoes = [
            snapshot
            for snapshot in self.meta.list_at(ultima, source=fonte, with_hero=False)
            if snapshot.hero_id == hero_id
        ]
        if not posicoes:
            return None
        return max(posicoes, key=lambda s: s.score).lane

    def _precisa_atualizar(self, hero_id: int, lane: Lane, rank_filter: RankFilter) -> bool:
        buscado_em = self.builds.last_refreshed_at(hero_id, lane, rank_filter=rank_filter)
        if buscado_em is None:
            return True
        limite = datetime.now(UTC) - timedelta(hours=settings.builds_cache_hours)
        return buscado_em < limite

    def _refresh(self, hero: Hero, lane: Lane, rank_filter: RankFilter) -> bool:
        """Busca na fonte e grava.

        Devolve False quando a fonte falhou, para quem chamou nao confundir
        "nao existe build" com "nao consegui perguntar". A falha nunca vira
        erro na cara do usuario: servimos o que ja houver.
        """
        provider = get_provider()
        try:
            dados = provider.get_hero_builds(hero.slug, lane, rank_filter=rank_filter)
        except ProviderNotSupportedError:
            logger.info(
                "provider nao fornece builds", extra={"provider": provider.name}
            )
            return False
        except ProviderError as exc:
            logger.warning(
                "falha ao consultar builds na fonte; servindo dado anterior se houver",
                extra={"hero": hero.slug, "lane": lane.value, "error": str(exc)},
            )
            return False

        indice = self.items.index_by_external_id()
        registros: list[HeroBuild] = []
        for build in dados:
            registro = HeroBuild(
                hero_id=hero.id,
                lane=build.lane,
                rank_filter=build.rank_filter,
                variant=build.variant,
                win_rate=build.win_rate,
                pick_rate=build.pick_rate,
                emblem=build.emblem,
                battle_spell=build.battle_spell,
                source=provider.name,
                collected_at=build.collected_at,
            )
            for posicao, external_id in enumerate(build.item_ids):
                item = indice.get(external_id)
                if item is None:
                    # Item fora do catalogo: ignoramos a posicao em vez de
                    # inventar um nome para ele.
                    logger.warning(
                        "item desconhecido em build; ignorado",
                        extra={"hero": hero.slug, "item_external_id": external_id},
                    )
                    continue
                registro.items.append(
                    HeroBuildItem(item_id=item.id, position=posicao)
                )
            registros.append(registro)

        self.builds.replace_for_hero_lane(hero.id, lane, rank_filter, registros)
        self.db.commit()
        logger.info(
            "builds atualizadas",
            extra={"hero": hero.slug, "lane": lane.value, "builds": len(registros)},
        )
        return True

    @staticmethod
    def _to_read(build: HeroBuild) -> HeroBuildRead:
        return HeroBuildRead(
            variant=build.variant,
            win_rate=build.win_rate,
            pick_rate=build.pick_rate,
            emblem=build.emblem,
            battle_spell=build.battle_spell,
            items=[
                BuildItemRead(
                    name=elo.item.name,
                    image_url=elo.item.image_url,
                    position=elo.position,
                )
                for elo in build.items
            ],
        )
