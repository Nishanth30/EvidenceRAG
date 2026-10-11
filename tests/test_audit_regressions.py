import json
import pytest
from app.retrieval.retriever import Retriever
from app.generation.rag_pipeline import RAGPipeline


def test_search_recovers_first_ingestion_after_rebuild_failure(service, monkeypatch):
    original = service.repository.vectors_and_metadata
    monkeypatch.setattr(service.repository, 'vectors_and_metadata',
                        lambda: (_ for _ in ()).throw(RuntimeError('transient read error')))
    with pytest.raises(RuntimeError):
        service.ingest('committed.txt', b'durable message identifiers prevent duplicate processing')
    assert len(service.documents()) == 1  # The transaction already committed.
    monkeypatch.setattr(service.repository, 'vectors_and_metadata', original)
    assert Retriever(service).search('message identifiers').results


def test_malformed_unknown_citation_cannot_bypass_validation(service, settings):
    service.ingest('source.txt', b'durable message identifiers prevent duplicate processing')
    class LLM:
        configured = True
        def generate(self, messages):
            return json.dumps(dict(status='answered', answer='Use message identifiers [S1]. Extra claim [S99, S1].', citations=['S1']))
    result = RAGPipeline(Retriever(service), LLM(), settings).ask('message identifiers')
    assert result.status == 'error'
    assert result.error_code == 'invalid_citations'


def test_outgoing_context_exactly_matches_returned_sources(service, settings):
    service.ingest('source.txt', b'durable message identifiers prevent duplicate processing ' * 6)
    captured = []
    class LLM:
        configured = True
        def generate(self, messages):
            captured.extend(messages)
            return json.dumps(dict(status='answered', answer='Use message identifiers [S1].', citations=['S1']))
    config = settings.model_copy(update={'max_context_chars': 120})
    result = RAGPipeline(Retriever(service), LLM(), config).ask('message identifiers')
    evidence = json.loads(captured[1]['content'])['evidence']
    assert len(evidence) == len(result.sources)
    assert sum(len(s.text) for s in result.sources) <= 120
    _, metadata = service.repository.vectors_and_metadata()
    chunks = {r['chunk_id']: r for r in metadata}
    for item, source in zip(evidence, result.sources, strict=True):
        assert item == {'source_id': source.source_id, 'document': source.document_name,
                        'page': source.page, 'passage': source.text}
        original = chunks[source.chunk_id]
        assert original['text'].startswith(source.text)
        assert source.start == original['start']
        assert source.end == source.start + len(source.text)
    assert set(result.cited_source_ids) <= {s.source_id for s in result.sources}
