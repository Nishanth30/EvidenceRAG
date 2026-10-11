"""Exercise a running API with the real configured encoder and disposable PDF data."""
import argparse
import json
from pathlib import Path
import uuid
import httpx
import pymupdf


def run(base):
    checks = []
    with httpx.Client(base_url=base, timeout=120) as client:
        health = client.get('/health')
        health.raise_for_status()
        assert health.json()['status'] == 'ok'
        before = client.get('/documents').json()
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((40, 50), 'Neptune telescope calibration uses the violet reference beacon.')
            pdf.new_page().insert_text((40, 50), 'The calibration record identifier is ' + uuid.uuid4().hex)
            data = pdf.tobytes()
        result = client.post('/documents', files={'file': ('smoke-calibration.pdf', data, 'application/pdf')})
        assert result.status_code == 201, result.text
        document = result.json()
        try:
            assert document['page_count'] == 2 and document['chunk_count'] == 2
            checks.append('real PDF upload and embedding with page metadata')
            query = {'query': 'What reference beacon does Neptune telescope calibration use?', 'top_k': 5}
            search = client.post('/search', json=query)
            search.raise_for_status()
            assert search.json()['results'][0]['document_id'] == document['id']
            assert search.json()['results'][0]['page'] == 1
            checks.append('real query embedding and FAISS top result')
            duplicate = client.post('/documents', files={'file': ('renamed.pdf', data, 'application/pdf')})
            assert duplicate.status_code == 409
            checks.append('duplicate rejection over HTTP')
            answer = client.post('/ask', json=query)
            answer.raise_for_status()
            if not health.json()['llm_configured']:
                assert answer.json()['status'] == 'error'
                assert answer.json()['sources']
                checks.append('missing LLM with supporting passages, no simulated answer')
            assert client.post('/search', json={'query': '  '}).status_code == 422
            checks.append('invalid query validation')
        finally:
            deletion = client.delete('/documents/' + document['id'])
            assert deletion.status_code == 204
        remaining = client.post('/search', json=query).json()['results']
        assert all(r['document_id'] != document['id'] for r in remaining)
        assert client.get('/documents').json() == before
        checks.append('deletion removes real vectors and preserves existing library')
    return {'status': 'passed', 'checks': checks, 'library_documents': len(before)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    report = run(args.url)
    print(json.dumps(report, indent=2))
    output = Path(__file__).resolve().parents[1] / 'evaluation/results/api-smoke.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
