"""merge divergent heads

Revision ID: 43ca4bea5cce
Revises: c6960e760cdf, f382833edebb
Create Date: 2026-10-20 16:15:46.051289

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "43ca4bea5cce"
down_revision: Union[str, Sequence[str], None] = ("c6960e760cdf", "f382833edebb")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
