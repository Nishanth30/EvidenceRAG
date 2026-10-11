import fcntl
import hashlib
from pathlib import Path
from threading import RLock
import numpy as np
from app.errors import AppError
from app.database.repository import Repository
from app.embeddings.embedding_service import EmbeddingService
from app.ingestion.parser import parse_document
from app.ingestion.chunker import split_pages
from app.retrieval.vector_store import VectorStore


class DocumentService:
    def __init__(self, settings, embeddings=None):
        self.settings = settings
        self.lock = RLock()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._file_lock = open(settings.data_dir / '.writer.lock', 'a+')
        try:
            fcntl.flock(self._file_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._file_lock.close()
            raise RuntimeError('DATA_DIR is in use. Run exactly one backend worker per data directory.') from exc
        try:
            self.embeddings = embeddings or EmbeddingService(settings)
            self.repository = Repository(settings.data_dir / 'metadata.sqlite3', settings.index_config,
                                         self.embeddings.dimension)
            self.store = VectorStore(self.repository, settings.data_dir)
        except Exception:
            self.close()
            raise

    def close(self):
        if not self._file_lock.closed:
            fcntl.flock(self._file_lock, fcntl.LOCK_UN)
            self._file_lock.close()

    def ingest(self, filename: str, content: bytes, content_type: str | None = None):
        filename = Path(filename.replace('\\', '/')).name.strip()
        if not filename or len(filename) > 255:
            raise AppError('Filename must contain 1-255 characters')
        pages = parse_document(filename, content, content_type,
                               self.settings.max_upload_mb * 1024 * 1024,
                               self.settings.max_extracted_chars)
        document_id = hashlib.sha256(content).hexdigest()
        with self.lock:
            if self.repository.contains(document_id):
                raise AppError('Identical document content is already indexed', 409)
            chunks = split_pages(pages, document_id, self.settings.chunk_size,
                                 self.settings.chunk_overlap, self.settings.chunk_strategy)
            vectors = self.embeddings.encode([c.text for c in chunks])
            if vectors.shape != (len(chunks), self.embeddings.dimension) or not np.isfinite(vectors).all():
                raise AppError('Embedding output is invalid', 503)
            if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4):
                raise AppError('Embedding output is not normalized', 503)
            result = self.repository.insert(document_id, filename, content, pages, chunks, vectors)
            self.store.rebuild()
            return result

    def delete(self, document_id: str):
        with self.lock:
            if not self.repository.delete(document_id):
                raise AppError('Document not found', 404)
            self.store.rebuild()

    def documents(self):
        with self.lock:
            return self.repository.documents()
