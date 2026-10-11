import hashlib
import re
import numpy as np
import pytest
from app.config import Settings
from app.ingestion.pipeline import DocumentService


class FakeEmbeddings:
    """Deterministic unit-test double; never used by the app or reported evaluation."""
    dimension = 64

    def encode(self, texts):
        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            for token in re.findall(r'\w+', text.lower()):
                index = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % self.dimension
                vectors[i, index] += 1
            if not vectors[i].any():
                vectors[i, 0] = 1
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path, chunk_size=100, chunk_overlap=20,
                    similarity_threshold=0.1)


@pytest.fixture
def service(settings):
    instance = DocumentService(settings, FakeEmbeddings())
    yield instance
    instance.close()
