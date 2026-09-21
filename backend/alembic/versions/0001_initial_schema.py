"""schema inicial: heroes, patches, hero_stats, meta_snapshots

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "heroes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
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
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_heroes_role", "heroes", ["role"], unique=False)
    op.create_index("ix_heroes_slug", "heroes", ["slug"], unique=True)

    op.create_table(
        "patches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("released_at", sa.Date(), nullable=True),
        sa.Column("notes_url", sa.String(length=500), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
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
    op.create_index("ix_patches_version", "patches", ["version"], unique=True)

    op.create_table(
        "hero_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hero_id", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Float(), nullable=False),
        sa.Column("pick_rate", sa.Float(), nullable=False),
        sa.Column("ban_rate", sa.Float(), nullable=False),
        sa.Column("matches", sa.Integer(), nullable=True),
        sa.Column("rank_filter", sa.String(length=20), nullable=False),
        sa.Column("patch", sa.String(length=20), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hero_id", "patch", "rank_filter", "collected_at", name="uq_hero_stats_reading"
        ),
    )
    op.create_index("ix_hero_stats_hero_id", "hero_stats", ["hero_id"], unique=False)
    op.create_index(
        "ix_hero_stats_patch_rank", "hero_stats", ["patch", "rank_filter"], unique=False
    )

    op.create_table(
        "meta_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hero_id", sa.Integer(), nullable=False),
        sa.Column("lane", sa.String(length=20), nullable=False),
        sa.Column("tier", sa.String(length=5), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("patch", sa.String(length=20), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hero_id", "lane", "patch", "collected_at", name="uq_meta_snapshot_reading"
        ),
    )
    op.create_index("ix_meta_snapshots_hero_id", "meta_snapshots", ["hero_id"], unique=False)
    op.create_index(
        "ix_meta_snapshots_lane_patch", "meta_snapshots", ["lane", "patch"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_meta_snapshots_lane_patch", table_name="meta_snapshots")
    op.drop_index("ix_meta_snapshots_hero_id", table_name="meta_snapshots")
    op.drop_table("meta_snapshots")

    op.drop_index("ix_hero_stats_patch_rank", table_name="hero_stats")
    op.drop_index("ix_hero_stats_hero_id", table_name="hero_stats")
    op.drop_table("hero_stats")

    op.drop_index("ix_patches_version", table_name="patches")
    op.drop_table("patches")

    op.drop_index("ix_heroes_slug", table_name="heroes")
    op.drop_index("ix_heroes_role", table_name="heroes")
    op.drop_table("heroes")
