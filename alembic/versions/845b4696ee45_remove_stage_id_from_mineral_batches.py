"""remove stage_id from mineral_batches

Revision ID: 845b4696ee45
Revises: b9114d28cfa5
Create Date: 2026-10-15 11:33:10.321097

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "845b4696ee45"
down_revision: Union[str, Sequence[str], None] = "b9114d28cfa5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.drop_constraint(
        op.f("mineral_batches_stage_id_fkey"), "mineral_batches", type_="foreignkey"
    )
    op.drop_column("mineral_batches", "stage_id")


def downgrade() -> None:
    """Downgrade schema."""

    op.add_column(
        "mineral_batches",
        sa.Column("stage_id", sa.SMALLINT(), autoincrement=False, nullable=False),
    )
    op.create_foreign_key(
        op.f("mineral_batches_stage_id_fkey"),
        "mineral_batches",
        "processing_stages",
        ["stage_id"],
        ["stage_id"],
    )
