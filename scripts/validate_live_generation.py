"""Three real Ollama RAG calls through /ask, recording actual HTTP traffic.

Requires the approved model to be installed and Ollama running. No mocks,
model downloads, or paid API endpoints are used by this script.
"""
from pathlib import Path
import sys
import argparse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.main import create_app
from app.embeddings.embedding_service import EmbeddingService
from app.generation.llm_client import LLMClient
from fastapi.testclient import TestClient
import httpx
import json
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evaluation/results/live-generation'
QUERIES = [
    ('straightforward', 'When should a consumer acknowledge a message?'),
    ('paraphrased', 'Two workers both see no record for the same event and then apply its update. Why is that unsafe, and what should enforce the decision?'),
    ('absent_specific', 'How many failed delivery attempts must occur before a message is moved to the dead-letter queue?'),
]


class RecordingHTTPTransport(httpx.BaseTransport):
    """Delegate to real network transport; only add request/response recording."""
    def __init__(self, exchanges):
        self.exchanges = exchanges

    def handle_request(self, request):
        assert request.url.host == '127.0.0.1' and request.url.port == 11434
        with httpx.HTTPTransport() as transport:
            response = transport.handle_request(request)
            response.read()
            self.exchanges.append({'url':str(request.url), 'request':json.loads(request.content),
                                   'http_status':response.status_code, 'response':response.json()})
            return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUTPUT)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    base = Settings(data_dir=ROOT/'data')
    with httpx.Client(base_url='http://127.0.0.1:11434', timeout=10) as ollama:
        version = ollama.get('/api/version').json()
        models = ollama.get('/api/tags').json()['models']
        model = next(m for m in models if m['name'] == 'qwen2.5:3b')
        details_response = ollama.post('/api/show',json={'model':'qwen2.5:3b'})
        details_response.raise_for_status()
        model_details = details_response.json()
    report = {'timestamp_utc':datetime.now(timezone.utc).isoformat(), 'provider':'ollama',
              'ollama_version':version, 'model':model, 'model_details':model_details,
              'execution':'Actual FastAPI /ask handlers via TestClient, real MiniLM and real Ollama HTTP inference. SQLite backup of running library. No mocked responses.',
              'top_k':base.top_k, 'similarity_threshold':base.similarity_threshold, 'queries':[]}
    with tempfile.TemporaryDirectory(dir=ROOT/'data') as temporary:
        directory = Path(temporary)
        with sqlite3.connect(f'file:{ROOT / "data/metadata.sqlite3"}?mode=ro',uri=True) as source:
            with sqlite3.connect(directory/'metadata.sqlite3') as target:
                source.backup(target)
        settings = base.model_copy(update={'data_dir':directory, 'llm_provider':'ollama',
                                          'llm_model':'qwen2.5:3b', 'llm_base_url':'http://127.0.0.1:11434'})
        exchanges = []
        llm = LLMClient(settings, RecordingHTTPTransport(exchanges))
        encoder = EmbeddingService(base)
        with TestClient(create_app(settings, encoder, llm)) as client:
            report['health'] = client.get('/health').json()
            for category, question in QUERIES:
                retrieval = client.post('/search',json={'query':question})
                retrieval.raise_for_status()
                before = len(exchanges)
                started = perf_counter()
                response = client.post('/ask',json={'query':question})
                elapsed = (perf_counter()-started)*1000
                response.raise_for_status()
                body = response.json()
                assert len(exchanges) == before + 1, 'A real LLM request was not recorded'
                exchange = exchanges[-1]
                assert exchange['http_status'] == 200
                assert exchange['response'].get('done') is True
                raw = exchange['response']['message']['content']
                assert raw.strip()
                evidence = json.loads(exchange['request']['messages'][1]['content'])['evidence']
                returned_sources = body['sources']
                assert len(evidence) == len(returned_sources)
                with sqlite3.connect(directory/'metadata.sqlite3') as db:
                    for sent, returned in zip(evidence,returned_sources,strict=True):
                        assert sent == {'source_id':returned['source_id'], 'document':returned['document_name'],
                                        'page':returned['page'], 'passage':returned['text']}
                        row = db.execute('SELECT text FROM pages WHERE document_id=? AND page IS ?',
                                         (returned['document_id'],returned['page'])).fetchone()
                        assert row[0][returned['start']:returned['end']] == returned['text']
                cited = list(dict.fromkeys(re.findall(r'\[(S\d+)\]',raw)))
                allowed = {s['source_id'] for s in returned_sources}
                try:
                    structured = json.loads(raw)
                    structured_citations = structured.get('citations', []) if isinstance(structured, dict) else []
                except ValueError:
                    structured_citations = []
                record = {'category':category, 'question':question, 'elapsed_ms':elapsed,
                          'retrieval':retrieval.json(), 'provider_exchange':exchange,
                          'api_response':body, 'raw_cited_ids':cited, 'structured_citations':structured_citations,
                          'structured_citations_exist':all(isinstance(s, str) and s in allowed for s in structured_citations),
                          'all_standalone_citations_exist':set(cited)<=allowed,
                          'has_standalone_citations':bool(cited), 'context_source_identity_verified':True}
                report['queries'].append(record)
                (output/'actual-results.json').write_text(json.dumps(report,indent=2)+'\n')
                print(json.dumps({'category':category,'status':body['status'],'elapsed_ms':round(elapsed,1),
                                  'raw_answer':raw,'citations':cited}),flush=True)
    print('Saved actual provider requests, responses, and source checks.',flush=True)


if __name__=='__main__':
    main()
