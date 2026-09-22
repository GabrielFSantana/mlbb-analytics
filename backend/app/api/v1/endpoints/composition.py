"""Endpoint da leitura de composicao."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CompositionServiceDep
from app.schemas.composition import CompositionResponse

router = APIRouter(prefix="/composition", tags=["composition"])


@router.get(
    "",
    response_model=CompositionResponse,
    summary="Le uma composicao pela sinergia medida entre as duplas",
)
def analyze(
    service: CompositionServiceDep,
    hero: list[str] = Query(
        default=[],
        description=(
            "Herois do time, ate cinco. Repita o parametro. Com um heroi so, "
            "devolve as melhores e as piores duplas dele."
        ),
    ),
) -> CompositionResponse:
    """Quanto cada dupla desloca a taxa de vitoria, segundo a fonte.

    O numero pertence a DUPLA: a matriz da fonte e simetrica, entao nao ha
    "quem ajuda quem". Duplas sem efeito mensuravel (metade dos pares) sao
    contadas em `neutral` e nao viram afirmacao.

    Nao existe nota geral da composicao de proposito: efeito de par nao e
    aditivo, e somar produziria uma previsao que ninguem mediu.
    """
    return service.analyze(hero)
