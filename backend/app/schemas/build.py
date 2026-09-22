"""Schemas de builds."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.models.enums import Lane
from app.schemas.hero import HeroRead


class BuildItemRead(BaseModel):
    name: str
    image_url: str | None = None
    position: int


class HeroBuildRead(BaseModel):
    """Uma variante de build.

    `items` traz apenas os itens CENTRAIS publicados pela fonte, nao uma
    build fechada de seis.
    """

    variant: int
    win_rate: float = Field(description="Fracao (0.0-1.0).")
    pick_rate: float
    emblem: str | None = None
    battle_spell: str | None = None
    talents: str | None = Field(
        default=None,
        description=(
            "Talentos do emblema, ja em texto. Na fonte atual, variantes com "
            "os mesmos itens costumam diferir so aqui."
        ),
    )
    items: list[BuildItemRead] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def win_rate_pct(self) -> float:
        return round(self.win_rate * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pick_rate_pct(self) -> float:
        return round(self.pick_rate * 100, 2)


class CommunityBuildItemRead(BaseModel):
    """Um item da build completa, com a contagem que o colocou ali."""

    name: str
    image_url: str | None = None
    position: int
    builds: int = Field(description="Em quantas builds da comunidade este item aparece.")
    share: float = Field(description="Fracao (0.0-1.0) das builds consideradas.")
    in_core: bool = Field(
        default=False,
        description="True quando a estatistica de partidas tambem lista este item.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def share_pct(self) -> float:
        return round(self.share * 100, 1)


class CommunityBuildRead(BaseModel):
    """Build fechada de seis itens, agregada dos guias de jogadores.

    ATENCAO ao apresentar: aqui NAO existe taxa de vitoria. `share` e
    frequencia de citacao. Tratar um pelo outro seria inventar desempenho
    que ninguem mediu.

    Tambem nao e separada por lane: os guias do patch atual sao poucas
    dezenas por heroi e dividi-los deixaria a maioria das lanes sem amostra.
    """

    items: list[CommunityBuildItemRead] = Field(default_factory=list)
    builds_considered: int = Field(
        description="Denominador das porcentagens. Sem ele, '76%' nao diz nada."
    )
    patch: str | None = None
    collected_at: datetime | None = None


class HeroBuildsResponse(BaseModel):
    hero: HeroRead
    lane: Lane | None = None
    builds: list[HeroBuildRead] = Field(default_factory=list)
    community: CommunityBuildRead | None = Field(
        default=None,
        description=(
            "Build completa vinda dos guias da comunidade. None quando nao ha "
            "material suficiente no patch atual para que a contagem signifique "
            "alguma coisa."
        ),
    )
    collected_at: datetime | None = None
    source: str
    is_mock: bool = False
    source_available: bool = Field(
        default=True,
        description=(
            "False quando precisavamos consultar a fonte e ela falhou. Sem isso, "
            "uma lista vazia por indisponibilidade seria indistinguivel de uma "
            "lista vazia por nao existir build - e o usuario leria a mensagem errada."
        ),
    )
