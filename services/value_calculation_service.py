from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from repositories.value_calculation_repository import ValueCalculationRepository
from models import (
    ValueCalculation,
    MineralBatch,
    BatchHistory,
    ProcessingStage,
    User,
    UserRole,
)
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date
import requests
import logging
from core.config import settings

logger = logging.getLogger(__name__)


class PriceUnavailableError(Exception):
    pass


class NoUserAvailableError(Exception):
    pass


class ValueCalculationService:
    def __init__(self, db: Session):
        self.repository = ValueCalculationRepository(db)

    def require_supply_chain_manager(self, current_user: User | None) -> User:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        if current_user.role != UserRole.SUPPLY_CHAIN_MANAGER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only supply chain managers can access value calculations",
            )
        return current_user

    def _check_company_access(
        self, current_user: User | None, batch_id: uuid.UUID
    ) -> None:
        if current_user is None or not current_user.company_name:
            return
        db = self.repository.db
        batch = db.query(MineralBatch).filter(MineralBatch.batch_id == batch_id).first()
        if not batch:
            return
        creator = db.query(User).filter(User.user_id == batch.created_by).first()
        if creator is None or not creator.company_name:
            return
        if current_user.company_name != creator.company_name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access batches from a different company",
            )

    def _fetch_lme_price(self, price_date=None) -> Decimal:
        api_key = settings.LME_API_KEY
        api_url = settings.LME_API_URL
        symbol = settings.LME_SYMBOL
        unit_to_tonne = settings.LME_UNIT_TO_TONNE

        if not api_key or not api_url:
            raise PriceUnavailableError("LME API not configured properly")

        if unit_to_tonne <= 0:
            raise PriceUnavailableError("LME_UNIT_TO_TONNE must be positive")

        if price_date is None:
            endpoint = f"{api_url}/latest"
            params = {
                "access_key": api_key,
                "base": "USD",
                "symbols": symbol,
            }
        else:
            endpoint = f"{api_url}/{price_date}"
            params = {
                "access_key": api_key,
                "base": "USD",
                "symbols": symbol,
            }

        try:
            response = requests.get(endpoint, params=params, timeout=10)
            if response.status_code != 200:
                logger.error(
                    f"LME API request failed: HTTP {response.status_code} {response.text[:300]}"
                )
                raise PriceUnavailableError("LME API request failed")

            data = response.json()
            if not data.get("success"):
                logger.error(f"LME API returned success=false: {data.get('error')}")
                raise PriceUnavailableError("LME API returned success=false")

            rates = data.get("rates", {})

            usd_price = rates.get(f"USD{symbol}")
            if usd_price is not None:
                price_per_unit = Decimal(str(usd_price))
            else:
                rate_value = rates.get(symbol)
                if rate_value is None:
                    logger.error(
                        f"LME API missing {symbol}; keys returned: {list(rates.keys())}"
                    )
                    raise PriceUnavailableError(
                        f"LME API response missing rate for symbol {symbol}"
                    )
                rate = Decimal(str(rate_value))
                if rate <= 0:
                    logger.error("LME API returned non-positive rate")
                    raise PriceUnavailableError("LME API returned non-positive rate")
                price_per_unit = Decimal(1) / rate

            if price_per_unit <= 0:
                logger.error("LME API returned non-positive price")
                raise PriceUnavailableError("LME API returned non-positive price")

            price_per_tonne = price_per_unit * Decimal(str(unit_to_tonne))
            return price_per_tonne.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        except requests.RequestException as e:
            logger.error(f"LME API request exception: {type(e).__name__}")
            raise PriceUnavailableError("LME API request failed") from e
        except (InvalidOperation, ValueError) as e:
            logger.error(f"LME API returned an unreadable response: {type(e).__name__}")
            raise PriceUnavailableError(
                "LME API returned an unreadable response"
            ) from e

    def get_default_user_id(self) -> uuid.UUID:
        user = self.repository.db.query(User).first()
        if not user:
            raise NoUserAvailableError("No users found in the system")
        return user.user_id

    def calculate_batch_value(
        self, batch_id: uuid.UUID, current_user: User | None = None
    ) -> ValueCalculation:
        if current_user is not None:
            self.require_supply_chain_manager(current_user)
        self._check_company_access(current_user, batch_id)
        try:
            user_id = self.get_default_user_id()
            return self.calculate_for_batch(batch_id=batch_id, user_id=user_id)
        except NoUserAvailableError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No users found in the system",
            )
        except LookupError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )
        except PriceUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Live LME price unavailable, try again later",
            )

    def calculate_for_batch(
        self, batch_id: uuid.UUID, user_id: uuid.UUID
    ) -> ValueCalculation:
        batch = (
            self.repository.db.query(MineralBatch)
            .filter(MineralBatch.batch_id == batch_id)
            .first()
        )

        if not batch:
            raise LookupError(f"Batch not found: {batch_id}")

        history = (
            self.repository.db.query(BatchHistory)
            .filter(BatchHistory.batch_id == batch_id)
            .order_by(BatchHistory.occurred_at.desc())
            .first()
        )

        if not history:
            raise LookupError(f"No history found for batch: {batch_id}")

        quantity = (
            history.quantity_tonnes
            if history.quantity_tonnes is not None
            else batch.quantity_tonnes
        )
        grade = history.grade if history.grade is not None else batch.grade
        recovery = history.recovery if history.recovery is not None else batch.recovery

        if quantity is None:
            raise ValueError("Quantity is required on the batch or its latest history")
        if quantity < 0:
            raise ValueError("Quantity must be non-negative")
        if grade is None:
            raise ValueError("Grade is required on the batch or its latest history")
        if grade < 0 or grade > 1:
            raise ValueError("Grade must be between 0 and 1")
        if recovery is not None and (recovery < 0 or recovery > 1):
            raise ValueError("Recovery must be between 0 and 1")

        price_date = date.today()
        reference_price = self._fetch_lme_price()

        contained_metal_tonnes = quantity * grade
        if recovery is None:
            recoverable_metal_tonnes = contained_metal_tonnes
        else:
            recoverable_metal_tonnes = contained_metal_tonnes * recovery

        calculated_value = recoverable_metal_tonnes * reference_price

        calculation_data = {
            "batch_id": batch_id,
            "batch_history_id": history.history_id,
            "stage_id": history.current_stage_id,
            "quantity": quantity,
            "quantity_unit": "tonnes",
            "grade": grade,
            "recovery": recovery,
            "reference_price": reference_price,
            "current_price": reference_price,
            "price_unit": "USD/tonne",
            "currency": "USD",
            "price_source": "Metals-API (LME copper)",
            "price_date": price_date,
            "contained_metal_tonnes": contained_metal_tonnes,
            "recoverable_metal_tonnes": recoverable_metal_tonnes,
            "calculated_value": calculated_value,
            "calculated_by": user_id,
        }

        return self.repository.create(calculation_data)

    def get_value_table(
        self, batch_id: uuid.UUID, current_user: User | None = None, price_date=None
    ) -> dict:
        if current_user is not None:
            self.require_supply_chain_manager(current_user)
        self._check_company_access(current_user, batch_id)
        try:
            return self._build_value_table(batch_id, price_date=price_date)
        except LookupError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
            )
        except PriceUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Live LME price unavailable, try again later",
            )

    def _build_value_table(self, batch_id: uuid.UUID, price_date=None) -> dict:
        db = self.repository.db

        batch = db.query(MineralBatch).filter(MineralBatch.batch_id == batch_id).first()
        if not batch:
            raise LookupError(f"Batch not found: {batch_id}")

        events = (
            db.query(BatchHistory, ProcessingStage)
            .join(
                ProcessingStage,
                ProcessingStage.stage_id == BatchHistory.current_stage_id,
            )
            .filter(BatchHistory.batch_id == batch_id)
            .order_by(BatchHistory.occurred_at.asc())
            .all()
        )
        if not events:
            raise LookupError(f"No history found for batch: {batch_id}")

        latest_per_stage = {}
        for history, stage in events:
            latest_per_stage[stage.stage_id] = (history, stage)
        ordered = sorted(
            latest_per_stage.values(), key=lambda pair: pair[1].stage_order
        )

        price = self._fetch_lme_price(price_date)

        rows = []
        previous_value = None
        for history, stage in ordered:
            quantity = (
                history.quantity_tonnes
                if history.quantity_tonnes is not None
                else batch.quantity_tonnes
            )
            grade = history.grade if history.grade is not None else batch.grade
            recovery = (
                history.recovery if history.recovery is not None else batch.recovery
            )

            if quantity is None or quantity < 0:
                raise ValueError(f"Invalid quantity at stage {stage.stage_name}")
            if grade is None or grade < 0 or grade > 1:
                raise ValueError(f"Invalid grade at stage {stage.stage_name}")
            if recovery is not None and (recovery < 0 or recovery > 1):
                raise ValueError(f"Invalid recovery at stage {stage.stage_name}")

            contained = quantity * grade
            recoverable = contained if recovery is None else contained * recovery
            total_value = recoverable * price
            value_lost = (contained - recoverable) * price

            if previous_value is not None and previous_value > 0:
                change_pct = (
                    (total_value - previous_value) / previous_value * 100
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                change_pct = None
            previous_value = total_value

            rows.append(
                {
                    "stage_id": stage.stage_id,
                    "stage_name": stage.stage_name,
                    "stage_order": stage.stage_order,
                    "occurred_at": history.occurred_at,
                    "quantity_tonnes": quantity,
                    "grade": grade,
                    "contained_metal_tonnes": contained,
                    "recovery": recovery,
                    "recoverable_metal_tonnes": recoverable,
                    "total_value": total_value,
                    "value_lost": value_lost,
                    "value_change_pct": change_pct,
                }
            )

        return {
            "batch_id": batch.batch_id,
            "batch_code": batch.batch_code,
            "reference_price": price,
            "price_unit": "USD/tonne",
            "currency": "USD",
            "price_source": "Metals-API (LME copper)",
            "price_date": price_date if price_date is not None else date.today(),
            "rows": rows,
        }

    def get_calculations_by_batch(
        self, batch_id: uuid.UUID, current_user: User | None = None
    ) -> List[ValueCalculation]:
        if current_user is not None:
            self.require_supply_chain_manager(current_user)
        self._check_company_access(current_user, batch_id)
        return self.repository.get_by_batch(batch_id)

    def get_calculations_by_batch_history(
        self, batch_history_id: uuid.UUID, current_user: User | None = None
    ) -> List[ValueCalculation]:
        db = self.repository.db
        history = (
            db.query(BatchHistory)
            .filter(BatchHistory.history_id == batch_history_id)
            .first()
        )
        if history is not None:
            if current_user is not None:
                self.require_supply_chain_manager(current_user)
            self._check_company_access(current_user, history.batch_id)
        return self.repository.get_by_batch_history(batch_history_id)
