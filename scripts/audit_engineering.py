"""Focused audit with real embeddings and process restart; never calls an LLM."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.embeddings.embedding_service import EmbeddingService
from app.main import create_app
from app.generation.prompt_builder import build_context
from app.schemas.responses import Passage
from fastapi.testclient import TestClient
import json
import sqlite3
import subprocess
import tempfile
import pymupdf

ROOT = Path(__file__).resolve().parents[1]


def phase(directory, stage):
    settings = Settings(_env_file=None, data_dir=directory, llm_provider='none', llm_model='')
    encoder = EmbeddingService(Settings(_env_file=None, data_dir=ROOT/'data'))
    with TestClient(create_app(settings, encoder)) as client:
        if stage == 'create':
            doc = ROOT/'sample_documents/message_delivery.md'
            result = client.post('/documents', files={'file':(doc.name,doc.read_bytes(),'text/markdown')})
            assert result.status_code == 201
            saved = result.json()
            baseline = client.get('/health').json()
            statuses = []
            for i in range(3):
                duplicate = client.post('/documents',files={'file':(f'renamed-{i}.md',doc.read_bytes(),'text/markdown')})
                statuses.append(duplicate.status_code)
                assert duplicate.status_code == 409
                health = client.get('/health').json()
                assert (health['documents'],health['chunks']) == (baseline['documents'],baseline['chunks'])
            with sqlite3.connect(directory/'metadata.sqlite3') as db:
                assert db.execute('SELECT count(*) FROM chunks').fetchone()[0] == saved['chunk_count']
                assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            with pymupdf.open() as pdf:
                pdf.new_page().insert_text((40,50),'The violet beacon calibrates the Neptune telescope.')
                pdf.new_page().insert_text((40,50),'The calibration report is stored in the observatory.')
                raw = pdf.tobytes()
            pdf_result = client.post('/documents',files={'file':('calibration.pdf',raw,'application/pdf')})
            assert pdf_result.status_code == 201 and pdf_result.json()['page_count'] == 2
            search = client.post('/search',json={'query':'Which beacon calibrates the Neptune telescope?'}).json()
            assert search['results'][0]['document_id'] == pdf_result.json()['id']
            assert search['results'][0]['page'] == 1
            assert client.delete('/documents/'+pdf_result.json()['id']).status_code == 204
            txt = client.post('/documents',files={'file':('test.txt',b'A telescope observes distant planets.','text/plain')})
            assert txt.status_code == 201
            assert client.delete('/documents/'+txt.json()['id']).status_code == 204
            invalid = {
                'blank_query':client.post('/search',json={'query':' '}).status_code,
                'invalid_k':client.post('/search',json={'query':'test','top_k':0}).status_code,
                'corrupt_pdf':client.post('/documents',files={'file':('bad.pdf',b'not pdf','application/pdf')}).status_code,
                'empty_file':client.post('/documents',files={'file':('empty.txt',b'','text/plain')}).status_code,
                'unsupported':client.post('/documents',files={'file':('bad.exe',b'abc','application/octet-stream')}).status_code,
                'oversized':client.post('/documents',files={'file':('large.txt',b'x'*(10*1024*1024+1),'text/plain')}).status_code,
                'missing_delete':client.delete('/documents/no-such-id').status_code}
            assert invalid == {'blank_query':422,'invalid_k':422,'corrupt_pdf':400,'empty_file':400,'unsupported':415,'oversized':413,'missing_delete':404}
            query = 'How do message identifiers prevent duplicate processing?'
            results = client.post('/search',json={'query':query}).json()['results']
            passages = [Passage(**r) for r in results if r['score'] >= settings.similarity_threshold]
            messages, sources = build_context(query, passages, 220)
            evidence = json.loads(messages[1]['content'])['evidence']
            with sqlite3.connect(directory/'metadata.sqlite3') as db:
                for item, source in zip(evidence,sources,strict=True):
                    row = db.execute('SELECT p.text FROM pages p WHERE p.document_id=? AND p.page IS ?',
                                     (source.document_id,source.page)).fetchone()
                    assert row[0][source.start:source.end] == source.text == item['passage']
                    assert item['source_id'] == source.source_id
                    assert item['document'] == source.document_name and item['page'] == source.page
            answer = client.post('/ask',json={'query':query}).json()
            assert answer['status']=='error' and answer['sources']
            result = {'document_id':saved['id'],'chunks':saved['chunk_count'],'duplicate_statuses':statuses,
                      'errors':invalid,'retrieved_chunk_ids':[r['chunk_id'] for r in results],
                      'source_context_identity':'passed against SQLite page substrings, with truncation',
                      'live_llm':'not configured; no generation performed'}
            (directory/'state.json').write_text(json.dumps(result))
            # Force next process to recover from a corrupt persisted cache.
            (directory/'index.faiss').write_bytes(b'audit: deliberately corrupted derived cache')
            return result
        state=json.loads((directory/'state.json').read_text())
        if stage == 'recover_delete':
            assert client.get('/health').json()['chunks']==state['chunks']
            results=client.post('/search',json={'query':'How do message identifiers prevent duplicate processing?'}).json()['results']
            assert [r['chunk_id'] for r in results] == state['retrieved_chunk_ids']
            assert client.delete('/documents/'+state['document_id']).status_code==204
            assert client.post('/search',json={'query':'message identifiers'}).json()['results']==[]
            with sqlite3.connect(directory/'metadata.sqlite3') as db:
                for table in ['documents','pages','chunks']:
                    assert db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]==0
            return {'fresh_process_recovery':'passed; identical ranking after corrupt cache', 'deletion':'passed; all dependent rows removed'}
        assert client.get('/documents').json()==[]
        assert client.get('/health').json()['chunks']==0
        assert client.post('/search',json={'query':'message identifiers'}).json()['results']==[]
        return {'deletion_survives_second_restart':'passed'}


if __name__=='__main__':
    if len(sys.argv)>1:
        directory,stage=Path(sys.argv[1]),sys.argv[2]
        result=phase(directory,stage)
        (directory/f'{stage}.json').write_text(json.dumps(result,indent=2))
    else:
        (ROOT/'data/audit').mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'data/audit') as tmp:
            directory=Path(tmp)
            report={}
            for stage in ['create','recover_delete','verify_deleted']:
                subprocess.run([sys.executable,__file__,str(directory),stage],check=True,cwd=ROOT)
                report[stage]=json.loads((directory/f'{stage}.json').read_text())
            path=ROOT/'evaluation/results/audit/engineering.json'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))
