import numpy as np
import pytest
from app.errors import AppError
from app.ingestion.pipeline import DocumentService
from app.retrieval.retriever import Retriever
from conftest import FakeEmbeddings


def test_search_restart_delete_and_cache_recovery(service, settings):
    doc = service.ingest('queue.txt', b'idempotency keys prevent duplicate message processing')
    other = service.ingest('space.txt', b'planet orbit galaxy sun telescope')
    retriever = Retriever(service)
    assert retriever.search('duplicate message').results[0].document_id == doc['id']
    assert (settings.data_dir / 'index.faiss').exists()
    service.close()
    (settings.data_dir / 'index.faiss').write_bytes(b'corrupt cache')
    restarted = DocumentService(settings, FakeEmbeddings())
    try:
        assert Retriever(restarted).search('duplicate message').results[0].document_id == doc['id']
        restarted.delete(doc['id'])
        assert all(r.document_id == other['id'] for r in Retriever(restarted).search('duplicate message').results)
        restarted.delete(other['id'])
        assert Retriever(restarted).search('anything').results == []
    finally:
        restarted.close()


def test_missing_cache_rebuilt(service, settings):
    service.ingest('x.txt', b'transactions commit atomically')
    service.close()
    (settings.data_dir / 'index.faiss').unlink()
    restarted = DocumentService(settings, FakeEmbeddings())
    assert restarted.store.index.ntotal == 1
    restarted.close()


def test_configuration_mismatch_and_process_lock(service, settings):
    with pytest.raises(RuntimeError, match='one backend worker'):
        DocumentService(settings, FakeEmbeddings())
    service.close()
    changed = settings.model_copy(update={'chunk_size': 120})
    with pytest.raises(AppError, match='configuration changed'):
        DocumentService(changed, FakeEmbeddings())


def test_transaction_failure_does_not_publish_vectors(service, monkeypatch):
    def fail(*args):
        raise RuntimeError('simulated metadata failure')
    monkeypatch.setattr(service.repository, 'insert', fail)
    with pytest.raises(RuntimeError):
        service.ingest('x.txt', b'atomic transaction')
    assert service.documents() == [] and service.store.index.ntotal == 0


def test_sqlite_rollback_during_chunk_insert(service):
    from app.ingestion.parser import Page
    from app.ingestion.chunker import split_pages
    pages = [Page(None, 'atomic transaction')]
    chunks = split_pages(pages, 'doc')
    # zip(strict=True) fails inside the transaction after document/page insertion.
    with pytest.raises(ValueError):
        service.repository.insert('doc', 'x.txt', b'atomic transaction', pages, chunks, [])
    assert service.documents() == []


def test_cache_failure_keeps_committed_search_and_delete_correct(service, monkeypatch):
    import app.retrieval.vector_store as module
    monkeypatch.setattr(module.faiss, 'write_index', lambda *args: (_ for _ in ()).throw(OSError('disk full')))
    doc = service.ingest('x.txt', b'atomic transaction')
    assert not service.store.cache_persisted
    assert Retriever(service).search('atomic').results
    service.delete(doc['id'])
    assert not Retriever(service).search('atomic').results


def test_rebuild_failure_never_serves_deleted_vectors(service, monkeypatch):
    doc = service.ingest('x.txt', b'atomic transaction')
    original = service.repository.vectors_and_metadata
    monkeypatch.setattr(service.repository, 'vectors_and_metadata', lambda: (_ for _ in ()).throw(RuntimeError('failure')))
    with pytest.raises(RuntimeError):
        service.delete(doc['id'])
    assert service.store.index is None
    monkeypatch.setattr(service.repository, 'vectors_and_metadata', original)
    assert Retriever(service).search('atomic').results == []


def test_bad_embedding_rejected_before_commit(service, monkeypatch):
    monkeypatch.setattr(service.embeddings, 'encode', lambda texts: np.zeros((1, 4), dtype=np.float32))
    with pytest.raises(AppError, match='invalid'):
        service.ingest('x.txt', b'atomic transaction')
    assert not service.documents()


def test_duplicate_passages_suppressed(service):
    service.ingest('x.txt', b'atomic transaction')
    service.ingest('y.txt', b'atomic transaction ')
    assert len(Retriever(service).search('atomic').results) == 1
