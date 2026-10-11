from fastapi.testclient import TestClient
from app.main import create_app
from conftest import FakeEmbeddings


def test_api_lifecycle_and_validation(settings):
    with TestClient(create_app(settings, FakeEmbeddings())) as client:
        assert client.get('/health').json()['status'] == 'ok'
        assert client.post('/search', json={'query': 'anything'}).json()['results'] == []
        for body in ({'query': ' '}, {'query': 'x', 'top_k': 0}, {'query': 'x', 'top_k': 21}):
            assert client.post('/search', json=body).status_code == 422
        result = client.post('/documents', files={'file': ('queue.txt', b'message keys prevent duplicates', 'text/plain')})
        assert result.status_code == 201
        document_id = result.json()['id']
        assert len(client.get('/documents').json()) == 1
        assert client.post('/search', json={'query': 'message keys'}).json()['results'][0]['document_id'] == document_id
        assert client.post('/ask', json={'query': 'message keys'}).json()['status'] == 'error'
        assert client.post('/documents', files={'file': ('x.txt', b'message keys prevent duplicates')}).status_code == 409
        assert client.post('/documents', files={'file': ('x.exe', b'bad')}).status_code == 415
        assert client.delete('/documents/' + document_id).status_code == 204
        assert client.delete('/documents/' + document_id).status_code == 404
        assert not client.post('/search', json={'query': 'message'}).json()['results']
        assert client.get('/openapi.json').status_code == 200
