"""build completa da comunidade e talentos do emblema

Acrescenta:

* `hero_builds.talents` - nullable, porque as builds ja gravadas foram
  coletadas antes de o campo existir e nao ha como preenche-lo
  retroativamente. Elas se atualizam sozinhas no proximo refresh.
* `community_builds` / `community_build_items` - a build de seis itens
  agregada dos guias escritos por jogadores, separada das builds
  estatisticas para que frequencia nunca seja lida como taxa de vitoria.

Revision ID: 0008_community_builds
Revises: 0007_announcements
Create Date: 2026-09-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_community_builds"
down_revision: str | None = "0007_announcements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hero_builds", sa.Column("talents", sa.String(length=200), nullable=True))

    op.create_table(
        "community_builds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hero_id", sa.Integer(), nullable=False),
        sa.Column("patch", sa.String(length=20), nullable=True),
        sa.Column("builds_considered", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hero_id", name="uq_community_build_hero"),
    )
    op.create_index(
        op.f("ix_community_builds_hero_id"), "community_builds", ["hero_id"], unique=False
    )

    op.create_table(
        "community_build_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("community_build_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("builds", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["community_build_id"], ["community_builds.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("community_build_id", "position", name="uq_community_build_position"),
    )
    op.create_index(
        op.f("ix_community_build_items_community_build_id"),
        "community_build_items",
        ["community_build_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_community_build_items_community_build_id"), table_name="community_build_items"
    )
    op.drop_table("community_build_items")
    op.drop_index(op.f("ix_community_builds_hero_id"), table_name="community_builds")
    op.drop_table("community_builds")
    op.drop_column("hero_builds", "talents")
