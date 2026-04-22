"""heron push state

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-22

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "heron_push_state",
        sa.Column("report_name", sa.Text, primary_key=True),
        sa.Column(
            "last_pushed_at", sa.DateTime(timezone=True), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("heron_push_state")
