"""Checks against the real Qdrant index and real models (pytest -m real). Skipped when Qdrant is down."""
import json

import pytest

from claimguard.config import BENCHMARK, app_collection, qdrant_url
from claimguard.ingest import load_documents, split_documents

pytestmark = pytest.mark.real


@pytest.fixture(scope='module')
def client():
    from qdrant_client import QdrantClient
    c = QdrantClient(url=qdrant_url(), timeout=3)
    try:
        if not c.collection_exists(app_collection()):
            pytest.skip('collection absente : python -m claimguard ingest')
    except Exception:
        pytest.skip('Qdrant indisponible : docker compose up -d')
    yield c
    c.close()


@pytest.fixture(scope='module')
def rag(client):
    from claimguard.rag import RAG
    return RAG(app_collection())


def test_collection_ids_match_ingestion_ids(client):
    size, overlap = (int(x[1:]) for x in app_collection().rsplit('_', 2)[1:])
    expected = {c.id for c in split_documents(load_documents(), size, overlap)}
    points, offset, ids = None, None, set()
    while True:
        points, offset = client.scroll(app_collection(), limit=256, offset=offset)
        ids |= {str(p.id) for p in points}
        if offset is None:
            break
    assert ids == expected


def test_qrels_ids_exist_in_collection(client):
    path = BENCHMARK / f'qrels_{app_collection()}.json'
    if not path.exists():
        pytest.skip('qrels absents')
    qrels = json.loads(path.read_text(encoding='utf-8'))
    ids = {i for v in qrels.values() for i in v}
    found = {str(p.id) for p in client.retrieve(app_collection(), list(ids))}
    assert found == ids


def test_six_strategies_return_ids_from_vectorstore(rag, client):
    for mode in ('dense', 'sparse', 'hybrid'):
        for rerank in (False, True):
            documents = rag.retrieve('billing error notice 60 days', mode=mode, rerank=rerank, k=5,
                                     n_candidates=20, as_of='2025-01-15')
            assert len(documents) == 5
            ids = [str(d.metadata['_id']) for d in documents]
            assert len(set(ids)) == 5
            assert all(d.metadata['valid_from_int'] <= 20250115 < d.metadata['valid_until_int'] for d in documents)
            assert len(client.retrieve(app_collection(), ids)) == 5


def test_version_filter_selects_older_version(rag):
    documents = rag.retrieve('billing error notice', mode='hybrid', k=5, as_of='2018-06-01')
    assert {d.metadata['version'] for d in documents if d.metadata['policy_id'] == 'REGZ-013'} <= {'1.0'}
