"""Add downloads.hdr.

Revision ID: 20261118110000
Revises: 20261115120000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261118110000"
down_revision: str | None = "20261115120000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("downloads") as batch:
        batch.add_column(sa.Column("hdr", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("downloads") as batch:
        batch.drop_column("hdr")
