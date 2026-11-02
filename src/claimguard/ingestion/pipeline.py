"""Page-preserving, section-aware parsing. No OCR or inferred business metadata."""
import hashlib
import json
import re
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from claimguard.models import Chunk, PolicyMetadata

HEADING = re.compile(r'^(?:#{1,6}\s+)?(\d+(?:\.\d+)+)\s+[—–-]?\s*(.*)$', re.M)

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def clean_text(text: str) -> str:
    # Preserve negations, punctuation, money, numbers and paragraph boundaries.
    return re.sub(r'[ \t]+', ' ', text.replace('\x00', '').replace('\r\n', '\n')).strip()

def load_pages(path: Path):
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        from langchain_community.document_loaders import PyPDFLoader
        pages = [(d.metadata['page'] + 1, d.page_content) for d in PyPDFLoader(str(path)).load()]
        if not any(t.strip() for _, t in pages):
            raise ValueError('No extractable PDF text; OCR and manual verification required')
        return pages
    if suffix in {'.md', '.txt'}:
        # A page is a form-feed-separated source page for text formats.
        return list(enumerate(path.read_text(encoding='utf-8').split('\f'), 1))
    raise ValueError('Supported formats: PDF, TXT, Markdown')

def extract_tables(path: Path) -> list[dict]:
    if path.suffix.lower() != '.pdf':
        return []
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return [{'page': i, 'rows': table} for i, p in enumerate(pdf.pages, 1)
                for table in p.extract_tables()]

def parse(path: Path, metadata: PolicyMetadata, chunk_size=1000, chunk_overlap=100) -> list[Chunk]:
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError('overlap must be between zero and chunk_size - 1')
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    digest, result, previous_section = sha256(path), [], 'preamble'
    for page, raw in load_pages(path):
        text = clean_text(raw)
        matches = list(HEADING.finditer(text))
        sections = []
        if matches and matches[0].start():
            sections.append((previous_section, text[:matches[0].start()]))
        for i, m in enumerate(matches):
            end = matches[i+1].start() if i+1 < len(matches) else len(text)
            sections.append((m.group(1), text[m.start():end]))
        if not matches:
            sections = [(previous_section, text)]
        for section, body in sections:
            previous_section = section
            for n, piece in enumerate(splitter.split_text(body)):
                identity = f'{digest}|{metadata.model_dump_json()}|{page}|{section}|{n}|{piece}'
                result.append(Chunk(chunk_id=hashlib.sha256(identity.encode()).hexdigest(), text=piece,
                    metadata=metadata, section=section, page=page, file_hash=digest, source_file=path.name))
    if not result:
        raise ValueError('Empty document')
    return result

def parse_with_sidecar(path: Path):
    metadata = PolicyMetadata.model_validate_json(path.with_suffix(path.suffix + '.json').read_text())
    return metadata, parse(path, metadata)
