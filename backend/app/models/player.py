"""Jogadores acompanhados e o historico de estrelas que eles reportam.

Por que auto-reportado
----------------------
A Moonton nao expoe estatisticas de jogador sem autenticacao da propria
conta (ver README). Em vez de nao ter a funcionalidade, guardamos o que o
jogador informa: o dado e dele, o controle e dele, e o historico e nosso.

Isso e assumido em todo lugar: `StarSnapshot.source` grava como o numero
chegou, e a interface diz que o valor e auto-reportado. Nunca apresentamos
isso como leitura oficial do jogo.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class Player(Base, TimestampMixin):
    """Alguem do time que acompanha a propria evolucao.

    A identidade e o id do Discord: e o que o bot conhece, nao exige que a
    pessoa informe id de jogo, e continua valendo se ela trocar de nick.
    """

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    discord_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)

    #: Opcionais: so para exibicao e para um futuro cruzamento com fonte
    #: externa, caso alguma passe a existir.
    game_player_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    game_server_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    snapshots: Mapped[list[StarSnapshot]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        order_by="StarSnapshot.reported_at",
    )

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<Player {self.display_name!r} discord={self.discord_user_id}>"


class StarSnapshot(Base, TimestampMixin):
    """Quantas estrelas o jogador tinha em um momento.

    Cada reporte vira uma linha: e o historico que permite medir ritmo e
    projetar quando a meta sera alcancada. Corrigir um numero errado e
    reportar de novo - a leitura mais recente vence.
    """

    __tablename__ = "star_snapshots"
    __table_args__ = (Index("ix_star_snapshots_player_reported", "player_id", "reported_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    #: Como o numero chegou ate aqui. Hoje sempre "self_reported"; existe
    #: para o dia em que houver leitura automatica conviver com o manual.
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="self_reported")
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    player: Mapped[Player] = relationship(back_populates="snapshots")

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<StarSnapshot player={self.player_id} stars={self.stars}>"
