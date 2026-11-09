"""merge heads

Revision ID: c8a5ae999125
Revises: c6960e760cdf, f382833edebb
Create Date: 2026-10-19 21:53:09.616412

"""

from typing import Sequence, Union


revision: str = "c8a5ae999125"
down_revision: Union[str, Sequence[str], None] = ("c6960e760cdf", "f382833edebb")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
