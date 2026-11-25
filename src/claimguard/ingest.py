"""Ingestion (labs 04-rag 10, 10bis, 14, 15): eCFR XML -> Document -> RecursiveCharacterTextSplitter
-> dense + sparse embeddings -> QdrantVectorStore.

One LangChain ``Document`` per top-level paragraph of a regulation section ((a), (b), ...). Its
``page_content`` is the official text, line for line, as parsed from the eCFR XML; nothing is rewritten.
The eCFR has no pages: the location of a chunk is ``cfr_section`` + ``paragraph`` (+ ``start_index``).
"""
import hashlib
import uuid
from datetime import datetime, timezone

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient, models

from claimguard import cfpb
from claimguard.config import REPORTS, ROOT, cfpb_settings, collection_name, qdrant_url, settings, write_json

CHUNK_NAMESPACE = uuid.UUID('6f1c1d2e-3a4b-5c6d-8e9f-0a1b2c3d4e5f')
OPEN_END = 99991231  # valid_until of the version currently in force


def date_int(value):
    """'2019-04-01' -> 20190401 (numeric payload, filterable with Range as in lab 14bis)."""
    return int(value.replace('-', '')) if value else OPEN_END


def load_documents():
    """Every version of every regulation section in data/cfpb/raw, as paragraph-level Documents."""
    documents = []
    for version in cfpb.regulation_versions(ROOT, cfpb_settings()):
        lines = version['parsed']['lines']
        for paragraph in version['parsed']['sections']:
            text = '\n'.join(lines[paragraph['start_line'] - 1:paragraph['end_line']])
            documents.append(Document(page_content=text, metadata={
                'source': version['file'].rsplit('/', 1)[-1],
                'file_hash': version['sha256'],
                'policy_id': version['policy_id'],
                'cfr_section': version['cfr_section'],
                'paragraph': paragraph['section'],
                'paragraph_title': paragraph['title'],
                'reference': f"{version['policy_id']}@{version['version']}#{paragraph['section']}",
                'citation': f"12 CFR {version['cfr_section']}({paragraph['section']})",
                'section_title': version['parsed']['heading'],
                'regulation': version['regulation'],
                'category': version['category'],
                'version': version['version'],
                'version_date': version['date'],
                'valid_until': version['until'],
                'valid_from_int': date_int(version['date']),
                'valid_until_int': date_int(version['until']),
                'line_start': paragraph['start_line'],
                'line_end': paragraph['end_line'],
                'url': version['url'],
            }))
    return documents


def split_documents(documents, chunk_size, chunk_overlap):
    """Course splitter; add_start_index keeps the character offset of each chunk inside its paragraph."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                                              add_start_index=True)
    chunks = splitter.split_documents(documents)
    for chunk in chunks:
        chunk.metadata['chunk_size'] = chunk_size
        chunk.metadata['chunk_overlap'] = chunk_overlap
        chunk.id = chunk_id(chunk)
    return chunks


def chunk_id(chunk):
    """Stable Qdrant point id: same file, paragraph, offset and text -> same id (idempotent upserts)."""
    m = chunk.metadata
    text_hash = hashlib.sha256(chunk.page_content.encode('utf-8')).hexdigest()
    return str(uuid.uuid5(CHUNK_NAMESPACE, f"{m['file_hash']}|{m['paragraph']}|{m['start_index']}|{text_hash}"))


def check_schema(client, name, dense_size):
    """Return a list of incompatibilities between an existing collection and the expected schema."""
    cfg = settings()['qdrant']
    info = client.get_collection(name).config.params
    problems = []
    vectors = info.vectors if isinstance(info.vectors, dict) else {}
    dense = vectors.get(cfg['dense_vector_name'])
    if dense is None:
        problems.append(f"vecteur dense « {cfg['dense_vector_name']} » absent")
    elif dense.size != dense_size or dense.distance != models.Distance.COSINE:
        problems.append(f'vecteur dense incompatible (taille {dense.size}, distance {dense.distance})')
    sparse = (info.sparse_vectors or {}).get(cfg['sparse_vector_name'])
    if sparse is None:
        problems.append(f"vecteur sparse « {cfg['sparse_vector_name']} » absent")
    elif sparse.modifier != models.Modifier.IDF:
        problems.append('vecteur sparse sans modificateur IDF (requis par Qdrant/bm25)')
    return problems


def indexed_hashes(client, name):
    """file_hash values already present in the collection (lab 14: skip files already indexed)."""
    hashes, offset = set(), None
    while True:
        points, offset = client.scroll(name, limit=256, offset=offset, with_payload=['metadata.file_hash'])
        hashes |= {p.payload['metadata']['file_hash'] for p in points}
        if offset is None:
            return hashes


def ingest(models_, chunk_size=None, chunk_overlap=None, rebuild=False, log=print):
    """Create or update the collection for one chunking configuration. Returns the ingestion manifest."""
    reference = settings()['chunking']['reference']
    chunk_size = chunk_size or reference['chunk_size']
    chunk_overlap = reference['chunk_overlap'] if chunk_overlap is None else chunk_overlap
    name = collection_name(chunk_size, chunk_overlap)
    cfg = settings()['qdrant']
    client = QdrantClient(url=qdrant_url())
    dense_size = len(models_.dense.embed_query('dimension'))
    exists = client.collection_exists(name)
    if exists and not rebuild:
        problems = check_schema(client, name, dense_size)
        if problems:
            raise RuntimeError(f'Collection {name} incompatible : {"; ".join(problems)}. '
                               'Relancez avec --rebuild pour la reconstruire.')
    if exists and rebuild:
        client.delete_collection(name)
        exists = False
        log(f'Collection {name} supprimée (reconstruction demandée).')

    documents = load_documents()
    already = indexed_hashes(client, name) if exists else set()
    new_documents = [d for d in documents if d.metadata['file_hash'] not in already]
    skipped = sorted({d.metadata['source'] for d in documents if d.metadata['file_hash'] in already})
    for source in skipped:
        log(f'Déjà indexé, ignoré : {source}')
    chunks = split_documents(new_documents, chunk_size, chunk_overlap)
    log(f'{len(documents)} paragraphes chargés, {len(new_documents)} à indexer -> {len(chunks)} chunks')

    store_options = dict(url=qdrant_url(), collection_name=name, retrieval_mode=RetrievalMode.HYBRID,
                         vector_name=cfg['dense_vector_name'], sparse_vector_name=cfg['sparse_vector_name'])
    if chunks and not exists:
        QdrantVectorStore.from_documents(
            documents=chunks, ids=[c.id for c in chunks], embedding=models_.dense,
            sparse_embedding=models_.sparse, sparse_vector_params={'modifier': models.Modifier.IDF},
            **store_options)
    elif chunks:
        store = QdrantVectorStore.from_existing_collection(
            embedding=models_.dense, sparse_embedding=models_.sparse, **store_options)
        store.add_documents(chunks, ids=[c.id for c in chunks])

    total = client.count(name, exact=True).count
    client.close()
    manifest = {
        'created_at': datetime.now(timezone.utc).isoformat(), 'collection': name, 'qdrant_url': qdrant_url(),
        'chunk_size': chunk_size, 'chunk_overlap': chunk_overlap, 'points_in_collection': total,
        'new_chunks': len(chunks), 'skipped_sources': skipped,
        'models': {k: settings()['models'][k] for k in ('dense', 'dense_revision', 'sparse')},
        'vectors': {'dense': cfg['dense_vector_name'], 'sparse': cfg['sparse_vector_name'] + ' (IDF)'},
        'sources': sorted({(d.metadata['source'], d.metadata['file_hash'], d.metadata['version_date'],
                            d.metadata['valid_until'] or '') for d in documents}),
    }
    manifest['sources'] = [dict(zip(('source', 'sha256', 'version_date', 'valid_until'), s)) for s in manifest['sources']]
    write_json(REPORTS / 'ingestion' / f'{name}.json', manifest)
    log(f'Collection {name} : {total} points')
    return manifest
