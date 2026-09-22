"""tabela generica de anuncios

Substitui `meta_announcements` por `announcements`, que aceita qualquer tipo
de publicacao (meta, ranking semanal, e o que vier). Os registros antigos
sao copiados, nao descartados: o autogenerate dropava a tabela direto, o que
faria o bot republicar atualizacoes ja enviadas em qualquer ambiente com
dados.

Revision ID: 0007_announcements
Revises: 0006_players_stars
Create Date: 2026-09-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_announcements"
down_revision: str | None = "0006_players_stars"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=False),
        sa.Column("announced_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.UniqueConstraint("kind", "reference", name="uq_announcement"),
    )
    op.create_index("ix_announcements_kind", "announcements", ["kind"], unique=False)

    # A referencia do meta e "<fonte>@<collected_at ISO>", o mesmo formato
    # que MetaUpdateService monta em codigo.
    op.execute(
        """
        INSERT INTO announcements (kind, reference, announced_at, created_at, updated_at)
        SELECT 'meta_update',
               source || '@' || to_char(collected_at AT TIME ZONE 'UTC',
                                        'YYYY-MM-DD"T"HH24:MI:SS+00:00'),
               announced_at,
               created_at,
               updated_at
        FROM meta_announcements
        """
    )

    op.drop_table("meta_announcements")


def downgrade() -> None:
    op.create_table(
        "meta_announcements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("announced_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.UniqueConstraint("collected_at", "source", name="uq_meta_announcement"),
    )
    op.drop_index("ix_announcements_kind", table_name="announcements")
    op.drop_table("announcements")
