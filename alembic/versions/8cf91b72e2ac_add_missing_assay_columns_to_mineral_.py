"""add missing assay columns to mineral batches

Revision ID: 8cf91b72e2ac
Revises: 0ca058993f78
Create Date: 2026-10-17 11:57:04.762704

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8cf91b72e2ac"
down_revision: Union[str, Sequence[str], None] = "0ca058993f78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mineral_batches",
        sa.Column("assay_file_data", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "mineral_batches",
        sa.Column(
            "assay_original_filename",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("mineral_batches", "assay_original_filename")
    op.drop_column("mineral_batches", "assay_file_data")
