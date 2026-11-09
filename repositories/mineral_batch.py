from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from models import MineralBatch, User


def _company_matches(company_name: str):
    """Trimmed, case-insensitive company match, used by every scoped query."""
    return func.lower(func.trim(User.company_name)) == company_name.strip().lower()


class MineralBatchRepository:
    """Data access only. Never commits or rolls back: that is owned by
    get_transactional_db. Writes use flush() so DB errors surface here."""

    def __init__(self, db: Session):
        self.db = db

    def _scoped(self, company_name: str) -> Query:
        """Batches whose creator belongs to company_name."""
        return (
            self.db.query(MineralBatch)
            .join(User, User.user_id == MineralBatch.created_by)
            .filter(_company_matches(company_name))
        )

    def get_all(
        self, company_name: str, newest_first: bool = True
    ) -> list[MineralBatch]:
        column = MineralBatch.created_at
        order = column.desc() if newest_first else column.asc()
        return self._scoped(company_name).order_by(order).all()

    def get_by_id(self, batch_id, company_name: str) -> MineralBatch | None:
        return (
            self._scoped(company_name).filter(MineralBatch.batch_id == batch_id).first()
        )

    def get_by_code(self, batch_code: str, company_name: str) -> MineralBatch | None:
        return (
            self._scoped(company_name)
            .filter(MineralBatch.batch_code == batch_code)
            .first()
        )

    def code_exists(self, batch_code: str) -> bool:
        # Deliberately unscoped: batch codes must be unique globally.
        return (
            self.db.query(MineralBatch.batch_id)
            .filter(MineralBatch.batch_code == batch_code)
            .first()
            is not None
        )

    def create(self, batch: MineralBatch) -> MineralBatch:
        self.db.add(batch)
        self.db.flush()
        self.db.refresh(batch)
        return batch

    def update_assay(
        self, batch: MineralBatch, file_data: bytes, filename: str
    ) -> MineralBatch:
        batch.assay_file_data = file_data
        batch.assay_original_filename = filename
        self.db.flush()
        self.db.refresh(batch)
        return batch
