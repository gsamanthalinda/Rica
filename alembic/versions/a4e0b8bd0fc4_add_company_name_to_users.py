"""add company_name to users

Revision ID: a4e0b8bd0fc4
Revises: c8a5ae999125
Create Date: 2026-10-19 21:53:13.057261

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4e0b8bd0fc4"
down_revision: Union[str, Sequence[str], None] = "925f61b2d684"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("company_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "company_name")
