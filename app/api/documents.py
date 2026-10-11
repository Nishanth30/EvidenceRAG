from fastapi import APIRouter, Request, UploadFile, Response
from app.errors import AppError
from app.schemas.responses import Document

router = APIRouter()


@router.post('/documents', response_model=Document, status_code=201)
def upload_document(request: Request, file: UploadFile):
    limit = request.app.state.settings.max_upload_mb * 1024 * 1024
    try:
        if file.size is not None and file.size > limit:
            raise AppError('File exceeds the upload size limit', 413)
        content = file.file.read(limit + 1)
        return request.app.state.documents.ingest(file.filename or '', content, file.content_type)
    finally:
        file.file.close()


@router.get('/documents', response_model=list[Document])
def list_documents(request: Request):
    return request.app.state.documents.documents()


@router.delete('/documents/{document_id}', status_code=204)
def delete_document(document_id: str, request: Request):
    request.app.state.documents.delete(document_id)
    return Response(status_code=204)
