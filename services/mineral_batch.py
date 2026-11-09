import io
import logging
import uuid

import qrcode
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import User, UserRole
from models.mineral_batch import MineralBatch
from repositories.mineral_batch import MineralBatchRepository
from schemas.mineral_batch import MineralBatchCreate

logger = logging.getLogger("uvicorn.error")

READ_ROLES = {UserRole.OPERATIONS_MANAGER, UserRole.SUPPLY_CHAIN_MANAGER}
WRITE_ROLES = {UserRole.OPERATIONS_MANAGER}


def _authorize(user: User | None, allowed: set = WRITE_ROLES) -> None:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    if user.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access.",
        )


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


class MineralBatchService:
    def __init__(self, db: Session):

        self.repository = MineralBatchRepository(db)

    def _require_company(self, user: User) -> str:

        company = _normalize(user.company_name)
        if not company:
            raise HTTPException(status_code=404, detail="Mineral batch not found.")
        return company

    def get_all_batches(self, user: User, sort: str = "desc") -> list[MineralBatch]:
        _authorize(user, READ_ROLES)
        if sort not in {"asc", "desc"}:
            raise HTTPException(status_code=422, detail="sort must be 'asc' or 'desc'.")
        company = _normalize(user.company_name)
        if not company:
            return []
        try:
            return self.repository.get_all(
                company_name=company, newest_first=(sort == "desc")
            )
        except SQLAlchemyError as exc:
            logger.exception("get_all_batches failed")
            raise HTTPException(
                status_code=500, detail="Could not retrieve mineral batches."
            ) from exc

    def get_batch_by_id(self, batch_id: uuid.UUID, user: User) -> MineralBatch:
        _authorize(user, READ_ROLES)
        company = self._require_company(user)
        try:
            batch = self.repository.get_by_id(batch_id, company)
        except SQLAlchemyError as exc:
            logger.exception("get_batch_by_id failed")
            raise HTTPException(
                status_code=500, detail="Could not retrieve the mineral batch."
            ) from exc
        if batch is None:
            raise HTTPException(status_code=404, detail="Mineral batch not found.")
        return batch

    def get_batch_by_code(self, batch_code: str, user: User) -> MineralBatch:
        _authorize(user, READ_ROLES)
        company = self._require_company(user)
        try:
            batch = self.repository.get_by_code(batch_code, company)
        except SQLAlchemyError as exc:
            logger.exception("get_batch_by_code failed")
            raise HTTPException(
                status_code=500, detail="Could not retrieve the mineral batch."
            ) from exc
        if batch is None:
            raise HTTPException(status_code=404, detail="Mineral batch not found.")
        return batch

    def generate_qr_code(self, batch_code: str, user: User) -> bytes:
        _authorize(user, READ_ROLES)
        self.get_batch_by_code(batch_code, user)
        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(batch_code)
            qr.make(fit=True)
            image = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()
        except Exception as exc:
            logger.exception("generate_qr_code failed")
            raise HTTPException(
                status_code=500, detail="Could not generate the batch QR code."
            ) from exc

    def create_batch(self, payload: MineralBatchCreate, user: User) -> MineralBatch:
        _authorize(user, WRITE_ROLES)
        if payload.mineral_type.strip().upper() != "COPPER":
            raise HTTPException(
                status_code=422, detail="Only COPPER batches are supported."
            )
        try:
            batch = MineralBatch(
                created_by=user.user_id,
                batch_code=self._generate_unique_code(),
                mineral_type="COPPER",
                source_type=payload.source_type,
                quantity_tonnes=payload.quantity_tonnes,
                grade=payload.grade,
                recovery=payload.recovery,
                stage_id=payload.stage_id,
            )
            return self.repository.create(batch)
        except SQLAlchemyError as exc:
            logger.exception("create_batch failed")
            raise HTTPException(
                status_code=500, detail="Could not register the mineral batch."
            ) from exc

    def save_assay(
        self, batch_id: uuid.UUID, user: User, file_data: bytes, filename: str
    ) -> MineralBatch:
        _authorize(user, WRITE_ROLES)

        batch = self.get_batch_by_id(batch_id, user)
        try:
            return self.repository.update_assay(batch, file_data, filename)
        except SQLAlchemyError as exc:
            logger.exception("save_assay failed")
            raise HTTPException(
                status_code=500, detail="Could not upload the assay document."
            ) from exc

    def _generate_unique_code(self) -> str:
        while True:
            code = f"CU-{uuid.uuid4().hex[:8].upper()}"
            if not self.repository.code_exists(code):
                return code
