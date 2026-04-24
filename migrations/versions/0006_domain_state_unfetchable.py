"""domain state: unfetchable

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-24

"""
from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_domains_state", "domains", type_="check")
    op.create_check_constraint(
        "ck_domains_state",
        "domains",
        "state IN ('red','green','pending','pending_review','unknown','unfetchable')",
    )


def downgrade() -> None:
    op.execute("UPDATE domains SET state = 'unknown' WHERE state = 'unfetchable'")
    op.drop_constraint("ck_domains_state", "domains", type_="check")
    op.create_check_constraint(
        "ck_domains_state",
        "domains",
        "state IN ('red','green','pending','pending_review','unknown')",
    )
