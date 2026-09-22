"""Acompanhamento da meta de estrelas do time.

Os numeros sao auto-reportados: a Moonton nao expoe estatisticas de jogador
sem autenticacao da conta. O valor aqui nao esta em ler o jogo, e em guardar
o historico - que ninguem mais guarda - e transformar isso em ritmo,
projecao e visao de time.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.progresso import Leitura, calcular_ritmo, percentual, projetar_conclusao
from app.models.player import Player, StarSnapshot
from app.schemas.player import PlayerProgress, StarReport, TeamProgress

logger = get_logger(__name__)


class PlayerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- escrita --------------------------------------------------------

    def report_stars(self, report: StarReport) -> PlayerProgress:
        """Registra um reporte, criando o jogador se for o primeiro."""
        player = self.db.scalar(
            select(Player).where(Player.discord_user_id == report.discord_user_id)
        )
        if player is None:
            player = Player(
                discord_user_id=report.discord_user_id,
                display_name=report.display_name,
            )
            self.db.add(player)
        else:
            # O apelido no Discord muda; o id nao. Mantemos o mais recente.
            player.display_name = report.display_name

        if report.game_player_id:
            player.game_player_id = report.game_player_id
        if report.game_server_id:
            player.game_server_id = report.game_server_id

        self.db.flush()
        self.db.add(
            StarSnapshot(
                player_id=player.id,
                stars=report.stars,
                reported_at=datetime.now(UTC),
                source="self_reported",
                note=report.note,
            )
        )
        self.db.commit()
        logger.info(
            "estrelas reportadas",
            extra={"player": player.display_name, "stars": report.stars},
        )
        return self._progresso_do_jogador(player, settings.team_star_goal)

    # -- leitura --------------------------------------------------------

    def team_progress(
        self,
        *,
        goal: int | None = None,
        window_days: int = 7,
    ) -> TeamProgress:
        meta = goal or settings.team_star_goal
        jogadores = list(
            self.db.scalars(select(Player).options(selectinload(Player.snapshots)))
        )
        progressos = [
            self._progresso_do_jogador(jogador, meta, window_days)
            for jogador in jogadores
            if jogador.snapshots
        ]
        progressos.sort(key=lambda p: p.stars, reverse=True)

        total = sum(p.stars for p in progressos)
        ganhos = [p.stars_gained for p in progressos if p.stars_gained is not None]

        return TeamProgress(
            goal=meta,
            players=progressos,
            total_stars=total,
            average_stars=round(total / len(progressos), 1) if progressos else 0.0,
            players_reached=sum(1 for p in progressos if p.reached),
            team_stars_gained=sum(ganhos) if ganhos else None,
            window_days=window_days,
        )

    def _progresso_do_jogador(
        self,
        player: Player,
        meta: int,
        window_days: int = 7,
    ) -> PlayerProgress:
        leituras = [
            Leitura(stars=s.stars, reported_at=s.reported_at) for s in player.snapshots
        ]
        ultima = max(player.snapshots, key=lambda s: s.reported_at)
        ritmo = calcular_ritmo(leituras, janela_dias=window_days)

        return PlayerProgress(
            display_name=player.display_name,
            discord_user_id=player.discord_user_id,
            stars=ultima.stars,
            percent=percentual(ultima.stars, meta),
            reported_at=ultima.reported_at,
            stars_gained=ritmo.estrelas_ganhas if ritmo else None,
            days_measured=ritmo.dias if ritmo else None,
            stars_per_day=ritmo.por_dia if ritmo else None,
            projected_at=projetar_conclusao(ultima.stars, meta, ritmo),
            reached=ultima.stars >= meta,
        )

    def history(self, discord_user_id: int, *, days: int = 60) -> list[StarSnapshot]:
        limite = datetime.now(UTC) - timedelta(days=days)
        stmt = (
            select(StarSnapshot)
            .join(Player)
            .where(Player.discord_user_id == discord_user_id, StarSnapshot.reported_at >= limite)
            .order_by(StarSnapshot.reported_at)
        )
        return list(self.db.scalars(stmt))
