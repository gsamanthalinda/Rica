"""merge assessment metadata and scenario decisions

Revision ID: 7771b190bf39
Revises: d1a4b7c92e30, e7f067104a73
Create Date: 2026-10-24 11:45:14.897116

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "7771b190bf39"
down_revision: Union[str, Sequence[str], None] = ("d1a4b7c92e30", "e7f067104a73")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
