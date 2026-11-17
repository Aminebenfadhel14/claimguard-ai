"""Web API contract tests with a lightweight keyword engine (no model weights needed)."""
from pathlib import Path
from fastapi.testclient import TestClient
from claimguard.web import create_app
from claimguard.models import Hit
from claimguard.storage.catalog import Catalog
from claimguard.corpora import paths

HOME = Path(__file__).resolve().parents[1]


class KeywordEngine:
    def __init__(self, corpus, tmp):
        locations = paths(HOME, corpus)
        catalog = Catalog(tmp / corpus)
        for p in sorted(locations['policies'].glob('*')):
            if p.suffix in {'.md', '.txt', '.pdf'}:
                catalog.ingest(p)
        self.chunks = catalog.chunks()
        self.index = None

    def retrieve(self, req, access=('public', 'internal')):
        words = {w.lower() for w in req.query.split() if len(w) > 3}
        scored = sorted(((sum(w in c.text.lower() for w in words), c) for c in self.chunks),
                        key=lambda x: (-x[0], x[1].chunk_id))
        hits = [Hit(chunk=c, score=float(s), stage='sparse') for s, c in scored[:20]]
        final, seen = [], set()
        for h in hits:
            if h.chunk.reference() not in seen:
                seen.add(h.chunk.reference()); final.append(h)
            if len(final) == req.top_k:
                break
        return {'query': req.query, 'dense': [], 'sparse': hits, 'rrf': [], 'reranker': [], 'final': final,
                'diagnostics': {'profile': 'test', 'latency_ms': 1.0, 'ranking_unit': 'section'}}


def client(tmp_path, monkeypatch):
    monkeypatch.setattr('claimguard.web.readiness', lambda home, corpus, profile, verify=False: {
        'corpus': corpus, 'documents': 2, 'profile': profile['name'], 'fingerprint': profile['fingerprint'],
        'models': {'dense': True, 'sparse': True, 'reranker': True},
        'available_modes': ['dense', 'sparse', 'hybrid', 'rerank'], 'groq_configured': False,
        'engine_ready': False, 'note': ''})
    builder = lambda corpus, profile, mode: KeywordEngine(corpus, tmp_path)
    return TestClient(create_app(builder=builder, home=HOME, static_dir=tmp_path / 'none'))


def test_config_status_and_cases(tmp_path, monkeypatch):
    with client(tmp_path, monkeypatch) as c:
        cfg = c.get('/api/config').json()
        assert {x['id'] for x in cfg['corpora']} == {'drip_r', 'novaretail'}
        assert cfg['default_profile'] in {p['id'] for p in cfg['profiles']}
        st = c.get('/api/status', params={'corpus': 'drip_r'}).json()
        assert st['engine_ready'] is False and 'rerank' in st['available_modes']
        cases = c.get('/api/cases', params={'q': 'camera', 'limit': 5}).json()
        assert cases['total'] > 0 and len(cases['items']) <= 5
        assert c.get('/api/status', params={'profile': 'nope'}).status_code == 400
        assert c.get('/api/status', params={'corpus': 'nope'}).status_code == 400


def test_search_returns_trace(tmp_path, monkeypatch):
    with client(tmp_path, monkeypatch) as c:
        r = c.post('/api/search', json={'corpus': 'novaretail', 'query': 'defective phone exchange refused',
                                        'incident_date': '2026-11-02', 'mode': 'rerank', 'top_k': 3})
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body['stages']['final']) == 3
        hit = body['stages']['final'][0]
        assert hit['reference'].count('@') == 1 and hit['text']
        assert c.get('/api/status', params={'corpus': 'novaretail'}).json()['engine_ready'] is True
        r = c.post('/api/search', json={'corpus': 'drip_r', 'query': 'return camera', 'agent_brief': 'late cable',
                                        'use_llm': True})
        assert 'Agent brief: late cable' in r.json()['original_query']
        assert r.json()['warnings']
        assert c.post('/api/search', json={'query': 'x'}).status_code == 422


def test_documents_and_versions(tmp_path, monkeypatch):
    monkeypatch.setattr('claimguard.web.paths', lambda home, corpus: {
        **paths(home, corpus), 'var': tmp_path / ('var_' + corpus)})
    with client(tmp_path, monkeypatch) as c:
        docs = c.get('/api/documents', params={'corpus': 'novaretail'}).json()['items']
        assert any(d['name'] == 'RETURN-001_2.0.md' for d in docs)
        doc = c.get('/api/documents/RETURN-001_2.0.md', params={'corpus': 'novaretail'}).json()
        assert doc['text'] and doc['metadata']['policy_id'] == 'RETURN-001'
        assert c.get('/api/documents/..%2F.env', params={'corpus': 'novaretail'}).status_code == 404
        assert c.get('/api/documents/RETURN-001_2.0.md/download', params={'corpus': 'novaretail'}).status_code == 200
        v = c.get('/api/policies/RETURN-001/versions', params={'corpus': 'novaretail'}).json()
        assert [x['version'] for x in v['versions']] == ['1.0', '2.0']
        d = c.get('/api/policies/RETURN-001/compare', params={'corpus': 'novaretail', 'a': '1.0', 'b': '2.0'}).json()
        assert d['diff'].startswith('---')
        sec = c.get('/api/documents/DRIP-001.txt', params={'corpus': 'drip_r'}).json()
        assert sec['sections'][0]['section'] == '1.1'


def test_evaluation(tmp_path, monkeypatch):
    with client(tmp_path, monkeypatch) as c:
        ev = c.get('/api/evaluation', params={'corpus': 'drip_r'}).json()
        assert ev['available'] and ev['primary']['id'] == 'E4'
        q = c.get('/api/evaluation/questions', params={'corpus': 'drip_r', 'experiment': 'E4'}).json()
        assert q['items']
