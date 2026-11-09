"""merge company name and MFA migrations

Revision ID: 51da2fc349b6
Revises: 688bd41a4d0a, a4e0b8bd0fc4
Create Date: 2026-10-22 13:28:41.285048

"""

from typing import Sequence, Union


revision: str = "51da2fc349b6"
down_revision: Union[str, Sequence[str], None] = ("688bd41a4d0a", "a4e0b8bd0fc4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
