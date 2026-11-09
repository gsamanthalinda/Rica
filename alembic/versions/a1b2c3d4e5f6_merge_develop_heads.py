"""merge the two develop heads into a single linear history

Revision ID: a1b2c3d4e5f6
Revises: c6960e760cdf, f382833edebb
Create Date: 2026-10-19 18:30:00.000000

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = (
    "c6960e760cdf",
    "f382833edebb",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
