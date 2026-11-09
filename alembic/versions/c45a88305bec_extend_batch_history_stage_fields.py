"""Extend batch history stage fields."""

from alembic import op
import sqlalchemy as sa

revision = "c45a88305bec"
down_revision = "f382833edebb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "batch_history",
        sa.Column("source_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "batch_history",
        sa.Column("source_location", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "batch_history",
        sa.Column(
            "feed_quantity_tonnes",
            sa.Numeric(precision=18, scale=6),
            nullable=True,
        ),
    )
    op.add_column(
        "batch_history",
        sa.Column(
            "feed_grade",
            sa.Numeric(precision=8, scale=6),
            nullable=True,
        ),
    )
    op.add_column(
        "batch_history",
        sa.Column(
            "output_quantity_tonnes",
            sa.Numeric(precision=18, scale=6),
            nullable=True,
        ),
    )
    op.add_column(
        "batch_history",
        sa.Column(
            "output_grade",
            sa.Numeric(precision=8, scale=6),
            nullable=True,
        ),
    )
    op.add_column(
        "batch_history",
        sa.Column(
            "moisture",
            sa.Numeric(precision=8, scale=6),
            nullable=True,
        ),
    )
    op.add_column(
        "batch_history",
        sa.Column("assay_document_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("batch_history", "assay_document_url")
    op.drop_column("batch_history", "moisture")
    op.drop_column("batch_history", "output_grade")
    op.drop_column("batch_history", "output_quantity_tonnes")
    op.drop_column("batch_history", "feed_grade")
    op.drop_column("batch_history", "feed_quantity_tonnes")
    op.drop_column("batch_history", "source_location")
    op.drop_column("batch_history", "source_type")
