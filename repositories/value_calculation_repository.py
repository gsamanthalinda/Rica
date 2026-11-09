from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from models import ValueCalculation
import uuid


class ValueCalculationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, calculation_data: Dict) -> ValueCalculation:
        calculation_data = calculation_data.copy()
        for key in ["batch_id", "batch_history_id", "calculated_by"]:
            if isinstance(calculation_data.get(key), str):
                calculation_data[key] = uuid.UUID(calculation_data[key])

        calculation = ValueCalculation(**calculation_data)
        self.db.add(calculation)
        self.db.commit()
        self.db.refresh(calculation)
        return calculation

    def get(self, calculation_id: uuid.UUID) -> Optional[ValueCalculation]:
        return (
            self.db.query(ValueCalculation)
            .filter(ValueCalculation.calculation_id == calculation_id)
            .first()
        )

    def get_by_batch(self, batch_id: uuid.UUID) -> List[ValueCalculation]:
        return (
            self.db.query(ValueCalculation)
            .filter(ValueCalculation.batch_id == batch_id)
            .all()
        )

    def get_by_batch_history(
        self, batch_history_id: uuid.UUID
    ) -> List[ValueCalculation]:
        return (
            self.db.query(ValueCalculation)
            .filter(ValueCalculation.batch_history_id == batch_history_id)
            .all()
        )
