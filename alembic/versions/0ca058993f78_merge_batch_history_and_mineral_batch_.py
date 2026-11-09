"""merge batch history and mineral batch migrations

Revision ID: 0ca058993f78
Revises: c45a88305bec, c6960e760cdf
Create Date: 2026-10-17 11:50:53.909894

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "0ca058993f78"
down_revision: Union[str, Sequence[str], None] = ("c45a88305bec", "c6960e760cdf")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
