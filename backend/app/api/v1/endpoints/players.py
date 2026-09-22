"""Endpoints de jogadores e da meta de estrelas."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import PlayerServiceDep, WeeklyRankingServiceDep
from app.schemas.player import (
    PlayerProgress,
    StarReport,
    TeamProgress,
    WeeklyRanking,
    WeeklyRankingAck,
)

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


@router.get(
    "/weekly-ranking/pending",
    response_model=WeeklyRanking | None,
    summary="Ranking semanal ainda nao publicado",
)
def pending_weekly_ranking(
    service: WeeklyRankingServiceDep,
    goal: int | None = Query(default=None, ge=1, le=2000),
) -> WeeklyRanking | None:
    """Usado pelo bot. `null` quando ja publicamos ou ninguem reportou."""
    return service.pending_ranking(goal=goal)


@router.post(
    "/weekly-ranking/ack",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirma que o ranking semanal foi publicado",
)
def ack_weekly_ranking(payload: WeeklyRankingAck, service: WeeklyRankingServiceDep) -> None:
    service.mark_announced(payload.week_label)
