"""Real models + local Qdrant integration; no fake embeddings or simulated scores."""
from pathlib import Path
from datetime import date
import pytest
from claimguard.runtime import build
from claimguard.models import SearchRequest

@pytest.fixture(scope='module')
def engine():
    _,e=build(Path(__file__).resolve().parents[1],with_reranker=True)
    yield e
    e.index.close()

def test_real_modes_and_trace(engine):
    query='My defective phone was refused for exchange four days after purchase.'
    for mode in ('dense','sparse','hybrid','rerank'):
        t=engine.retrieve(SearchRequest(query=query,incident_date='2026-11-02',mode=mode,top_k=5))
        assert 'RETURN-001@2.0#4.2' in [h.chunk.reference() for h in t['final']]
        assert all(h.chunk.metadata.version=='2.0' for h in t['final'] if h.chunk.metadata.policy_id=='RETURN-001')
        if mode in ('hybrid','rerank'):assert t['dense'] and t['sparse'] and t['rrf']
        if mode=='rerank':assert t['final'][0].chunk.reference()=='RETURN-001@2.0#4.2'

def test_real_temporal_and_access_filters(engine):
    for mode in ('dense','sparse'):
        hits=engine.index.search('defective product exchange',date(2025,11,1),mode)
        assert hits and all(h.chunk.metadata.version=='1.0' and h.chunk.metadata.policy_id=='RETURN-001' for h in hits)
        assert engine.index.search('defective product',date(2026,11,2),mode,access=('public',))==[]
        bill=engine.index.search('payment double charge',date(2026,11,2),mode,category='billing')
        assert bill and all(h.chunk.metadata.category=='billing' for h in bill)
