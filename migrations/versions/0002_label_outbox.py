"""add outbox status to labels_emitted

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-17

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "labels_emitted",
        sa.Column("status", sa.Text, server_default="pending", nullable=False),
    )
    op.add_column("labels_emitted", sa.Column("ozone_error", sa.Text))
    op.add_column(
        "labels_emitted", sa.Column("delivered_at", sa.DateTime(timezone=True))
    )
    op.create_check_constraint(
        "ck_labels_emitted_status",
        "labels_emitted",
        "status IN ('pending','emitted','failed','shadow')",
    )
    op.create_index(
        "ix_labels_emitted_status_pending",
        "labels_emitted",
        ["id"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # `sig` and `subscribeLabels`-related plumbing are owned by Ozone now.
    op.drop_column("labels_emitted", "sig")


def downgrade() -> None:
    op.add_column("labels_emitted", sa.Column("sig", sa.LargeBinary))
    op.drop_index("ix_labels_emitted_status_pending", table_name="labels_emitted")
    op.drop_constraint("ck_labels_emitted_status", "labels_emitted", type_="check")
    op.drop_column("labels_emitted", "delivered_at")
    op.drop_column("labels_emitted", "ozone_error")
    op.drop_column("labels_emitted", "status")
