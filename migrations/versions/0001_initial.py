"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-17

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "domains",
        sa.Column("host", sa.Text, primary_key=True),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("platform", sa.Text),
        sa.Column("confidence", sa.Float),
        sa.Column("signals", postgresql.JSONB),
        sa.Column("detector_version", sa.Text),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_checked", sa.DateTime(timezone=True)),
        sa.Column(
            "last_changed",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('red','green','pending','pending_review','unknown')",
            name="ck_domains_state",
        ),
    )
    op.create_index("ix_domains_state", "domains", ["state"])
    op.create_index("ix_domains_last_checked", "domains", ["last_checked"])

    op.create_table(
        "fetch_queue",
        sa.Column("host", sa.Text, primary_key=True),
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
    op.create_index("ix_fetch_queue_locked_until", "fetch_queue", ["locked_until"])

    op.create_table(
        "pending_posts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("post_uri", sa.Text, nullable=False),
        sa.Column("post_cid", sa.Text, nullable=False),
        sa.Column("host", sa.Text, sa.ForeignKey("fetch_queue.host"), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column(
            "seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_pending_posts_host", "pending_posts", ["host"])

    op.create_table(
        "labels_emitted",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("seq", sa.BigInteger, nullable=False, unique=True),
        sa.Column("post_uri", sa.Text, nullable=False),
        sa.Column("post_cid", sa.Text, nullable=False),
        sa.Column("val", sa.Text, nullable=False),
        sa.Column("host", sa.Text, nullable=False),
        sa.Column("neg", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("shadow", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("sig", sa.LargeBinary),
        sa.Column(
            "emitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_labels_emitted_seq", "labels_emitted", ["seq"])
    op.create_index(
        "ux_labels_emitted_uri_val_neg",
        "labels_emitted",
        ["post_uri", "val", "neg"],
        unique=True,
    )

    op.execute("CREATE SEQUENCE IF NOT EXISTS labels_emitted_seq_seq")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS labels_emitted_seq_seq")
    op.drop_index("ux_labels_emitted_uri_val_neg", table_name="labels_emitted")
    op.drop_index("ix_labels_emitted_seq", table_name="labels_emitted")
    op.drop_table("labels_emitted")
    op.drop_index("ix_pending_posts_host", table_name="pending_posts")
    op.drop_table("pending_posts")
    op.drop_index("ix_fetch_queue_locked_until", table_name="fetch_queue")
    op.drop_table("fetch_queue")
    op.drop_index("ix_domains_last_checked", table_name="domains")
    op.drop_index("ix_domains_state", table_name="domains")
    op.drop_table("domains")
