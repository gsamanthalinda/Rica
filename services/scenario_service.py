import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from sqlalchemy.exc import DataError, IntegrityError

from models import User, UserRole
from models.scenario import Scenario
from models.value_calculation import ValueCalculation
from models.scenario_results import ScenarioResult
from services.mineral_batch import MineralBatchService, _authorize

logger = logging.getLogger(__name__)

SCENARIO_ROLES = {UserRole.SUPPLY_CHAIN_MANAGER}


def service_call(call):
    try:
        return call()
    except ValueError as exc:
        message = str(exc)
        code = (
            status.HTTP_404_NOT_FOUND
            if message == "Scenario not found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=message) from exc


class ScenarioService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _decimal(value, field):
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(f"{field} must be a valid number")
        if not number.is_finite():
            raise ValueError(f"{field} must be finite")
        return number

    def _commit(self):
        try:
            self.db.commit()
        except IntegrityError as exc:
            logger.error("Scenario commit failed (integrity): %s", exc.orig)
            print("Scenario commit failed (integrity):", exc.orig, flush=True)
            raise ValueError(
                "Request conflicts with existing data "
                "(for example, a referenced record does not exist)"
            ) from exc
        except DataError as exc:
            logger.error("Scenario commit failed (data): %s", exc.orig)
            print("Scenario commit failed (data):", exc.orig, flush=True)
            raise ValueError("A value is out of range") from exc

    def create_scenario(
        self,
        user: User,
        *,
        batch_id,
        baseline_calculation_id,
        scenario_name,
        assumed_quantity,
        assumed_grade,
        assumed_recovery,
        assumed_price,
        assumed_stage_id,
        price_unit,
        currency,
    ):
        _authorize(user, SCENARIO_ROLES)
        MineralBatchService(self.db).get_batch_by_id(batch_id, user)

        quantity = self._decimal(assumed_quantity, "quantity")
        grade = self._decimal(assumed_grade, "grade")
        recovery = self._decimal(assumed_recovery, "recovery")
        price = self._decimal(assumed_price, "price")

        if quantity < 0:
            raise ValueError("Quantity cannot be negative")
        if not Decimal("0") <= grade <= Decimal("1"):
            raise ValueError("Grade must be between 0 and 1")
        if not Decimal("0") <= recovery <= Decimal("1"):
            raise ValueError("Recovery must be between 0 and 1")
        if price <= 0:
            raise ValueError("Price must be greater than zero")
        if not scenario_name or not scenario_name.strip():
            raise ValueError("Scenario name is required")
        if not price_unit or not price_unit.strip() or len(price_unit.strip()) > 30:
            raise ValueError("A valid price unit is required")
        if not currency or len(currency.strip()) != 3:
            raise ValueError("Currency must be a three-character code")

        baseline = self.db.get(ValueCalculation, baseline_calculation_id)
        if baseline is None:
            raise ValueError("Baseline calculation not found")
        if baseline.batch_id != batch_id:
            raise ValueError("Baseline calculation belongs to another batch")

        scenario = Scenario(
            batch_id=batch_id,
            baseline_calculation_id=baseline_calculation_id,
            created_by=user.user_id,
            scenario_name=scenario_name.strip(),
            assumed_quantity=quantity,
            assumed_grade=grade,
            assumed_recovery=recovery,
            assumed_price=price,
            assumed_stage_id=assumed_stage_id,
            price_unit=price_unit.strip(),
            currency=currency.strip().upper(),
        )
        try:
            self.db.add(scenario)
            self._commit()
            self.db.refresh(scenario)
            return scenario
        except Exception:
            self.db.rollback()
            raise

    def get_scenario(self, user: User, scenario_id):
        _authorize(user, SCENARIO_ROLES)
        scenario = self.db.get(Scenario, scenario_id)
        if scenario is None:
            raise ValueError("Scenario not found")
        try:
            MineralBatchService(self.db).get_batch_by_id(scenario.batch_id, user)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                raise ValueError("Scenario not found") from exc
            raise
        return scenario

    def list_scenarios(self, user: User, batch_id=None, created_by=None):
        _authorize(user, SCENARIO_ROLES)
        company_batches = MineralBatchService(self.db).get_all_batches(user, "asc")
        allowed_batch_ids = {batch.batch_id for batch in company_batches}
        if batch_id is not None:
            if batch_id not in allowed_batch_ids:
                return []
            allowed_batch_ids = {batch_id}
        if not allowed_batch_ids:
            return []
        query = select(Scenario).where(Scenario.batch_id.in_(allowed_batch_ids))
        if created_by is not None:
            query = query.where(Scenario.created_by == created_by)
        return list(self.db.scalars(query.order_by(Scenario.scenario_name)).all())

    def update_scenario(self, user: User, scenario_id, data):
        scenario = self.get_scenario(user, scenario_id)
        if hasattr(data, "model_dump"):
            updates = data.model_dump(exclude_unset=True)
        elif hasattr(data, "dict"):
            updates = data.dict(exclude_unset=True)
        else:
            updates = dict(data)

        allowed = {
            "scenario_name",
            "assumed_quantity",
            "assumed_grade",
            "assumed_recovery",
            "assumed_price",
            "assumed_stage_id",
            "price_unit",
            "currency",
        }
        decimals = {
            "assumed_quantity",
            "assumed_grade",
            "assumed_recovery",
            "assumed_price",
        }

        try:
            for field, value in updates.items():
                if field not in allowed:
                    continue
                if field in decimals:
                    value = self._decimal(value, field)
                if field == "assumed_quantity" and value < 0:
                    raise ValueError("Quantity cannot be negative")
                if field == "assumed_grade" and not Decimal("0") <= value <= Decimal(
                    "1"
                ):
                    raise ValueError("Grade must be between 0 and 1")
                if field == "assumed_recovery" and not Decimal("0") <= value <= Decimal(
                    "1"
                ):
                    raise ValueError("Recovery must be between 0 and 1")
                if field == "assumed_price" and value <= 0:
                    raise ValueError("Price must be greater than zero")
                if field == "scenario_name":
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError("Scenario name is required")
                    value = value.strip()
                if field == "price_unit":
                    if (
                        not isinstance(value, str)
                        or not value.strip()
                        or len(value.strip()) > 30
                    ):
                        raise ValueError("A valid price unit is required")
                    value = value.strip()
                if field == "currency":
                    if not isinstance(value, str) or len(value.strip()) != 3:
                        raise ValueError("Currency must be a three-character code")
                    value = value.strip().upper()
                setattr(scenario, field, value)

            self._commit()
            self.db.refresh(scenario)
            return scenario
        except Exception:
            self.db.rollback()
            raise

    def delete_scenario(self, user: User, scenario_id):
        scenario = self.get_scenario(user, scenario_id)
        if scenario.results:
            raise ValueError("Cannot delete a scenario that has results")
        try:
            self.db.delete(scenario)
            self._commit()
        except Exception:
            self.db.rollback()
            raise

    def calculate_scenario(self, user: User, scenario_id):
        scenario = self.get_scenario(user, scenario_id)
        baseline = self.db.get(ValueCalculation, scenario.baseline_calculation_id)
        if baseline is None:
            raise ValueError("Baseline calculation not found")

        quantity = self._decimal(scenario.assumed_quantity, "assumed_quantity")
        grade = self._decimal(scenario.assumed_grade, "assumed_grade")
        recovery = self._decimal(scenario.assumed_recovery, "assumed_recovery")
        price = self._decimal(scenario.assumed_price, "assumed_price")
        baseline_value = self._decimal(baseline.calculated_value, "calculated_value")

        simulated_value = quantity * grade * recovery * price
        difference = simulated_value - baseline_value
        percentage = (
            difference / baseline_value * Decimal("100") if baseline_value else None
        )

        try:
            latest = self.db.scalar(
                select(func.max(ScenarioResult.execution_number)).where(
                    ScenarioResult.scenario_id == scenario_id
                )
            )
            result = ScenarioResult(
                scenario_id=scenario_id,
                execution_number=(latest or 0) + 1,
                simulated_value=simulated_value,
                baseline_value=baseline_value,
                value_difference=difference,
                percentage_difference=percentage,
                calculated_at=datetime.now(timezone.utc),
            )
            self.db.add(result)
            self._commit()
            self.db.refresh(result)
            return result
        except Exception:
            self.db.rollback()
            raise

    def execute_scenario(self, user: User, scenario_id):
        return self.calculate_scenario(user, scenario_id)

    def get_results(self, user: User, scenario_id):
        self.get_scenario(user, scenario_id)
        query = (
            select(ScenarioResult)
            .where(ScenarioResult.scenario_id == scenario_id)
            .order_by(ScenarioResult.execution_number)
        )
        return list(self.db.scalars(query).all())

    def assess_result(self, user: User, scenario_id, result_id, evidence=None):
        self.get_scenario(user, scenario_id)
        result = self.db.get(ScenarioResult, result_id)
        if result is None or result.scenario_id != scenario_id:
            raise ValueError("Result does not belong to this scenario")

        evidence = evidence or []
        metrics = {
            item["metric"]
            for item in evidence
            if item.get("applicable", True)
            and item.get("metric")
            and item.get("value") is not None
        }
        required = {
            "recovery",
            "processing_capacity",
            "infrastructure",
            "regulatory",
            "market",
        }
        gaps = sorted(required - metrics)
        difference = self._decimal(result.value_difference, "value_difference")
        findings = []
        if difference < 0:
            findings.append("Scenario value is below baseline")
        if gaps:
            findings.append("Missing evidence for: " + ", ".join(gaps))

        recommendation = (
            "Proceed after validation"
            if gaps
            else "Revise scenario"
            if difference < 0
            else "Proceed"
        )
        return {
            "scenario_id": str(scenario_id),
            "result_id": str(result_id),
            "assessed_at": datetime.now(timezone.utc).isoformat(),
            "recommendation": recommendation,
            "findings": findings,
            "evidence_gaps": gaps,
        }
