"""drop FK pending_posts.host -> fetch_queue.host

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-22

The FK caused a race under concurrent consumer/worker operation: worker
classifies a domain and deletes its fetch_queue row, but the consumer may
have inserted new pending_posts rows for the same host in the interval,
violating the FK at delete time. `pending_posts.host` is conceptually a
hostname, not a queue reference — drop the constraint.
"""
from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "pending_posts_host_fkey", "pending_posts", type_="foreignkey"
    )


def downgrade() -> None:
    op.create_foreign_key(
        "pending_posts_host_fkey",
        "pending_posts",
        "fetch_queue",
        ["host"],
        ["host"],
    )
