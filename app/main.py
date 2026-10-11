from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api import documents, search, chat
from app.config import Settings
from app.errors import AppError
from app.ingestion.pipeline import DocumentService
from app.retrieval.retriever import Retriever
from app.generation.llm_client import LLMClient
from app.generation.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)


def create_app(settings=None, embeddings=None, llm=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        service = DocumentService(settings, embeddings)
        app.state.settings = settings
        app.state.documents = service
        app.state.retriever = Retriever(service)
        app.state.llm = llm or LLMClient(settings)
        app.state.rag = RAGPipeline(app.state.retriever, app.state.llm, settings)
        try:
            yield
        finally:
            service.close()

    app = FastAPI(title='EvidenceRAG', version='1.0.0', lifespan=lifespan,
                  description='Local document intelligence with semantic retrieval and evidence citations.')

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        if exc.status_code >= 500:
            logger.error('Service failure: %s', exc, exc_info=exc)
        return JSONResponse(status_code=exc.status_code, content={'detail': str(exc)})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.error('Unexpected request failure', exc_info=exc)
        return JSONResponse(status_code=500, content={'detail': 'Internal processing error. Check server logs.'})

    @app.get('/health')
    def health():
        with app.state.documents.lock:
            store = app.state.documents.store
            return {'status': 'ok' if store.index is not None else 'degraded',
                    'documents': len(app.state.documents.documents()), 'chunks': len(store.metadata),
                    'llm_configured': app.state.llm.configured,
                    'embedding_model': settings.embedding_model,
                    'embedding_status': 'lazy_loaded_on_first_nonempty_request',
                    'faiss_cache_persisted': store.cache_persisted}

    app.include_router(documents.router, tags=['Documents'])
    app.include_router(search.router, tags=['Retrieval'])
    app.include_router(chat.router, tags=['Generation'])
    return app


app = create_app()
