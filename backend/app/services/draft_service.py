"""Assistente de draft: o que pegar contra o que o inimigo ja pegou.

Combina tres coisas que ja temos no banco - meta por lane/ranque, relacoes
de counter e sinergias - numa recomendacao explicavel. A heuristica em si
mora em `app.domain.draft`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.domain.draft import SinalDeDraft, calcular_score_de_draft
from app.models.enums import Lane, RankFilter, RelationType
from app.models.hero import Hero
from app.models.hero_relation import HeroRelation
from app.providers.factory import get_provider
from app.repositories.hero_repository import HeroRepository
from app.repositories.meta_repository import MetaRepository
from app.schemas.draft import DraftCandidate, DraftResponse
from app.schemas.hero import HeroRead

logger = get_logger(__name__)

#: Quantas sugestoes devolver. Mais que isso vira lista para ninguem ler.
MAX_SUGESTOES = 5


class DraftService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.heroes = HeroRepository(db)
        self.meta = MetaRepository(db)

    def suggest(
        self,
        *,
        enemies: list[str],
        allies: list[str] | None = None,
        lane: Lane | None = None,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> DraftResponse:
        provider = get_provider()
        inimigos, desconhecidos = self._resolver(enemies)
        aliados, desconhecidos_aliados = self._resolver(allies or [])
        desconhecidos += desconhecidos_aliados

        fonte = self.meta.latest_source()
        ultima = self.meta.latest_collected_at(source=fonte, rank_filter=rank_filter)
        if ultima is None:
            return DraftResponse(
                enemies=[HeroRead.model_validate(h) for h in inimigos],
                allies=[HeroRead.model_validate(h) for h in aliados],
                lane=lane,
                rank_filter=rank_filter,
                unknown_terms=desconhecidos,
                source=provider.name,
                is_mock=provider.is_mock,
            )

        snapshots = self.meta.list_at(ultima, lane=lane, source=fonte, rank_filter=rank_filter)
        indisponiveis = {h.id for h in inimigos} | {h.id for h in aliados}

        contra, a_favor, sinergia = self._mapas_de_relacao()
        ids_inimigos = [h.id for h in inimigos]
        ids_aliados = [h.id for h in aliados]
        por_id = {h.id: h for h in inimigos + aliados}

        candidatos: list[DraftCandidate] = []
        for snapshot in snapshots:
            # Nao sugerir quem ja esta em campo, dos dois lados.
            if snapshot.hero_id in indisponiveis:
                continue

            countera = [
                inimigo
                for inimigo in ids_inimigos
                if inimigo in contra.get(snapshot.hero_id, set())
                or snapshot.hero_id in a_favor.get(inimigo, set())
            ]
            counterado = [
                inimigo
                for inimigo in ids_inimigos
                if inimigo in a_favor.get(snapshot.hero_id, set())
                or snapshot.hero_id in contra.get(inimigo, set())
            ]
            combina = [
                aliado
                for aliado in ids_aliados
                if aliado in sinergia.get(snapshot.hero_id, set())
                or snapshot.hero_id in sinergia.get(aliado, set())
            ]

            sinal = SinalDeDraft(
                meta_score=snapshot.score,
                countera=countera,
                counterado_por=counterado,
                sinergias=combina,
            )
            candidatos.append(
                DraftCandidate(
                    hero=HeroRead.model_validate(snapshot.hero),
                    lane=snapshot.lane,
                    tier=snapshot.tier,
                    meta_score=snapshot.score,
                    draft_score=calcular_score_de_draft(sinal),
                    counters=[HeroRead.model_validate(por_id[i]) for i in countera],
                    countered_by=[HeroRead.model_validate(por_id[i]) for i in counterado],
                    synergies=[HeroRead.model_validate(por_id[i]) for i in combina],
                )
            )

        # Duas perguntas diferentes, duas listas:
        #   "o que e bom pegar agora?"  -> ordenado pelo score final
        #   "o que countera o inimigo?" -> ordenado pela vantagem de counter
        melhores = sorted(candidatos, key=lambda c: c.draft_score, reverse=True)
        counters = sorted(
            (c for c in candidatos if len(c.counters) > len(c.countered_by)),
            key=lambda c: (len(c.counters) - len(c.countered_by), c.meta_score),
            reverse=True,
        )

        return DraftResponse(
            enemies=[HeroRead.model_validate(h) for h in inimigos],
            allies=[HeroRead.model_validate(h) for h in aliados],
            lane=lane,
            rank_filter=rank_filter,
            suggestions=melhores[:MAX_SUGESTOES],
            counter_picks=counters[:MAX_SUGESTOES],
            unknown_terms=desconhecidos,
            collected_at=ultima,
            patch=snapshots[0].patch if snapshots else None,
            source=fonte or provider.name,
            is_mock=provider.is_mock,
        )

    # -- helpers --------------------------------------------------------

    def _resolver(self, termos: list[str]) -> tuple[list[Hero], list[str]]:
        """Traduz nomes digitados em herois, reportando o que nao casou."""
        encontrados: list[Hero] = []
        desconhecidos: list[str] = []
        vistos: set[int] = set()

        for termo in termos:
            limpo = termo.strip()
            if not limpo:
                continue
            slug = limpo.lower().replace(" ", "-")
            hero = self.heroes.get_by_slug(slug) or self.heroes.get_by_name(limpo)
            if hero is None:
                desconhecidos.append(limpo)
            elif hero.id not in vistos:
                vistos.add(hero.id)
                encontrados.append(hero)
        return encontrados, desconhecidos

    def _mapas_de_relacao(
        self,
    ) -> tuple[dict[int, set[int]], dict[int, set[int]], dict[int, set[int]]]:
        """Carrega o grafo de relacoes em memoria.

        Sao poucas centenas de arestas: uma consulta unica sai mais barata
        que uma por candidato, e o grafo inteiro cabe folgado na memoria.
        """
        contra: dict[int, set[int]] = {}
        a_favor: dict[int, set[int]] = {}
        sinergia: dict[int, set[int]] = {}

        destinos = {
            RelationType.STRONG: contra,
            RelationType.WEAK: a_favor,
            RelationType.ASSIST: sinergia,
        }
        for relacao in self.db.scalars(select(HeroRelation)):
            destino = destinos.get(relacao.relation_type)
            if destino is not None:
                destino.setdefault(relacao.hero_id, set()).add(relacao.related_hero_id)
        return contra, a_favor, sinergia
