"""Real-model native-runtime regression check. Run from the repository root."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Import through the production path: FAISS must be loaded before inference.
from app.main import create_app
from app.config import Settings
from app.embeddings.embedding_service import EmbeddingService
import faiss
import numpy as np

settings = Settings(_env_file=None)
encoder = EmbeddingService(settings)
vectors = encoder.encode(['A queue redelivers a message.', 'A planet orbits a star.'])
assert vectors.shape == (2, 384)
assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4)
index = faiss.IndexFlatIP(384)
index.add(vectors)
scores, ids = index.search(encoder.encode(['A queue redelivers a message.']), 1)
assert ids[0, 0] == 0 and scores[0, 0] > .99
assert create_app(settings).title == 'EvidenceRAG'
print('PASS: real MiniLM inference, dimensions, normalization, and FAISS retrieval in one process')
