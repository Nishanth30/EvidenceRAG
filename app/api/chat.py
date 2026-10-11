from fastapi import APIRouter, Request
from app.schemas.responses import QueryRequest, AnswerResponse

router = APIRouter()


@router.post('/ask', response_model=AnswerResponse)
def ask(body: QueryRequest, request: Request):
    return request.app.state.rag.ask(body.query, body.top_k)
