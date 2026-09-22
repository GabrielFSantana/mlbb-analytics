"""itens e builds

Revision ID: 0004_items_builds
Revises: 0003_hero_relations
Create Date: 2026-09-22 11:19:30.492759
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_items_builds"
down_revision: str | None = "0003_hero_relations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_items_external_id"), "items", ["external_id"], unique=True)
    op.create_table(
        "hero_builds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hero_id", sa.Integer(), nullable=False),
        sa.Column("lane", sa.String(length=20), nullable=False),
        sa.Column("rank_filter", sa.String(length=20), nullable=False),
        sa.Column("variant", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Float(), nullable=False),
        sa.Column("pick_rate", sa.Float(), nullable=False),
        sa.Column("emblem", sa.String(length=80), nullable=True),
        sa.Column("battle_spell", sa.String(length=80), nullable=True),
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
        sa.UniqueConstraint(
            "hero_id", "lane", "rank_filter", "variant", name="uq_hero_build_variant"
        ),
    )
    op.create_index(op.f("ix_hero_builds_hero_id"), "hero_builds", ["hero_id"], unique=False)
    op.create_index("ix_hero_builds_lookup", "hero_builds", ["hero_id", "lane"], unique=False)
    op.create_table(
        "hero_build_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("build_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["build_id"], ["hero_builds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("build_id", "position", name="uq_hero_build_item_position"),
    )
    op.create_index(
        op.f("ix_hero_build_items_build_id"), "hero_build_items", ["build_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_hero_build_items_build_id"), table_name="hero_build_items")
    op.drop_table("hero_build_items")
    op.drop_index("ix_hero_builds_lookup", table_name="hero_builds")
    op.drop_index(op.f("ix_hero_builds_hero_id"), table_name="hero_builds")
    op.drop_table("hero_builds")
    op.drop_index(op.f("ix_items_external_id"), table_name="items")
    op.drop_table("items")
