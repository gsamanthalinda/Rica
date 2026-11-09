"""test connection

Revision ID: e956f09d346f
Revises:
Create Date: 2026-10-13 16:21:10.051828

"""

from typing import Sequence, Union


revision: str = "e956f09d346f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
