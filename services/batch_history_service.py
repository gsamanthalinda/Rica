import os
import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from models import User
from models.batch_history import BatchHistory
from models.mineral_batch import MineralBatch
from repositories import batch_history_repository as repository
from schemas.batch_history import BatchHistoryCreate, BatchHistoryUpdate
from services.mineral_batch import (
    READ_ROLES,
    WRITE_ROLES,
    MineralBatchService,
    _authorize,
)


UPLOAD_ROOT = Path("uploads")
ASSAY_DIR = UPLOAD_ROOT / "assay"
ASSAY_URL_PREFIX = "/batch-history/files/assay/"

MAX_BYTES = 10 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024

# Declared (client) content type -> extension. Only used as a cross-check;
# the real type is detected from the file's own bytes.
ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

# Magic-byte signatures: (prefix, extension)
FILE_SIGNATURES = [
    (b"%PDF-", ".pdf"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
]

MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
}

# We only ever serve files we generated ourselves: <uuid4>.<ext>
ASSAY_FILENAME_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(pdf|png|jpg)$"
)

# Roles follow the mineral batch service:
#   read  -> operations manager + supply chain manager
#   write -> operations manager only (create, update, delete)


# --- Authorization helpers --------------------------------------------------
def _authorize_batch(
    db: Session,
    user: User,
    batch_id: UUID,
    allowed_roles: set,
) -> MineralBatch:
    """Role check, then the mineral batch service's own company-level rule.

    Raises 404 if the batch is missing or belongs to another company.
    """
    _authorize(user, allowed_roles)

    return MineralBatchService(db).get_batch_by_id(batch_id, user)


def _authorize_company_access(
    db: Session,
    user: User,
    batch_id: UUID,
) -> MineralBatch:
    """Role-agnostic check: the user just has to belong to the batch's company."""
    batch = repository.get_mineral_batch_by_id(db, batch_id)

    # Same response whether the batch is missing or belongs to another company
    if batch is None or not MineralBatchService(db)._same_company(user, batch):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assay file not found",
        )

    return batch


def _get_authorized_history(
    db: Session,
    user: User,
    history_id: UUID,
    allowed_roles: set,
) -> BatchHistory:
    _authorize(user, allowed_roles)

    history = repository.get_batch_history_by_id(db, history_id)

    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch history record not found",
        )

    try:
        _authorize_batch(db, user, history.batch_id, allowed_roles)
    except HTTPException as exc:
        # Another company's record looks exactly like a missing one
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch history record not found",
            ) from exc
        raise

    return history


# --- Validation helpers -----------------------------------------------------
def _parse_history_data(data: str, schema):
    try:
        return schema.model_validate_json(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(include_url=False),
        ) from exc


def _validate_batch_and_stage(
    db: Session,
    batch_id: UUID,
    stage_id: int,
):
    if repository.get_mineral_batch_by_id(db, batch_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    if repository.get_processing_stage_by_id(db, stage_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found",
        )


def _validate_unique_batch_stage(
    db: Session,
    batch_id: UUID,
    stage_id: int,
    exclude_history_id: UUID | None = None,
):
    existing_history = repository.get_batch_history_by_batch_and_stage(
        db,
        batch_id,
        stage_id,
    )

    if existing_history is not None and (
        exclude_history_id is None or existing_history.history_id != exclude_history_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A history record already exists for this batch and stage.",
        )


def _refresh_current_stage(
    db: Session,
    batch_id: UUID,
):
    batch = repository.get_mineral_batch_by_id(db, batch_id)

    if batch is None:
        return

    latest_stage = repository.get_latest_stage_for_batch(
        db,
        batch_id,
    )

    if latest_stage is not None:
        batch.stage_id = latest_stage.stage_id
        repository.update_mineral_batch(db, batch)


# --- Internal service functions (NO authorization) --------------------------
# These perform no access checks. Routers must not call them directly; the
# authorized functions further down are the ones exposed through the API.
def get_batch_history_by_id(
    db: Session,
    history_id: UUID,
):
    return repository.get_batch_history_by_id(db, history_id)


def create_batch_history(
    db: Session,
    history_data: BatchHistoryCreate,
):
    _validate_batch_and_stage(
        db,
        history_data.batch_id,
        history_data.current_stage_id,
    )
    _validate_unique_batch_stage(
        db,
        history_data.batch_id,
        history_data.current_stage_id,
    )

    history = BatchHistory(**history_data.model_dump())
    created_history = repository.create_batch_history(
        db,
        history,
    )

    _refresh_current_stage(db, history.batch_id)

    return created_history


def update_batch_history(
    db: Session,
    history_id: UUID,
    history_data: BatchHistoryUpdate,
):
    history = repository.get_batch_history_by_id(db, history_id)

    if history is None:
        return None

    update_data = history_data.model_dump(exclude_unset=True)

    if "batch_id" in update_data or "current_stage_id" in update_data:
        batch_id = update_data.get("batch_id", history.batch_id)
        stage_id = update_data.get(
            "current_stage_id",
            history.current_stage_id,
        )

        _validate_batch_and_stage(db, batch_id, stage_id)
        _validate_unique_batch_stage(
            db,
            batch_id,
            stage_id,
            exclude_history_id=history_id,
        )

    original_batch_id = history.batch_id

    for field, value in update_data.items():
        setattr(history, field, value)

    updated_history = repository.update_batch_history(
        db,
        history,
    )

    _refresh_current_stage(db, original_batch_id)

    if history.batch_id != original_batch_id:
        _refresh_current_stage(db, history.batch_id)

    return updated_history


def delete_batch_history(
    db: Session,
    history_id: UUID,
) -> bool:
    history = repository.get_batch_history_by_id(db, history_id)

    if history is None:
        return False

    batch_id = history.batch_id
    assay_url = history.assay_document_url

    repository.delete_batch_history(db, history)
    _refresh_current_stage(db, batch_id)

    # Only remove the file once the record is really gone
    _delete_assay_file(assay_url)

    return True


# --- Authorized reads and delete (used by the router) -----------------------
def get_batch_history_by_id_or_404(
    db: Session,
    user: User,
    history_id: UUID,
) -> BatchHistory:
    return _get_authorized_history(db, user, history_id, READ_ROLES)


def get_batch_history_by_batch(
    db: Session,
    user: User,
    batch_id: UUID,
    skip: int = 0,
    limit: int = 100,
):
    _authorize_batch(db, user, batch_id, READ_ROLES)

    return repository.get_batch_history_by_batch(
        db,
        batch_id,
        skip=skip,
        limit=limit,
    )


def delete_batch_history_or_404(
    db: Session,
    user: User,
    history_id: UUID,
) -> None:
    _get_authorized_history(db, user, history_id, WRITE_ROLES)
    delete_batch_history(db, history_id)


#Assay documents upload
class UnsupportedMediaTypeException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF, PNG or JPEG files are allowed",
        )


class FileTooLargeException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File is too large (10 MB maximum)",
        )


def _read_upload_limited(upload: UploadFile) -> bytes:
    """Read the upload in chunks and abort as soon as it exceeds MAX_BYTES,
    so an oversized file is never fully loaded into memory."""
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = upload.file.read(READ_CHUNK_BYTES)

        if not chunk:
            break

        total += len(chunk)

        if total > MAX_BYTES:
            raise FileTooLargeException()

        chunks.append(chunk)

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    return b"".join(chunks)


def _detect_extension(content: bytes) -> str | None:
    for signature, extension in FILE_SIGNATURES:
        if content.startswith(signature):
            return extension

    return None


def _assay_filename_from_url(url: str | None) -> str | None:
    if not url or not url.startswith(ASSAY_URL_PREFIX):
        return None

    filename = url[len(ASSAY_URL_PREFIX) :]

    return filename if ASSAY_FILENAME_RE.fullmatch(filename) else None


def _delete_assay_file(url: str | None) -> None:
    """Best-effort removal of a stored assay file (never raises)."""
    filename = _assay_filename_from_url(url)

    if filename is None:
        return

    try:
        (ASSAY_DIR / filename).unlink(missing_ok=True)
    except OSError:
        pass


def handle_assay_upload(
    content_type: str | None,
    content: bytes,
) -> str:
    """Validate and store assay bytes. Returns the file's private URL.

    - declared content type must be allowed
    - size must not exceed MAX_BYTES
    - the real type, detected from magic bytes, must agree with the declared type
    - the filename is always generated by the server
    """
    declared_extension = ALLOWED_TYPES.get(content_type or "")

    if declared_extension is None:
        raise UnsupportedMediaTypeException()

    if len(content) > MAX_BYTES:
        raise FileTooLargeException()

    if _detect_extension(content) != declared_extension:
        raise UnsupportedMediaTypeException()

    ASSAY_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4()}{declared_extension}"
    file_path = ASSAY_DIR / filename
    file_path.write_bytes(content)

    try:
        os.chmod(file_path, 0o600)
    except OSError:
        pass

    return f"{ASSAY_URL_PREFIX}{filename}"


def _save_upload(upload: UploadFile) -> str:
    """Read an uploaded file with the size limit enforced while reading."""
    content = _read_upload_limited(upload)

    return handle_assay_upload(upload.content_type, content)


# --- Assay documents: authorized download -----------------------------------
def get_assay_document(
    db: Session,
    user: User,
    filename: str,
) -> FileResponse:
    # 1. Strict allow-list on the filename: blocks traversal, odd encodings, etc.
    if not ASSAY_FILENAME_RE.fullmatch(filename):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assay file not found",
        )

    # 2. The file must belong to a history record we know about
    history = repository.get_batch_history_by_assay_url(
        db,
        f"{ASSAY_URL_PREFIX}{filename}",
    )

    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assay file not found",
        )

    # 3. Authenticated (router) + same company as the parent batch. No role check.
    _authorize_company_access(db, user, history.batch_id)

    # 4. Defense in depth: resolved path must stay inside the assay directory
    assay_root = ASSAY_DIR.resolve()
    file_path = (ASSAY_DIR / filename).resolve()

    if file_path.parent != assay_root or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assay file not found",
        )

    return FileResponse(
        path=file_path,
        media_type=MEDIA_TYPES[file_path.suffix],
        filename=filename,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


# --- Authorized create / update (form payload + optional assay file) --------
def create_batch_history_with_assay(
    db: Session,
    user: User,
    data: str,
    assay_file: UploadFile | None = None,
) -> BatchHistory:
    history_data = _parse_history_data(data, BatchHistoryCreate)

    _authorize_batch(db, user, history_data.batch_id, WRITE_ROLES)
    _validate_batch_and_stage(
        db,
        history_data.batch_id,
        history_data.current_stage_id,
    )
    _validate_unique_batch_stage(
        db,
        history_data.batch_id,
        history_data.current_stage_id,
    )

    history_values = history_data.model_dump()
    assay_url = None

    if assay_file is not None:
        assay_url = _save_upload(assay_file)
        history_values["assay_document_url"] = assay_url

    try:
        history = BatchHistory(**history_values)
        created_history = repository.create_batch_history(
            db,
            history,
        )
        _refresh_current_stage(db, history.batch_id)
    except Exception:
       
        _delete_assay_file(assay_url)
        raise

    return created_history


def update_batch_history_with_assay(
    db: Session,
    user: User,
    history_id: UUID,
    data: str,
    assay_file: UploadFile | None = None,
) -> BatchHistory:
    history_data = _parse_history_data(data, BatchHistoryUpdate)
    history = _get_authorized_history(db, user, history_id, WRITE_ROLES)

    update_data = history_data.model_dump(exclude_unset=True)

    if "batch_id" in update_data or "current_stage_id" in update_data:
        batch_id = update_data.get("batch_id", history.batch_id)
        stage_id = update_data.get(
            "current_stage_id",
            history.current_stage_id,
        )

        # Moving a record to another batch requires access to the target too
        if batch_id != history.batch_id:
            _authorize_batch(db, user, batch_id, WRITE_ROLES)

        _validate_batch_and_stage(db, batch_id, stage_id)
        _validate_unique_batch_stage(
            db,
            batch_id,
            stage_id,
            exclude_history_id=history_id,
        )

    original_batch_id = history.batch_id
    old_assay_url = history.assay_document_url
    new_assay_url = None

    for field, value in update_data.items():
        setattr(history, field, value)

    if assay_file is not None:
        new_assay_url = _save_upload(assay_file)
        history.assay_document_url = new_assay_url

    try:
        updated_history = repository.update_batch_history(
            db,
            history,
        )

        _refresh_current_stage(db, original_batch_id)

        if history.batch_id != original_batch_id:
            _refresh_current_stage(db, history.batch_id)
    except Exception:
        _delete_assay_file(new_assay_url)
        raise

    # The replaced document is no longer referenced, so remove it
    if new_assay_url is not None and old_assay_url != new_assay_url:
        _delete_assay_file(old_assay_url)

    return updated_history
