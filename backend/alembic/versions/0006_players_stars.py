"""jogadores e estrelas

Revision ID: 0006_players_stars
Revises: 0005_meta_rank_filter
Create Date: 2026-09-22 12:43:33.238927
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_players_stars"
down_revision: str | None = "0005_meta_rank_filter"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("game_player_id", sa.String(length=32), nullable=True),
        sa.Column("game_server_id", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_players_discord_user_id"), "players", ["discord_user_id"], unique=True)
    op.create_table(
        "star_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_star_snapshots_player_id"), "star_snapshots", ["player_id"], unique=False
    )
    op.create_index(
        "ix_star_snapshots_player_reported",
        "star_snapshots",
        ["player_id", "reported_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_star_snapshots_player_reported", table_name="star_snapshots")
    op.drop_index(op.f("ix_star_snapshots_player_id"), table_name="star_snapshots")
    op.drop_table("star_snapshots")
    op.drop_index(op.f("ix_players_discord_user_id"), table_name="players")
    op.drop_table("players")
