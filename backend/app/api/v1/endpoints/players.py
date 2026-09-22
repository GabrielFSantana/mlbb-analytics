"""Endpoints de jogadores e da meta de estrelas."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import PlayerServiceDep
from app.schemas.player import PlayerProgress, StarReport, TeamProgress

router = APIRouter(prefix="/players", tags=["players"])


@router.post(
    "/stars",
    response_model=PlayerProgress,
    status_code=status.HTTP_201_CREATED,
    summary="Registra um reporte de estrelas",
)
def report_stars(report: StarReport, service: PlayerServiceDep) -> PlayerProgress:
    """Grava a leitura e devolve o progresso atualizado do jogador.

    Os numeros sao informados pelo proprio jogador: a Moonton nao expoe
    estatisticas de conta sem autenticacao. Cada reporte vira uma linha, e o
    historico e o que permite medir ritmo.
    """
    return service.report_stars(report)


@router.get("/progress", response_model=TeamProgress, summary="Progresso do time")
def team_progress(
    service: PlayerServiceDep,
    goal: int | None = Query(default=None, ge=1, le=2000, description="Meta de estrelas."),
    window_days: int = Query(default=7, ge=1, le=90, description="Janela do ritmo, em dias."),
) -> TeamProgress:
    return service.team_progress(goal=goal, window_days=window_days)
