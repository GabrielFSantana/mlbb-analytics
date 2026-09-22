"""Leitura de composicao a partir da sinergia medida entre duplas.

Estrategia de coleta
--------------------
Como as builds, a sinergia e buscada SOB DEMANDA. Cada consulta traz a
linha inteira da matriz de um heroi (hoje 132 parceiros) numa unica
chamada; puxar a matriz completa custaria uma requisicao por heroi do
elenco, numa fonte sem rate limit documentado.

Para um time de N herois precisamos de apenas N-1 consultas: a matriz e
simetrica, entao a linha do ultimo heroi so repetiria pares que os
anteriores ja trouxeram. Ver `app.domain.composicao.pares_necessarios`.

O resultado fica no banco e vale por `SYNERGY_CACHE_HOURS`. Se a fonte
cair, servimos o que ja houver e dizemos que ela estava fora.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import combinations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotSupportedError
from app.core.logging import get_logger
from app.domain.composicao import TOP_POR_LADO, Dupla, classificar, ler_composicao
from app.domain.composicao import pares_necessarios as quantos_consultar
from app.models.hero import Hero
from app.models.hero_synergy import HeroSynergy
from app.providers.factory import get_provider
from app.repositories.hero_repository import HeroRepository
from app.repositories.synergy_repository import HeroSynergyRepository
from app.schemas.composition import CompositionResponse, PairRead
from app.schemas.hero import HeroRead

logger = get_logger(__name__)

#: Teto do time em MLBB. Mais que isso nao e composicao, e lista.
MAX_HEROIS = 5


class CompositionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.heroes = HeroRepository(db)
        self.synergies = HeroSynergyRepository(db)

    def analyze(self, terms: list[str]) -> CompositionResponse:
        """Le uma composicao, ou as melhores duplas de um heroi sozinho."""
        provider = get_provider()
        encontrados, desconhecidos = self._resolver(terms)
        base = CompositionResponse(
            heroes=[HeroRead.model_validate(h) for h in encontrados],
            unknown_terms=desconhecidos,
            source=provider.name,
            is_mock=provider.is_mock,
        )
        if not encontrados:
            return base

        # Com um heroi so, a pergunta muda: nao ha composicao para ler, e
        # sim "com quem este heroi forma boas duplas".
        alvos = encontrados[: quantos_consultar(len(encontrados))] or encontrados[:1]
        fonte_ok = all(self._garantir(hero) for hero in alvos)

        if len(encontrados) == 1:
            pares = self._melhores_duplas(encontrados[0])
        else:
            pares = self._pares_do_time(encontrados)

        leitura = ler_composicao(
            Dupla(a=p.a.slug, b=p.b.slug, delta=p.win_rate_delta) for p in pares
        )
        return base.model_copy(
            update={
                "pairs": pares,
                "favorable": leitura.favoraveis,
                "unfavorable": leitura.desfavoraveis,
                "neutral": leitura.neutras,
                "collected_at": self._coletado_em(alvos[0]),
                "source_available": fonte_ok,
            }
        )

    # -- montagem dos pares ---------------------------------------------

    def _pares_do_time(self, herois: list[Hero]) -> list[PairRead]:
        """Todos os pares possiveis entre os herois informados.

        Uma dupla sem medicao e omitida em vez de virar zero: "nao sabemos"
        e "nao muda nada" sao coisas diferentes.
        """
        ids = [h.id for h in herois]
        por_id = {h.id: h for h in herois}
        medido: dict[tuple[int, int], HeroSynergy] = {}
        for registro in self.synergies.list_between(ids):
            medido[self._chave(registro.hero_id, registro.partner_id)] = registro

        pares: list[PairRead] = []
        for a, b in combinations(herois, 2):
            registro = medido.get(self._chave(a.id, b.id))
            if registro is None:
                continue
            # A ordem de exibicao segue a que a pessoa digitou, nao a que a
            # fonte gravou: o numero e da dupla e vale nos dois sentidos.
            pares.append(
                PairRead(
                    a=HeroRead.model_validate(por_id[a.id]),
                    b=HeroRead.model_validate(por_id[b.id]),
                    win_rate_delta=registro.win_rate_delta,
                    strength=classificar(registro.win_rate_delta),
                    partner_win_rate=registro.partner_win_rate,
                )
            )
        return sorted(pares, key=lambda p: (-p.win_rate_delta, p.a.name, p.b.name))

    def _melhores_duplas(self, hero: Hero) -> list[PairRead]:
        """As duplas mais favoraveis e as mais desfavoraveis deste heroi."""
        registros = self.synergies.list_for_hero(hero.id)
        ordenados = sorted(registros, key=lambda r: r.win_rate_delta, reverse=True)
        melhores = ordenados[:TOP_POR_LADO]
        piores = [r for r in ordenados[-TOP_POR_LADO:] if r not in melhores]

        return [
            PairRead(
                a=HeroRead.model_validate(hero),
                b=HeroRead.model_validate(registro.partner),
                win_rate_delta=registro.win_rate_delta,
                strength=classificar(registro.win_rate_delta),
                partner_win_rate=registro.partner_win_rate,
            )
            for registro in melhores + piores
        ]

    @staticmethod
    def _chave(a: int, b: int) -> tuple[int, int]:
        """Chave independente da direcao: o par e o mesmo nos dois sentidos."""
        return (a, b) if a <= b else (b, a)

    # -- coleta ----------------------------------------------------------

    def _garantir(self, hero: Hero) -> bool:
        """Busca a linha do heroi se o cache venceu. False se a fonte falhou."""
        if not self._precisa_atualizar(hero.id):
            return True

        provider = get_provider()
        try:
            duplas = provider.get_hero_allies(hero.slug)
        except ProviderNotSupportedError:
            logger.info("provider nao fornece sinergia", extra={"provider": provider.name})
            return False
        except ProviderError as exc:
            logger.warning(
                "falha ao consultar sinergia; servindo dado anterior se houver",
                extra={"hero": hero.slug, "error": str(exc)},
            )
            return False

        por_slug = self.heroes.slug_index()
        registros: list[HeroSynergy] = []
        for dupla in duplas:
            parceiro = por_slug.get(dupla.partner_slug)
            if parceiro is None:
                # Heroi que a fonte conhece e nos ainda nao: ignoramos em vez
                # de criar um registro orfao. A sincronizacao resolve.
                continue
            registros.append(
                HeroSynergy(
                    hero_id=hero.id,
                    partner_id=parceiro.id,
                    win_rate_delta=dupla.win_rate_delta,
                    partner_win_rate=dupla.partner_win_rate,
                    source=provider.name,
                    collected_at=dupla.collected_at,
                )
            )

        self.synergies.replace_for_hero(hero.id, registros)
        self.db.commit()
        logger.info(
            "sinergia atualizada", extra={"hero": hero.slug, "duplas": len(registros)}
        )
        return True

    def _precisa_atualizar(self, hero_id: int) -> bool:
        buscado_em = self.synergies.last_refreshed_at(hero_id)
        if buscado_em is None:
            return True
        return buscado_em < datetime.now(UTC) - timedelta(hours=settings.synergy_cache_hours)

    def _coletado_em(self, hero: Hero) -> datetime | None:
        registros = self.synergies.list_for_hero(hero.id)
        return registros[0].collected_at if registros else None

    def _resolver(self, termos: list[str]) -> tuple[list[Hero], list[str]]:
        """Traduz nomes digitados em herois, reportando o que nao casou."""
        encontrados: list[Hero] = []
        desconhecidos: list[str] = []
        vistos: set[int] = set()

        for termo in termos[:MAX_HEROIS]:
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
