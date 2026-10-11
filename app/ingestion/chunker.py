from dataclasses import dataclass
from hashlib import sha256
import json
import re
from app.ingestion.parser import Page


@dataclass(frozen=True)
class Chunk:
    id: str
    page: int | None
    start: int
    end: int
    text: str


def split_pages(pages: list[Page], document_id: str, size: int = 800,
                overlap: int = 150, strategy: str = 'recursive') -> list[Chunk]:
    """Character offsets refer to extracted page text, including overlapping characters."""
    if size < 1 or not 0 <= overlap < size or strategy not in {'fixed', 'recursive'}:
        raise ValueError('Invalid chunking configuration')
    chunks = []
    for page_index, page in enumerate(pages):
        text, start = page.text, 0
        while start < len(text):
            end = min(start + size, len(text))
            if strategy == 'recursive' and end < len(text):
                # Recursively prefer paragraph, sentence, then word boundaries.
                # Minimum progress prevents overlap from trapping the loop.
                lower = start + max(size // 2, overlap + 1)
                for pattern in (r'\n\s*\n', r'(?<=[.!?])\s+', r'\s+'):
                    candidates = list(re.finditer(pattern, text[lower:end]))
                    if candidates:
                        end = lower + candidates[-1].end()
                        break
            passage = text[start:end]
            if passage.strip():
                identity = json.dumps([document_id, strategy, size, overlap, page_index,
                                       page.number, start, end], separators=(',', ':'))
                chunks.append(Chunk(sha256(identity.encode()).hexdigest(), page.number,
                                    start, end, passage))
            if end == len(text):
                break
            start = end - overlap
    return chunks
