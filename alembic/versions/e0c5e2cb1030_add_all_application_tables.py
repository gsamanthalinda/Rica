"""Add all application tables

Revision ID: e0c5e2cb1030
Revises: e956f09d346f
Create Date: 2026-10-13 17:31:54.089022

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e0c5e2cb1030"
down_revision: Union[str, Sequence[str], None] = "e956f09d346f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "processing_stages",
        sa.Column("stage_id", sa.SmallInteger(), nullable=False),
        sa.Column("stage_name", sa.String(length=100), nullable=False),
        sa.Column("stage_order", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "stage_order > 0", name="ck_processing_stages_order_positive"
        ),
        sa.PrimaryKeyConstraint("stage_id"),
        sa.UniqueConstraint("stage_name"),
        sa.UniqueConstraint("stage_order"),
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "SYSTEM_ADMINISTRATOR",
                "SUPPLY_CHAIN_MANAGER",
                "OPERATIONS_MANAGER",
                name="user_role",
            ),
            nullable=False,
        ),
        sa.Column(
            "account_status",
            sa.Enum("ACTIVE", "DISABLED", name="account_status"),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "mineral_batches",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("batch_code", sa.String(length=100), nullable=False),
        sa.Column(
            "mineral_type",
            sa.String(length=100),
            server_default="COPPER",
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.Enum("SELF_EXTRACTED", "PURCHASED", name="source_type"),
            nullable=False,
        ),
        sa.Column("quantity_tonnes", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("grade", sa.Numeric(precision=8, scale=6), nullable=False),
        sa.Column("recovery", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("stage_id", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "CLOSED", name="batch_status"),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.CheckConstraint("mineral_type = 'COPPER'", name="ck_batches_mineral_copper"),
        sa.CheckConstraint("grade >= 0 AND grade <= 1", name="ck_batches_grade_range"),
        sa.CheckConstraint("quantity_tonnes >= 0", name="ck_batches_quantity_nonneg"),
        sa.CheckConstraint(
            "recovery IS NULL OR (recovery >= 0 AND recovery <= 1)",
            name="ck_batches_recovery_range",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["stage_id"],
            ["processing_stages.stage_id"],
        ),
        sa.PrimaryKeyConstraint("batch_id"),
        sa.UniqueConstraint("batch_code"),
    )
    op.create_table(
        "batch_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("current_stage_id", sa.SmallInteger(), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        sa.Column("quantity_tonnes", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("grade", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("recovery", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "grade IS NULL OR (grade >= 0 AND grade <= 1)",
            name="ck_history_grade_range",
        ),
        sa.CheckConstraint(
            "quantity_tonnes IS NULL OR quantity_tonnes >= 0",
            name="ck_history_quantity_nonneg",
        ),
        sa.CheckConstraint(
            "recovery IS NULL OR (recovery >= 0 AND recovery <= 1)",
            name="ck_history_recovery_range",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["mineral_batches.batch_id"],
        ),
        sa.ForeignKeyConstraint(
            ["current_stage_id"],
            ["processing_stages.stage_id"],
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"],
            ["users.user_id"],
        ),
        sa.PrimaryKeyConstraint("history_id"),
    )
    op.create_table(
        "value_calculations",
        sa.Column("calculation_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("batch_history_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.SmallInteger(), nullable=False),
        sa.Column("reference_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("price_unit", sa.String(length=30), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("price_source", sa.String(length=150), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column(
            "contained_metal_tonnes", sa.Numeric(precision=18, scale=6), nullable=False
        ),
        sa.Column(
            "recoverable_metal_tonnes",
            sa.Numeric(precision=18, scale=6),
            nullable=False,
        ),
        sa.Column(
            "calculated_value", sa.Numeric(precision=24, scale=6), nullable=False
        ),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("calculated_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint("calculated_value >= 0", name="ck_valcalc_value_nonneg"),
        sa.CheckConstraint(
            "contained_metal_tonnes >= 0", name="ck_valcalc_contained_nonneg"
        ),
        sa.CheckConstraint(
            "recoverable_metal_tonnes >= 0", name="ck_valcalc_recoverable_nonneg"
        ),
        sa.CheckConstraint("reference_price > 0", name="ck_valcalc_price_positive"),
        sa.ForeignKeyConstraint(
            ["batch_history_id"],
            ["batch_history.history_id"],
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["mineral_batches.batch_id"],
        ),
        sa.ForeignKeyConstraint(
            ["calculated_by"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["stage_id"],
            ["processing_stages.stage_id"],
        ),
        sa.PrimaryKeyConstraint("calculation_id"),
    )
    op.create_table(
        "scenarios",
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_calculation_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("scenario_name", sa.String(length=150), nullable=False),
        sa.Column(
            "assumed_quantity", sa.Numeric(precision=18, scale=6), nullable=False
        ),
        sa.Column("assumed_grade", sa.Numeric(precision=8, scale=6), nullable=False),
        sa.Column("assumed_recovery", sa.Numeric(precision=8, scale=6), nullable=False),
        sa.Column("assumed_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("assumed_stage_id", sa.SmallInteger(), nullable=False),
        sa.Column("price_unit", sa.String(length=30), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.CheckConstraint(
            "assumed_grade >= 0 AND assumed_grade <= 1", name="ck_scenarios_grade_range"
        ),
        sa.CheckConstraint("assumed_price > 0", name="ck_scenarios_price_positive"),
        sa.CheckConstraint(
            "assumed_quantity >= 0", name="ck_scenarios_quantity_nonneg"
        ),
        sa.CheckConstraint(
            "assumed_recovery >= 0 AND assumed_recovery <= 1",
            name="ck_scenarios_recovery_range",
        ),
        sa.ForeignKeyConstraint(
            ["assumed_stage_id"],
            ["processing_stages.stage_id"],
        ),
        sa.ForeignKeyConstraint(
            ["baseline_calculation_id"],
            ["value_calculations.calculation_id"],
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["mineral_batches.batch_id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
        ),
        sa.PrimaryKeyConstraint("scenario_id"),
    )
    op.create_table(
        "scenario_results",
        sa.Column("results_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("execution_number", sa.Integer(), nullable=False),
        sa.Column("simulated_value", sa.Numeric(precision=24, scale=6), nullable=False),
        sa.Column("baseline_value", sa.Numeric(precision=24, scale=6), nullable=False),
        sa.Column(
            "value_difference", sa.Numeric(precision=24, scale=6), nullable=False
        ),
        sa.Column(
            "percentage_difference", sa.Numeric(precision=12, scale=6), nullable=True
        ),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("baseline_value >= 0", name="ck_results_baseline_nonneg"),
        sa.CheckConstraint(
            "execution_number > 0", name="ck_results_execution_positive"
        ),
        sa.CheckConstraint("simulated_value >= 0", name="ck_results_simulated_nonneg"),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.scenario_id"],
        ),
        sa.PrimaryKeyConstraint("results_id"),
        sa.UniqueConstraint(
            "scenario_id", "execution_number", name="uq_results_scenario_execution"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("scenario_results")
    op.drop_table("scenarios")
    op.drop_table("value_calculations")
    op.drop_table("batch_history")
    op.drop_table("mineral_batches")
    op.drop_table("users")
    op.drop_table("processing_stages")
