import pymupdf
import pytest
from app.errors import AppError
from app.ingestion.parser import parse_document, Page
from app.ingestion.chunker import split_pages


def test_text_markdown_duplicate_and_metadata(service):
    doc = service.ingest('../queue.md', b'# Queue\nUse idempotency keys to prevent duplicate processing.', 'text/markdown')
    assert doc['filename'] == 'queue.md'
    assert doc['chunk_count'] == 1 and doc['page_count'] == 1
    with pytest.raises(AppError, match='already indexed'):
        service.ingest('renamed.txt', b'# Queue\nUse idempotency keys to prevent duplicate processing.', 'text/plain')
    assert len(service.documents()) == 1


def test_pdf_pages_and_offsets(service):
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 50), 'A queue retries deliveries after consumer failure.')
        pdf.new_page().insert_text((50, 50), 'A database transaction commits atomically.')
        content = pdf.tobytes()
    result = service.ingest('guide.pdf', content, 'application/pdf')
    assert result['page_count'] == 2
    _, metadata = service.repository.vectors_and_metadata()
    assert {m['page'] for m in metadata} == {1, 2}
    assert all(m['end'] - m['start'] == len(m['text']) for m in metadata)


@pytest.mark.parametrize('filename,content,mime,message', [
    ('x.exe', b'abc', None, 'Supported'), ('x.txt', b'', None, 'empty'),
    ('x.md', b' \n ', None, 'No readable'), ('x.pdf', b'broken', None, 'corrupt'),
    ('x.txt', b'\xff\xff', None, 'UTF-8'), ('x.txt', b'a\x00b', None, 'Binary'),
    ('x.pdf', b'abc', 'text/plain', 'Content type'),
])
def test_invalid_documents(filename, content, mime, message):
    with pytest.raises(AppError, match=message):
        parse_document(filename, content, mime, 10000)


def test_limits_and_scanned_pdf():
    with pytest.raises(AppError, match='size limit'):
        parse_document('x.txt', b'large', None, 2)
    with pytest.raises(AppError, match='processing limit'):
        parse_document('x.txt', b'large', None, 100, 2)
    with pymupdf.open() as pdf:
        pdf.new_page()
        content = pdf.tobytes()
    with pytest.raises(AppError, match='OCR'):
        parse_document('blank.pdf', content, None, 100000)


@pytest.mark.parametrize('strategy', ['fixed', 'recursive'])
def test_chunks_cover_text_stable_overlap_and_pages(strategy):
    text = ('First sentence. Second sentence.\n\nAnother paragraph contains evidence. ' * 20)
    pages = [Page(1, text), Page(2, 'Other page')]
    chunks = split_pages(pages, 'doc', 100, 20, strategy)
    assert chunks == split_pages(pages, 'doc', 100, 20, strategy)
    first = [c for c in chunks if c.page == 1]
    assert first[0].start == 0 and first[-1].end == len(text)
    assert all(len(c.text) <= 100 and text[c.start:c.end] == c.text for c in first)
    assert all(a.end - b.start == 20 for a, b in zip(first, first[1:]))
    assert chunks[-1].page == 2 and chunks[-1].text == 'Other page'
    assert not split_pages([Page(None, '')], 'doc')
    assert chunks[0].id != split_pages(pages, 'doc', 100, 10, strategy)[0].id


def test_recursive_prefers_paragraph():
    text = 'a' * 60 + '\n\n' + 'b' * 70
    chunks = split_pages([Page(None, text)], 'doc', 100, 10, 'recursive')
    assert chunks[0].end == 62


def test_encrypted_pdf_rejected():
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((40, 40), 'Secret test fixture')
        content = pdf.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,
                              owner_pw='fixture-owner', user_pw='fixture-reader')
    with pytest.raises(AppError, match='Password-protected'):
        parse_document('locked.pdf', content, 'application/pdf', 100000)
