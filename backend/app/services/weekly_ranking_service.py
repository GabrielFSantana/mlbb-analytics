"""Ranking semanal de estrelas do time.

Responde "quem mais subiu na semana", a partir dos reportes que os proprios
jogadores fizeram. Usa o mesmo mecanismo de publicacao exatamente-uma-vez do
update de meta: o backend calcula e marca, o bot publica e confirma.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.semana import periodo_legivel, rotulo_iso, semana_anterior
from app.models.announcement import AnnouncementKind
from app.models.player import Player, StarSnapshot
from app.repositories.announcement_repository import AnnouncementRepository
from app.schemas.player import PlayerWeeklyDelta, WeeklyRanking

logger = get_logger(__name__)

#: Quantos jogadores aparecem no destaque. O resto entra no total do time.
TOP_DESTAQUES = 10


class WeeklyRankingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.anuncios = AnnouncementRepository(db)

    def pending_ranking(self, *, goal: int | None = None) -> WeeklyRanking | None:
        """Ranking da semana fechada, se ainda nao foi publicado.

        Devolve None quando ja publicamos, ou quando ninguem reportou nada
        na semana - um canal que recebe "ninguem jogou" toda segunda vira
        ruido que as pessoas passam a ignorar.
        """
        inicio, fim = semana_anterior(datetime.now(UTC))
        referencia = rotulo_iso(inicio)

        if self.anuncios.was_announced(AnnouncementKind.WEEKLY_RANKING, referencia):
            return None

        ranking = self.build_ranking(inicio, fim, goal=goal)
        if not ranking.movers:
            # Marcamos mesmo sem publicar, para nao recalcular a cada poll.
            self.mark_announced(referencia)
            logger.info("semana sem reportes; nada a publicar", extra={"semana": referencia})
            return None
        return ranking

    def build_ranking(
        self,
        inicio: datetime,
        fim: datetime,
        *,
        goal: int | None = None,
    ) -> WeeklyRanking:
        meta = goal or settings.team_star_goal
        jogadores = list(
            self.db.scalars(select(Player).options(selectinload(Player.snapshots)))
        )

        movimentos: list[PlayerWeeklyDelta] = []
        for jogador in jogadores:
            na_semana = [
                s for s in jogador.snapshots if inicio <= s.reported_at < fim
            ]
            if not na_semana:
                # Sem reporte na semana nao ha o que afirmar: dizer que ficou
                # parado seria inventar um dado que ninguem deu.
                continue

            fim_semana = max(na_semana, key=lambda s: s.reported_at)
            base = self._base_anterior(jogador.snapshots, inicio) or min(
                na_semana, key=lambda s: s.reported_at
            )

            movimentos.append(
                PlayerWeeklyDelta(
                    display_name=jogador.display_name,
                    discord_user_id=jogador.discord_user_id,
                    stars_start=base.stars,
                    stars_end=fim_semana.stars,
                    stars_gained=fim_semana.stars - base.stars,
                    reports=len(na_semana),
                    reached=fim_semana.stars >= meta,
                    crossed_goal=base.stars < meta <= fim_semana.stars,
                )
            )

        movimentos.sort(key=lambda m: (m.stars_gained, m.stars_end), reverse=True)
        inicio_dia, fim_dia = periodo_legivel(inicio, fim)

        return WeeklyRanking(
            week_label=rotulo_iso(inicio),
            week_start=inicio_dia,
            week_end=fim_dia,
            goal=meta,
            movers=movimentos[:TOP_DESTAQUES],
            team_stars_gained=sum(m.stars_gained for m in movimentos),
            players_reported=len(movimentos),
        )

    @staticmethod
    def _base_anterior(
        snapshots: list[StarSnapshot], inicio: datetime
    ) -> StarSnapshot | None:
        """Ultimo reporte antes da semana, que e o ponto de partida real."""
        anteriores = [s for s in snapshots if s.reported_at < inicio]
        return max(anteriores, key=lambda s: s.reported_at) if anteriores else None

    def mark_announced(self, week_label: str) -> bool:
        novo = self.anuncios.mark(AnnouncementKind.WEEKLY_RANKING, week_label)
        if novo:
            self.db.commit()
            logger.info("ranking semanal marcado como publicado", extra={"semana": week_label})
        return novo
