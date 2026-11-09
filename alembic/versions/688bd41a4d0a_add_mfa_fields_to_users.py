"""add MFA fields to users

Revision ID: 688bd41a4d0a
Revises: 3c6e0e8141cb
Create Date: 2026-10-17 12:07:28.844620

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "688bd41a4d0a"
down_revision: Union[str, Sequence[str], None] = "3c6e0e8141cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "mfa_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("mfa_secret_encrypted", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "mfa_secret_encrypted")
    op.drop_column("users", "mfa_enabled")
