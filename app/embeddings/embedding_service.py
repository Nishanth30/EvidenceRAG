from functools import lru_cache
from threading import RLock
import numpy as np
from app.errors import AppError


@lru_cache(maxsize=2)
def load_model(name: str, revision: str, device: str, cache: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name, revision=revision or None, device=device, cache_folder=cache)


class EmbeddingService:
    def __init__(self, settings):
        self.settings = settings
        self.dimension = 384  # all-MiniLM-L6-v2 output dimension
        self._lock = RLock()

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts or any(not text.strip() for text in texts):
            raise ValueError('Embedding inputs must be non-empty text')
        with self._lock:
            try:
                model = load_model(self.settings.embedding_model, self.settings.embedding_revision,
                                   self.settings.embedding_device,
                                   str(self.settings.data_dir / 'models'))
                dimension_getter = getattr(model, 'get_embedding_dimension', None) or model.get_sentence_embedding_dimension
                if dimension_getter() != self.dimension:
                    raise ValueError('This application requires a 384-dimensional embedding model')
                vectors = model.encode(texts, batch_size=self.settings.embedding_batch_size,
                                       normalize_embeddings=True, convert_to_numpy=True,
                                       show_progress_bar=False)
                vectors = np.asarray(vectors, dtype=np.float32)
                if vectors.shape != (len(texts), self.dimension) or not np.isfinite(vectors).all():
                    raise ValueError('Invalid embedding dimensions or non-finite values')
                if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4):
                    raise ValueError('Embeddings must be normalized')
                return np.ascontiguousarray(vectors)
            except Exception as exc:
                raise AppError('Embedding model unavailable. Check the model download/cache and server logs.', 503) from exc
