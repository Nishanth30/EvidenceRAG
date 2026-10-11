from dataclasses import dataclass
from pathlib import Path
import pymupdf
from app.errors import AppError


@dataclass(frozen=True)
class Page:
    number: int | None
    text: str


MIME_TYPES = {
    '.pdf': {'application/pdf', 'application/octet-stream'},
    '.txt': {'text/plain', 'application/octet-stream'},
    '.md': {'text/markdown', 'text/x-markdown', 'text/plain', 'application/octet-stream'},
}


def parse_document(filename: str, content: bytes, content_type: str | None,
                   max_bytes: int, max_chars: int = 2_000_000) -> list[Page]:
    extension = Path(filename).suffix.lower()
    if extension not in MIME_TYPES:
        raise AppError('Supported file types: PDF, TXT, Markdown', 415)
    if content_type and content_type.split(';')[0].lower() not in MIME_TYPES[extension]:
        raise AppError('Content type does not match the file extension', 415)
    if len(content) > max_bytes:
        raise AppError('File exceeds the upload size limit', 413)
    if not content:
        raise AppError('The uploaded file is empty')
    if extension == '.pdf':
        try:
            with pymupdf.open(stream=content, filetype='pdf') as doc:
                if doc.needs_pass:
                    raise AppError('Password-protected PDFs are not supported')
                pages = []
                total = 0
                for i, page in enumerate(doc):
                    text = page.get_text(sort=True).replace('\x00', '')
                    total += len(text)
                    if total > max_chars:
                        raise AppError('Extracted text exceeds the processing limit', 413)
                    pages.append(Page(i + 1, text))
        except AppError:
            raise
        except Exception as exc:
            raise AppError('The PDF is corrupt or unreadable') from exc
    else:
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise AppError('Text documents must use UTF-8 encoding') from exc
        if '\x00' in text:
            raise AppError('Binary content is not a supported text document')
        pages = [Page(None, text)]
    if sum(len(p.text) for p in pages) > max_chars:
        raise AppError('Extracted text exceeds the processing limit', 413)
    if not any(p.text.strip() for p in pages):
        raise AppError('No readable text found. Scanned PDFs require OCR, which is not supported.')
    return pages
