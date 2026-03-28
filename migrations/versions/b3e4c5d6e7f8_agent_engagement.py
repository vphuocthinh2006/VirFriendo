"""agent engagement stats and likes

Revision ID: b3e4c5d6e7f8
Revises: 8f0b2a7d1c1b
Create Date: 2026-03-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3e4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "8f0b2a7d1c1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_stats",
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("plays", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("agent_id"),
    )
    op.create_table(
        "user_agent_likes",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "agent_id"),
    )


def downgrade() -> None:
    op.drop_table("user_agent_likes")
    op.drop_table("agent_stats")
