from typing import Literal
from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(None, ge=1, le=20)

    @field_validator('query')
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Query must not be blank')
        return value.strip()


class Document(BaseModel):
    id: str
    filename: str
    content_hash: str
    page_count: int
    chunk_count: int
    created_at: str


class Passage(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    start: int
    end: int
    text: str
    score: float


class SearchResponse(BaseModel):
    results: list[Passage]
    elapsed_ms: float
    insufficient_evidence: bool
    threshold: float


class Source(Passage):
    source_id: str


class AnswerResponse(BaseModel):
    answer: str
    status: Literal['answered', 'insufficient_evidence', 'error']
    sources: list[Source]
    cited_source_ids: list[str] = []
    error_code: Literal['llm_unavailable', 'invalid_model_response', 'invalid_citations'] | None = None
    warning: str | None = None
