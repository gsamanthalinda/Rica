import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.auth import get_current_user
from database import get_db
from models import User
from schemas.mineral_batch import MineralBatchCreate, MineralBatchResponse
from services.mineral_batch import MineralBatchService

# Every route requires a valid logged-in user
router = APIRouter(
    prefix="/mineral-batches",
    tags=["Mineral Batches"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", status_code=201, response_model=MineralBatchResponse)
def register_mineral_batch(
    payload: MineralBatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MineralBatchService(db).create_batch(payload, user)


@router.get("", response_model=list[MineralBatchResponse])
def get_all_mineral_batches(
    sort: str = Query("desc"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MineralBatchService(db).get_all_batches(user, sort)


@router.get("/search", response_model=list[MineralBatchResponse])
def search_mineral_batches(
    batch_code: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return [MineralBatchService(db).get_batch_by_code(batch_code.strip(), user)]


@router.get("/code/{batch_code}", response_model=MineralBatchResponse)
def get_mineral_batch_by_code(
    batch_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MineralBatchService(db).get_batch_by_code(batch_code.strip(), user)


@router.get("/code/{batch_code}/qr-code")
def get_mineral_batch_qr_code(
    batch_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    code = batch_code.strip()
    qr_image = MineralBatchService(db).generate_qr_code(code, user)
    return Response(
        content=qr_image,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{code}-qr.png"'},
    )


@router.put("/{batch_id}/upload-assay", response_model=MineralBatchResponse)
def upload_assay_document(
    batch_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return MineralBatchService(db).save_assay(
        batch_id, user, file.file.read(), file.filename
    )
