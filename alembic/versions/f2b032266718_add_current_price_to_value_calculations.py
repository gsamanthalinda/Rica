"""add current_price to value_calculations

Revision ID: f2b032266718
Revises: e0c5e2cb1030
Create Date: 2026-10-14 22:03:40.779206

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2b032266718"
down_revision: Union[str, Sequence[str], None] = "e0c5e2cb1030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "value_calculations",
        sa.Column("current_price", sa.Numeric(precision=18, scale=6), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("value_calculations", "current_price")
