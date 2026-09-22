"""relacoes entre herois

Revision ID: 0003_hero_relations
Revises: 0002_meta_announcements
Create Date: 2026-09-22 10:56:48.209622
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_hero_relations"
down_revision: str | None = "0002_meta_announcements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hero_relations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hero_id", sa.Integer(), nullable=False),
        sa.Column("related_hero_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
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
        sa.ForeignKeyConstraint(["related_hero_id"], ["heroes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hero_id", "related_hero_id", "relation_type", name="uq_hero_relation"),
    )
    op.create_index(op.f("ix_hero_relations_hero_id"), "hero_relations", ["hero_id"], unique=False)
    op.create_index(
        "ix_hero_relations_lookup", "hero_relations", ["hero_id", "relation_type"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_hero_relations_lookup", table_name="hero_relations")
    op.drop_index(op.f("ix_hero_relations_hero_id"), table_name="hero_relations")
    op.drop_table("hero_relations")
