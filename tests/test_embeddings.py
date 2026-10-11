import numpy as np
import pytest
from app.errors import AppError
from app.embeddings.embedding_service import EmbeddingService


def test_encoder_checks_dimension_normalization_and_empty_input(settings, monkeypatch):
    import app.embeddings.embedding_service as module
    class Model:
        def get_embedding_dimension(self):
            return 384
        def encode(self, texts, **kwargs):
            assert kwargs['normalize_embeddings'] is True
            assert kwargs['batch_size'] == settings.embedding_batch_size
            out = np.zeros((len(texts), 384), dtype=np.float32)
            out[:, 0] = 1
            return out
    model = Model()
    monkeypatch.setattr(module, 'load_model', lambda *args: model)
    encoder = EmbeddingService(settings)
    assert encoder.encode(['hello', 'world']).shape == (2, 384)
    with pytest.raises(ValueError):
        encoder.encode([' '])
    with pytest.raises(ValueError):
        encoder.encode([])
    monkeypatch.setattr(model, 'get_embedding_dimension', lambda: 12)
    with pytest.raises(AppError):
        encoder.encode(['hello'])
    monkeypatch.setattr(model, 'get_embedding_dimension', lambda: 384)
    monkeypatch.setattr(model, 'encode', lambda *args, **kwargs: np.zeros((1, 384), dtype=np.float32))
    with pytest.raises(AppError):
        encoder.encode(['hello'])
