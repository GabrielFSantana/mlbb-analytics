"""meta por faixa de ranque

Revision ID: 0005_meta_rank_filter
Revises: 0004_items_builds
Create Date: 2026-09-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_meta_rank_filter"
down_revision: str | None = "0004_items_builds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A coluna e NOT NULL e a tabela ja tem dados: criamos com server_default
    # para o backfill e removemos o default em seguida, deixando o valor a
    # cargo da aplicacao (como nas demais colunas de enum).
    op.add_column(
        "meta_snapshots",
        sa.Column("rank_filter", sa.String(length=20), nullable=False, server_default="all"),
    )
    op.alter_column("meta_snapshots", "rank_filter", server_default=None)

    op.drop_index("ix_meta_snapshots_lane_patch", table_name="meta_snapshots")
    op.drop_constraint("uq_meta_snapshot_reading", "meta_snapshots", type_="unique")
    op.create_unique_constraint(
        "uq_meta_snapshot_reading",
        "meta_snapshots",
        ["hero_id", "lane", "rank_filter", "patch", "collected_at"],
    )
    op.create_index(
        "ix_meta_snapshots_lane_rank", "meta_snapshots", ["lane", "rank_filter"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_meta_snapshots_lane_rank", table_name="meta_snapshots")
    op.drop_constraint("uq_meta_snapshot_reading", "meta_snapshots", type_="unique")
    op.create_unique_constraint(
        "uq_meta_snapshot_reading",
        "meta_snapshots",
        ["hero_id", "lane", "patch", "collected_at"],
    )
    op.create_index(
        "ix_meta_snapshots_lane_patch", "meta_snapshots", ["lane", "patch"], unique=False
    )
    op.drop_column("meta_snapshots", "rank_filter")
