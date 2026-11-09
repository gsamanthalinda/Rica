"""adjust value_calculation model

Revision ID: f382833edebb
Revises: 925f61b2d684
Create Date: 2026-10-14 22:53:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f382833edebb"
down_revision = "925f61b2d684"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""

    op.alter_column(
        "value_calculations",
        "recovery",
        existing_type=sa.Numeric(precision=8, scale=6),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.alter_column(
        "value_calculations",
        "recovery",
        existing_type=sa.Numeric(precision=8, scale=6),
        nullable=False,
    )
