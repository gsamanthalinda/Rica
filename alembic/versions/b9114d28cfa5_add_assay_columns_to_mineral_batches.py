"""add assay columns to mineral batches

Revision ID: b9114d28cfa5
Revises: e0c5e2cb1030
Create Date: 2026-10-15 09:09:25.392791

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9114d28cfa5"
down_revision: Union[str, Sequence[str], None] = "e0c5e2cb1030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "mineral_batches", sa.Column("assay_file_data", sa.LargeBinary(), nullable=True)
    )
    op.add_column(
        "mineral_batches",
        sa.Column("assay_original_filename", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("mineral_batches", "assay_original_filename")
    op.drop_column("mineral_batches", "assay_file_data")
