"""Add downloads.playlist_title, playlist_channel and playlist_id.

Revision ID: 20261118120000
Revises: 20261118110000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261118120000"
down_revision: str | None = "20261118110000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("playlist_title", "playlist_channel", "playlist_id")


def upgrade() -> None:
    with op.batch_alter_table("downloads") as batch:
        for name in _COLUMNS:
            batch.add_column(sa.Column(name, sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("downloads") as batch:
        for name in _COLUMNS:
            batch.drop_column(name)
