"""add password_changed_at to users

Revision ID: 3c6e0e8141cb
Revises: 8cf91b72e2ac
Create Date: 2026-10-17 12:00:04.063893

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3c6e0e8141cb"
down_revision: Union[str, Sequence[str], None] = "8cf91b72e2ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
