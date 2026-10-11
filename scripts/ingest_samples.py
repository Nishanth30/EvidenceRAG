from pathlib import Path
import argparse
import httpx

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    for path in sorted((Path(__file__).resolve().parents[1] / 'sample_documents').glob('*.md')):
        response = httpx.post(args.url.rstrip('/') + '/documents',
                              files={'file': (path.name, path.read_bytes(), 'text/markdown')}, timeout=300)
        if response.status_code == 409:
            print(f'{path.name}: already indexed')
        else:
            response.raise_for_status()
            print(f"{path.name}: {response.json()['chunk_count']} chunks")
