"""Add downloads.vcodec, acodec, dynamic_range and warning_message.

Revision ID: 20261119120000
Revises: 20261118130000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261119120000"
down_revision: str | None = "20261118130000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("vcodec", "acodec", "dynamic_range", "warning_message")


def upgrade() -> None:
    with op.batch_alter_table("downloads") as batch:
        for name in _COLUMNS:
            batch.add_column(sa.Column(name, sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("downloads") as batch:
        for name in _COLUMNS:
            batch.drop_column(name)
