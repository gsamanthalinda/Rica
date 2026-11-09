"""merge remaining migration heads

Revision ID: b6331a84d024
Revises: 35412823f677, 7771b190bf39, b2c3d4e5f6a7, c8a5ae999125
Create Date: 2026-10-24 17:23:21.314850

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "b6331a84d024"
down_revision: Union[str, Sequence[str], None] = (
    "35412823f677",
    "7771b190bf39",
    "b2c3d4e5f6a7",
    "c8a5ae999125",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
