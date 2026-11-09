"""add stage_id back to mineral_batches

Revision ID: c6960e760cdf
Revises: 845b4696ee45
Create Date: 2026-10-15 12:25:45.229166

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6960e760cdf"
down_revision: Union[str, Sequence[str], None] = "845b4696ee45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "mineral_batches",
        sa.Column("stage_id", sa.SmallInteger(), nullable=True),
    )
    op.execute(
        "UPDATE mineral_batches "
        "SET stage_id = (SELECT MIN(stage_id) FROM processing_stages)"
    )
    op.alter_column("mineral_batches", "stage_id", nullable=False)
    op.create_foreign_key(
        "mineral_batches_stage_id_fkey",
        "mineral_batches",
        "processing_stages",
        ["stage_id"],
        ["stage_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "mineral_batches_stage_id_fkey", "mineral_batches", type_="foreignkey"
    )
    op.drop_column("mineral_batches", "stage_id")
