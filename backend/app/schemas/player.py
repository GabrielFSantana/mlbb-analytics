"""Schemas de jogadores e da meta de estrelas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class StarReport(BaseModel):
    """Um reporte de estrelas vindo do bot."""

    discord_user_id: int
    display_name: str = Field(max_length=100)
    stars: int = Field(ge=0, le=2000, description="Estrelas atuais, auto-reportadas.")
    note: str | None = Field(default=None, max_length=200)
    game_player_id: str | None = Field(default=None, max_length=32)
    game_server_id: str | None = Field(default=None, max_length=32)


class PlayerProgress(BaseModel):
    """Onde um jogador esta em relacao a meta."""

    display_name: str
    discord_user_id: int
    stars: int
    percent: float
    reported_at: datetime
    #: Variacao na janela recente. None quando ha so um reporte.
    stars_gained: int | None = None
    days_measured: float | None = None
    stars_per_day: float | None = None
    projected_at: datetime | None = Field(
        default=None,
        description=(
            "Estimativa de quando a meta seria atingida mantendo o ritmo. None "
            "quando nao ha historico suficiente - projetar com duas leituras "
            "proximas produz numero sem significado."
        ),
    )
    reached: bool = False


class TeamProgress(BaseModel):
    """Visao do time rumo a meta."""

    goal: int
    players: list[PlayerProgress] = Field(default_factory=list)
    total_stars: int = 0
    average_stars: float = 0.0
    players_reached: int = 0
    #: Estrelas que o time somou na janela, considerando quem tem historico.
    team_stars_gained: int | None = None
    window_days: int = 7
    self_reported: bool = Field(
        default=True,
        description=(
            "Sempre true: estes numeros sao informados pelos proprios jogadores, "
            "nao lidos do jogo. A interface precisa deixar isso claro."
        ),
    )


class PlayerWeeklyDelta(BaseModel):
    """Quanto um jogador andou na semana."""

    display_name: str
    discord_user_id: int
    stars_start: int
    stars_end: int
    stars_gained: int
    reports: int = Field(description="Quantas vezes reportou na semana.")
    reached: bool = False
    crossed_goal: bool = Field(
        default=False, description="Cruzou a meta justamente nesta semana."
    )


class WeeklyRanking(BaseModel):
    """Resumo da semana fechada."""

    week_label: str = Field(description="Ano e semana ISO, ex.: 2026-W38.")
    week_start: date
    week_end: date
    goal: int
    movers: list[PlayerWeeklyDelta] = Field(default_factory=list)
    team_stars_gained: int = 0
    players_reported: int = 0
    self_reported: bool = True


class WeeklyRankingAck(BaseModel):
    week_label: str
