"""add downloads.quality_cap

Revision ID: 20261115120000
Revises: 20260609233000
Create Date: 2026-11-15 12:00:00

"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261115120000"
down_revision: str | None = "20260609233000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("downloads") as batch:
        batch.add_column(sa.Column("quality_cap", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("downloads") as batch:
        batch.drop_column("quality_cap")
