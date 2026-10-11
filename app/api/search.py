from fastapi import APIRouter, Request
from app.schemas.responses import QueryRequest, SearchResponse

router = APIRouter()


@router.post('/search', response_model=SearchResponse)
def search(body: QueryRequest, request: Request):
    return request.app.state.retriever.search(body.query, body.top_k)
