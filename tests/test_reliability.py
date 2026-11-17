"""Regression coverage for readiness, real offline search and presentation failures."""
import json
import shutil
import socket
from pathlib import Path
import pytest
from claimguard.settings import ROOT, artifact_dir, load_profile
from claimguard.diagnostics import readiness, check_artifact, record_error
from claimguard.models import Hit, SearchRequest
from claimguard.retrieval.engine import RetrievalEngine
from claimguard.runtime import build


def test_deduplicate_before_top_k(tmp_path):
    from claimguard.models import PolicyMetadata
    metadata=PolicyMetadata(document_id='TEST-V1',policy_id='TEST-001',title='Test',category='returns',department='Support',version='1.0',effective_date='2025-01-01')
    source=tmp_path/'policy.md'
    source.write_text('## 1.1 Return\nReturn with proof.\n## 1.2 Exceptions\nDamage is excluded.')
    from claimguard.ingestion.pipeline import parse
    a,b = parse(source, metadata)
    duplicate = a.model_copy(update={'chunk_id':'d'*64})
    ranking = [Hit(chunk=c,score=3-i,stage='dense') for i,c in enumerate((a,duplicate,b))]
    class Index:
        def search(self, **kwargs): return ranking
    trace = RetrievalEngine(Index()).retrieve(SearchRequest(query='refund policy',incident_date='2026-11-02',mode='dense',top_k=2))
    assert [h.chunk.section for h in trace['final']]==[a.section,b.section]
    assert trace['final'][0].chunk.chunk_id==a.chunk_id
    assert len(trace['dense'])==3


def test_artifact_integrity_and_modes(tmp_path):
    (tmp_path/'configs').mkdir()
    shutil.copyfile(ROOT/'configs/retrieval.json',tmp_path/'configs/retrieval.json')
    profile=load_profile(tmp_path,'course')
    directory=artifact_dir(tmp_path,profile['dense'])
    directory.mkdir(parents=True)
    data=directory/'weights'
    data.write_bytes(b'abcd')
    from claimguard.settings import file_hash
    manifest=profile['dense']|{'files':[{'path':'weights','size':4,'sha256':file_hash(data)}]}
    (directory/'manifest.json').write_text(json.dumps(manifest))
    assert check_artifact(tmp_path,profile['dense'],verify=True)
    data.write_bytes(b'efgh')
    assert not check_artifact(tmp_path,profile['dense'],verify=True)
    data.unlink()
    assert not check_artifact(tmp_path,profile['dense'])
    assert readiness(tmp_path,'drip_r','course')['available_modes']==[]


def test_reranking_budget_covers_distinct_sections(tmp_path):
    from claimguard.models import PolicyMetadata
    from claimguard.ingestion.pipeline import parse
    metadata=PolicyMetadata(document_id='TEST-V1',policy_id='TEST-001',title='Test',category='returns',department='Support',version='1.0',effective_date='2025-01-01')
    source=tmp_path/'policy.md'
    source.write_text('## 1.1 General\nGeneral return.\n## 1.2 Specific\nSpecific exception.')
    a,b=parse(source,metadata)
    ranking=[Hit(chunk=a.model_copy(update={'chunk_id':str(i).zfill(64)}),score=100-i,stage='dense') for i in range(8)]
    ranking.append(Hit(chunk=b,score=.1,stage='dense'))
    class Index:
        def search(self,**kwargs): return ranking
    class Reranker:
        def predict(self,pairs,**kwargs):
            assert len(pairs)==2
            return [1 if 'Specific exception' in text else 0 for _,text in pairs]
    trace=RetrievalEngine(Index(),Reranker(),profile={'rerank_k':2}).retrieve(SearchRequest(query='specific exception',incident_date='2026-11-02',mode='rerank',top_k=2))
    assert trace['final'][0].chunk.section=='1.2'


def test_log_redacts_credentials(tmp_path,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','private-test-key')
    try: raise RuntimeError('Provider private-test-key Authorization: Bearer secret-token')
    except RuntimeError: error_id=record_error(tmp_path,'test')
    log=(tmp_path/'var/logs/errors.log').read_text(encoding='utf-8')
    assert error_id in log and 'RuntimeError' in log
    assert 'private-test-key' not in log and 'secret-token' not in log


@pytest.fixture(scope='module')
def offline_drip():
    _,engine=build(ROOT,corpus='drip_r',profile='course',mode='rerank')
    yield engine
    engine.index.close()


def test_real_offline_four_modes_and_screenshot(offline_drip,monkeypatch):
    def deny(*args,**kwargs): raise AssertionError('Unexpected network access')
    monkeypatch.setattr(socket.socket,'connect',deny)
    query='Hello, this is Alastair MacGregor. I need to return a couple of items from my recent order. I opened one camera from the "OmniPro Wireless Security Camera System", but it doesn’t work with my Wi-Fi, and the other camera plus the extension cable are still sealed. I’m a bit confused about the return window for the extension cable since it arrived late. Can you help?'
    for mode in ('dense','sparse','hybrid','rerank'):
        trace=offline_drip.retrieve(SearchRequest(query=query,incident_date='2026-11-02',mode=mode))
        refs=[h.chunk.reference() for h in trace['final']]
        assert len(refs)==5 and len(set(refs))==5
        assert all(h.chunk.metadata.policy_id.startswith('DRIP-') for h in trace['final'])
    for query in ('Comment renvoyer un cadeau sans numéro de commande ?', 'How do I return a gift without the order number?'):
        trace=offline_drip.retrieve(SearchRequest(query=query,incident_date='2026-11-02',mode='rerank'))
        assert 'DRIP-001@1.0#1.15' in [h.chunk.reference() for h in trace['final']]


def test_sparse_only_loads_no_transformer_weights(tmp_path,monkeypatch):
    import sentence_transformers
    def deny(*args,**kwargs): raise AssertionError('Unneeded transformer weights loaded')
    monkeypatch.setattr(sentence_transformers,'SentenceTransformer',deny)
    monkeypatch.setattr(sentence_transformers,'CrossEncoder',deny)
    (tmp_path/'configs').mkdir()
    shutil.copyfile(ROOT/'configs/retrieval.json',tmp_path/'configs/retrieval.json')
    profile=load_profile(tmp_path,'course')
    shutil.copytree(artifact_dir(ROOT,profile['sparse']),artifact_dir(tmp_path,profile['sparse']))
    shutil.copytree(ROOT/'data/drip_r/policies',tmp_path/'data/drip_r/policies')
    _,engine=build(tmp_path,corpus='drip_r',profile='course',mode='sparse')
    try:
        assert engine.index.encoder is None and engine.reranker is None
        assert engine.retrieve(SearchRequest(query='gift return',incident_date='2026-11-02',mode='sparse'))['final']
    finally: engine.index.close()


def test_development_training_test_separation():
    from claimguard.datasets.drip_r import read_jsonl
    from claimguard.evaluation.runner import validate_split
    dev=read_jsonl(ROOT/'data/drip_r/development/questions.jsonl')
    train=read_jsonl(ROOT/'data/drip_r/development/training.jsonl')
    validate_split(ROOT,'drip_r',dev,'development')
    assert not {r['scenario_group'] for r in train}&{r['scenario_group'] for r in dev}
    test=read_jsonl(ROOT/'data/drip_r/evaluation/questions.jsonl')
    with pytest.raises(ValueError,match='leakage'): validate_split(ROOT,'drip_r',[test[0]],'development')
    assert {r['language'] for r in dev}=={'fr','en'}


def test_mcp_document_tools_do_not_require_models(monkeypatch):
    from claimguard.mcp import server
    def unavailable(): raise AssertionError('Document reading must not load models')
    monkeypatch.setenv('CLAIMGUARD_CORPUS','drip_r')
    monkeypatch.setattr(server,'services',unavailable)
    result=server.get_policy_section('DRIP-001','1.0','1.15')
    assert result['chunks'] and result['reference']=='DRIP-001@1.0#1.15'


def test_index_identity_and_catalog_remain_stable(offline_drip):
    from claimguard.storage.catalog import Catalog
    catalog=Catalog(ROOT/'var/drip_r')
    authoritative={c.chunk_id:c.text for c in catalog.chunks()}
    assert authoritative
    assert all(c.text in authoritative_text for c in offline_drip.index.chunks.values()
               for authoritative_text in [next(a.text for a in catalog.chunks() if a.reference()==c.reference() and c.text in a.text)])
    assert {c.chunk_id:c.text for c in catalog.chunks()}==authoritative


def test_ui_keeps_evidence_when_groq_fails(offline_drip,monkeypatch):
    import claimguard.runtime as runtime
    import claimguard.prompts.rag as rag
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('GROQ_API_KEY','dummy-local-test')
    monkeypatch.setattr(runtime,'build',lambda *a,**k: (None,offline_drip))
    monkeypatch.setattr(rag,'groq_model',lambda: object())
    monkeypatch.setattr(rag,'rewrite',lambda query,llm: query)
    def unavailable(*args,**kwargs): raise ConnectionError('synthetic unavailable provider')
    monkeypatch.setattr(rag,'generate',unavailable)
    app=AppTest.from_file(str(ROOT/'app/Home.py')).run(timeout=30)
    app.checkbox[0].check()
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert any('Brouillon indisponible' in w.value for w in app.warning)
    assert any('sections distinctes' in c.value for c in app.caption)
    # The same running UI remains usable after changing corpus.
    app.sidebar.selectbox[0].select('novaretail').run(timeout=30)
    assert not app.exception
    assert not any('sections distinctes' in c.value for c in app.caption)
