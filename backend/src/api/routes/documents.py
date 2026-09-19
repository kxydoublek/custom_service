from fastapi import Depends, File, Query, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pycore.api import APIRouter, error_response, paginated_response, success_response
from pycore.api.routes import handle_errors
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.models import User
from src.db.session import get_db
from src.repositories.document import DocumentRepository
from src.services.ingest import (
    DOCUMENT_STATUSES,
    DocumentDetail,
    DocumentSummary,
    IngestService,
    schedule_ingest,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _not_found() -> JSONResponse:
    resp, code = error_response(
        error="文档不存在",
        error_code="NOT_FOUND",
        status_code=status.HTTP_404_NOT_FOUND,
    )
    return JSONResponse(status_code=code, content=jsonable_encoder(resp))


@router.post("")
@handle_errors
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = await file.read()
    service = IngestService(DocumentRepository(db))
    summary: DocumentSummary = await service.submit_upload(file.filename or "", payload)
    await db.commit()
    schedule_ingest(summary.id, user.id)
    return success_response(data=summary.model_dump(), message="ok")


@router.get("")
@handle_errors
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    status_filter: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user
    if status_filter is not None and status_filter not in DOCUMENT_STATUSES:
        raise ValueError("status 仅支持 queued、processing、ready、failed")
    repo = DocumentRepository(db)
    service = IngestService(repo)
    total = await repo.count(status_filter)
    documents = await repo.list_page(
        offset=(page - 1) * page_size,
        limit=page_size,
        status=status_filter,
    )
    items = [(await service.get_summary(document)).model_dump() for document in documents]
    return paginated_response(
        data=items,
        page=page,
        page_size=page_size,
        total_items=total,
    )


@router.get("/{document_id}")
@handle_errors
async def get_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del user
    repo = DocumentRepository(db)
    document = await repo.get_by_id(document_id)
    if document is None:
        return _not_found()
    detail: DocumentDetail = await IngestService(repo).get_detail(document)
    return success_response(data=detail.model_dump(), message="ok")
