"""shortener resolver tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-17

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shortener_resolutions",
        sa.Column("short_url", sa.Text, primary_key=True),
        sa.Column("resolved_url", sa.Text),
        sa.Column("resolved_host", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_shortener_resolutions_resolved_host",
        "shortener_resolutions",
        ["resolved_host"],
    )

    op.create_table(
        "shortener_queue",
        sa.Column("short_url", sa.Text, primary_key=True),
        sa.Column(
            "enqueued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer, server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text),
    )
    op.create_index(
        "ix_shortener_queue_locked_until",
        "shortener_queue",
        ["locked_until"],
    )

    op.create_table(
        "shortener_pending",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("post_uri", sa.Text, nullable=False),
        sa.Column("post_cid", sa.Text, nullable=False),
        sa.Column("short_url", sa.Text, nullable=False),
        sa.Column(
            "seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_shortener_pending_short_url", "shortener_pending", ["short_url"])


def downgrade() -> None:
    op.drop_index("ix_shortener_pending_short_url", table_name="shortener_pending")
    op.drop_table("shortener_pending")
    op.drop_index("ix_shortener_queue_locked_until", table_name="shortener_queue")
    op.drop_table("shortener_queue")
    op.drop_index(
        "ix_shortener_resolutions_resolved_host", table_name="shortener_resolutions"
    )
    op.drop_table("shortener_resolutions")
