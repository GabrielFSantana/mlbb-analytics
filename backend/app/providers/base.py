"""Contrato unico para qualquer fonte de dados de MLBB.

Por que essa abstracao existe
-----------------------------
A Moonton nao publica uma API oficial adequada a esse tipo de aplicacao.
Qualquer fonte que venhamos a usar sera de terceiros, comunitaria ou de
cadastro manual - e portanto instavel. Services, API e bot conversam apenas
com esta interface, de modo que trocar a fonte nao propague mudancas para
o resto do sistema.

Implementacoes previstas:

* `MockDataProvider`      - dados de demonstracao (unica disponivel hoje).
* `ManualDataProvider`    - dados cadastrados por nos.
* `CommunityAPIProvider`  - fonte comunitaria, se e quando uma for aprovada.
* `OfficialProvider`      - caso uma API oficial passe a existir.

Capacidades nao suportadas devem levantar `ProviderNotSupportedError` em vez
de retornar dados vazios, para que a diferenca entre "nao ha dado" e "essa
fonte nao sabe responder isso" seja explicita.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from app.core.exceptions import ProviderNotSupportedError
from app.models.enums import Lane, RankFilter
from app.providers.schemas import (
    HeroData,
    HeroStatsData,
    MatchData,
    MetaEntryData,
    PatchData,
    PlayerData,
)


class MLBBDataProvider(ABC):
    """Interface de leitura de dados de MLBB."""

    #: Identificador curto, gravado junto dos dados para rastreabilidade.
    name: ClassVar[str]

    #: True quando os dados sao ficticios. A API e o bot sinalizam isso ao
    #: usuario final; nunca apresente dado mock como se fosse real.
    is_mock: ClassVar[bool] = False

    #: Documentacao da origem: URL, contrato ou "cadastro manual".
    source_description: ClassVar[str] = "nao documentada"

    @abstractmethod
    def get_heroes(self) -> list[HeroData]:
        """Catalogo de herois conhecido pela fonte."""

    @abstractmethod
    def get_hero_stats(
        self,
        *,
        patch: str | None = None,
        rank_filter: RankFilter = RankFilter.ALL,
    ) -> list[HeroStatsData]:
        """Win/pick/ban rate. `patch=None` significa o patch corrente da fonte."""

    @abstractmethod
    def get_meta(
        self,
        *,
        lane: Lane | None = None,
        patch: str | None = None,
    ) -> list[MetaEntryData]:
        """Tier list por lane. `lane=None` retorna todas as lanes."""

    def get_patches(self) -> list[PatchData]:
        """Patches conhecidos. Opcional."""
        raise ProviderNotSupportedError(f"{self.name} nao fornece patches")

    # ------------------------------------------------------------------
    # Fase 4 - Player Tracking / Match History.
    # Declarados aqui para fixar o contrato; nenhuma fonte os implementa.
    # ------------------------------------------------------------------

    def get_player(self, player_id: str, server_id: str) -> PlayerData:
        raise ProviderNotSupportedError(f"{self.name} nao fornece dados de jogador")

    def get_matches(self, player_id: str, server_id: str, *, limit: int = 20) -> list[MatchData]:
        raise ProviderNotSupportedError(f"{self.name} nao fornece historico de partidas")
