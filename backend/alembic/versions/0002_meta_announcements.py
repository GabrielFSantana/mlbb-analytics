"""tabela de anuncios de meta

Revision ID: 0002_meta_announcements
Revises: 0001_initial
Create Date: 2026-09-21 21:48:19.382366
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_meta_announcements"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("meta_announcements",
    sa.Column("id", sa.Integer(), nullable=False),
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
    sa.UniqueConstraint("collected_at", "source", name="uq_meta_announcement")
    )


def downgrade() -> None:
    op.drop_table("meta_announcements")
