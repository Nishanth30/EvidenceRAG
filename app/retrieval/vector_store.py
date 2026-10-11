import hashlib
import logging
import os
import faiss
import numpy as np

logger = logging.getLogger(__name__)


class VectorStore:
    """FAISS is a replaceable cache. Rebuild from committed SQLite vectors on startup."""
    def __init__(self, repository, directory):
        self.repository = repository
        self.path = directory / 'index.faiss'
        self.index = None
        self.metadata = []
        self.cache_persisted = False
        self.rebuild()

    def rebuild(self):
        # Invalidate first: a failed rebuild must never serve stale/deleted data.
        self.index = None
        vectors, metadata = self.repository.vectors_and_metadata()
        index = faiss.IndexIDMap2(faiss.IndexFlatIP(self.repository.dimension))
        if len(vectors):
            index.add_with_ids(vectors, np.array([m['vector_id'] for m in metadata], dtype=np.int64))
        self.metadata = {m['vector_id']: m for m in metadata}
        self.index = index
        self.cache_persisted = False
        temporary = self.path.with_suffix('.tmp')
        try:
            faiss.write_index(index, str(temporary))
            os.replace(temporary, self.path)
            self.cache_persisted = True
        except Exception:
            logger.exception('FAISS cache write failed; committed SQLite vectors remain recoverable')
            temporary.unlink(missing_ok=True)

    def search(self, vector, top_k: int):
        if self.index is None:
            self.rebuild()
        if not self.index.ntotal:
            return []
        # Overfetch for duplicate/near-identical overlapping passage suppression.
        count = min(self.index.ntotal, max(top_k * 8, 40))
        scores, ids = self.index.search(vector, count)
        results, hashes = [], set()
        for score, vector_id in zip(scores[0], ids[0], strict=True):
            if vector_id == -1:
                continue
            item = self.metadata[int(vector_id)]
            digest = hashlib.sha256(' '.join(item['text'].split()).encode()).hexdigest()
            if digest in hashes:
                continue
            overlapping = False
            for selected in results:
                if item['document_id'] == selected['document_id'] and item['page'] == selected['page']:
                    intersection = max(0, min(item['end'], selected['end']) - max(item['start'], selected['start']))
                    if intersection / min(item['end'] - item['start'], selected['end'] - selected['start']) > 0.8:
                        overlapping = True
            if overlapping:
                continue
            hashes.add(digest)
            results.append({k: v for k, v in item.items() if k != 'vector_id'} | {'score': float(score)})
            if len(results) == top_k:
                break
        return results
