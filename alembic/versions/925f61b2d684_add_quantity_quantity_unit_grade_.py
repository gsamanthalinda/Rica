from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "925f61b2d684"
down_revision: Union[str, Sequence[str], None] = "f2b032266718"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "value_calculations",
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=True),
    )
    op.add_column(
        "value_calculations",
        sa.Column(
            "quantity_unit",
            sa.String(length=20),
            nullable=False,
            server_default="tonnes",
        ),
    )
    op.add_column(
        "value_calculations",
        sa.Column("grade", sa.Numeric(precision=8, scale=6), nullable=True),
    )
    op.add_column(
        "value_calculations",
        sa.Column("recovery", sa.Numeric(precision=8, scale=6), nullable=True),
    )

    op.execute("""
        UPDATE value_calculations AS vc
        SET
            quantity = COALESCE(
                (SELECT bh.quantity_tonnes
                 FROM batch_history AS bh
                 WHERE bh.history_id = vc.batch_history_id),
                (SELECT mb.quantity_tonnes
                 FROM mineral_batches AS mb
                 WHERE mb.batch_id = vc.batch_id)
            ),
            grade = COALESCE(
                (SELECT bh.grade
                 FROM batch_history AS bh
                 WHERE bh.history_id = vc.batch_history_id),
                (SELECT mb.grade
                 FROM mineral_batches AS mb
                 WHERE mb.batch_id = vc.batch_id)
            ),
            recovery = COALESCE(
                (SELECT bh.recovery
                 FROM batch_history AS bh
                 WHERE bh.history_id = vc.batch_history_id),
                (SELECT mb.recovery
                 FROM mineral_batches AS mb
                 WHERE mb.batch_id = vc.batch_id)
            )
    """)

    op.alter_column(
        "value_calculations",
        "quantity",
        existing_type=sa.Numeric(precision=18, scale=6),
        nullable=False,
    )
    op.alter_column(
        "value_calculations",
        "grade",
        existing_type=sa.Numeric(precision=8, scale=6),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("value_calculations", "recovery")
    op.drop_column("value_calculations", "grade")
    op.drop_column("value_calculations", "quantity_unit")
    op.drop_column("value_calculations", "quantity")
