"""sinergia medida entre duplas de herois

Criacao pura de tabela: nao toca em dado existente. Gerada por autogenerate
e conferida - o conteudo abaixo e exatamente o que o metadata descreve.

Revision ID: 0009_hero_synergies
Revises: 0008_community_builds
Create Date: 2026-09-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_hero_synergies"
down_revision: str | None = "0008_community_builds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hero_synergies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hero_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("win_rate_delta", sa.Float(), nullable=False),
        sa.Column("partner_win_rate", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["hero_id"], ["heroes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["partner_id"], ["heroes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hero_id", "partner_id", name="uq_hero_synergy_pair"),
    )
    op.create_index(op.f("ix_hero_synergies_hero_id"), "hero_synergies", ["hero_id"], unique=False)
    op.create_index(
        "ix_hero_synergies_lookup", "hero_synergies", ["hero_id", "partner_id"], unique=False
    )
    op.create_index(
        op.f("ix_hero_synergies_partner_id"), "hero_synergies", ["partner_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_hero_synergies_partner_id"), table_name="hero_synergies")
    op.drop_index("ix_hero_synergies_lookup", table_name="hero_synergies")
    op.drop_index(op.f("ix_hero_synergies_hero_id"), table_name="hero_synergies")
    op.drop_table("hero_synergies")
