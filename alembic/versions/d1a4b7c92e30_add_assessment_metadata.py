"""Add assessment metadata to scenario decisions.

Revision ID: d1a4b7c92e30
Revises: 51da2fc349b6
"""

from alembic import op

revision = "d1a4b7c92e30"
down_revision = "51da2fc349b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE scenario_decisions
        ADD COLUMN IF NOT EXISTS assessed_by VARCHAR(100)
        NOT NULL DEFAULT 'SYSTEM'
    """)
    op.execute("""
        ALTER TABLE scenario_decisions
        ADD COLUMN IF NOT EXISTS assessment_method VARCHAR(40)
        NOT NULL DEFAULT 'RULE_BASED_V1'
    """)


def downgrade() -> None:
    op.drop_column("scenario_decisions", "assessment_method")
    op.drop_column("scenario_decisions", "assessed_by")
