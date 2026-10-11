import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
import numpy as np
from app.errors import AppError


class Repository:
    """SQLite owns original files, extracted pages, chunks, vectors and their mapping."""
    def __init__(self, path, config: dict, dimension: int):
        self.path = path
        self.dimension = dimension
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT);
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL, content_hash TEXT UNIQUE NOT NULL,
                    page_count INTEGER NOT NULL, chunk_count INTEGER NOT NULL, created_at TEXT NOT NULL,
                    original BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS pages (
                    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
                    ordinal INTEGER, page INTEGER, text TEXT NOT NULL,
                    PRIMARY KEY(document_id, ordinal));
                CREATE TABLE IF NOT EXISTS chunks (
                    vector_id INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
                    page INTEGER, start INTEGER, end INTEGER, text TEXT NOT NULL, embedding BLOB NOT NULL);
            ''')
            config = {**config, 'dimension': dimension}
            expected = json.dumps(config, sort_keys=True)
            row = db.execute('SELECT value FROM config WHERE id=1').fetchone()
            if row and row['value'] != expected:
                raise AppError('Index configuration changed. Use a new DATA_DIR or restore the original settings.', 409)
            db.execute('INSERT OR IGNORE INTO config VALUES (1, ?)', (expected,))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def documents(self) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT id,filename,content_hash,page_count,chunk_count,created_at FROM documents ORDER BY created_at')]

    def contains(self, document_id: str) -> bool:
        with self.connect() as db:
            return db.execute('SELECT 1 FROM documents WHERE id=?', (document_id,)).fetchone() is not None

    def insert(self, document_id, filename, original, pages, chunks, vectors):
        created = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?)',
                       (document_id, filename, document_id, len(pages), len(chunks), created, original))
            db.executemany('INSERT INTO pages VALUES (?,?,?,?)',
                           [(document_id, i, p.number, p.text) for i, p in enumerate(pages)])
            db.executemany('INSERT INTO chunks (id,document_id,page,start,end,text,embedding) VALUES (?,?,?,?,?,?,?)',
                           [(c.id, document_id, c.page, c.start, c.end, c.text, v.astype('<f4').tobytes())
                            for c, v in zip(chunks, vectors, strict=True)])
        return dict(id=document_id, filename=filename, content_hash=document_id,
                    page_count=len(pages), chunk_count=len(chunks), created_at=created)

    def delete(self, document_id: str) -> bool:
        with self.connect() as db:
            return db.execute('DELETE FROM documents WHERE id=?', (document_id,)).rowcount > 0

    def vectors_and_metadata(self):
        with self.connect() as db:
            rows = db.execute('''SELECT c.*,d.filename FROM chunks c JOIN documents d
                                 ON c.document_id=d.id ORDER BY c.vector_id''').fetchall()
        vectors = np.empty((len(rows), self.dimension), dtype=np.float32)
        metadata = []
        for i, row in enumerate(rows):
            vector = np.frombuffer(row['embedding'], dtype='<f4')
            if vector.shape != (self.dimension,) or not np.isfinite(vector).all():
                raise RuntimeError('Stored vector is corrupt; restore the database from a backup')
            if not np.isclose(np.linalg.norm(vector), 1, atol=1e-4):
                raise RuntimeError('Stored vector is not normalized')
            vectors[i] = vector
            metadata.append(dict(chunk_id=row['id'], document_id=row['document_id'],
                                 document_name=row['filename'], page=row['page'], start=row['start'],
                                 end=row['end'], text=row['text'], vector_id=row['vector_id']))
        return vectors, metadata
