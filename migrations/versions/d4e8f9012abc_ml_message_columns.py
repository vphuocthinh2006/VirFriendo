"""ml metadata columns on messages

Revision ID: d4e8f9012abc
Revises: b3e4c5d6e7f8
Create Date: 2026-05-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e8f9012abc"
down_revision: Union[str, Sequence[str], None] = "b3e4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("dialogue_act", sa.String(length=128), nullable=True))
    op.add_column("messages", sa.Column("ml_metadata", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "ml_metadata")
    op.drop_column("messages", "dialogue_act")
