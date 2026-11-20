"""Add downloads.batch_id, batch_notified and the push_subscriptions table.

Revision ID: 20261118130000
Revises: 20261118120000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261118130000"
down_revision: str | None = "20261118120000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("downloads") as batch:
        batch.add_column(sa.Column("batch_id", sa.String(), nullable=True))
        batch.add_column(
            sa.Column("batch_notified", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.create_index("ix_downloads_batch_id", ["batch_id"])
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("endpoint", sa.String(), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(), nullable=False),
        sa.Column("auth", sa.String(), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()
        ),
    )


def downgrade() -> None:
    op.drop_table("push_subscriptions")
    with op.batch_alter_table("downloads") as batch:
        batch.drop_index("ix_downloads_batch_id")
        batch.drop_column("batch_notified")
        batch.drop_column("batch_id")
