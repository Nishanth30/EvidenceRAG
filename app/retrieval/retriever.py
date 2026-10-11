from time import perf_counter
from app.errors import AppError
from app.schemas.responses import SearchResponse


class Retriever:
    def __init__(self, documents):
        self.documents = documents

    def search(self, query: str, top_k: int | None = None) -> SearchResponse:
        settings = self.documents.settings
        top_k = top_k if top_k is not None else settings.top_k
        if not query.strip() or len(query) > 2000 or not 1 <= top_k <= 20:
            raise AppError('Supply a non-empty query (up to 2000 characters) and top_k between 1 and 20', 422)
        started = perf_counter()
        with self.documents.lock:
            if self.documents.store.index is None:
                self.documents.store.rebuild()
            if not self.documents.store.metadata:
                results = []
            else:
                vector = self.documents.embeddings.encode([query.strip()])
                results = self.documents.store.search(vector, top_k)
        return SearchResponse(results=results, elapsed_ms=(perf_counter() - started) * 1000,
                              insufficient_evidence=not results or results[0]['score'] < settings.similarity_threshold,
                              threshold=settings.similarity_threshold)
