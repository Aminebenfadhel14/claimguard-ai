"""DRIP-R source provenance, no simulator leakage, meaningful corpus isolation tests."""
import hashlib
import json
from datetime import date
from pathlib import Path
import pytest
from claimguard.datasets.drip_r import HASHES, read_jsonl, agent_input, query_for, evaluation_sample
from claimguard.models import PolicyMetadata, SearchRequest
from claimguard.ingestion.pipeline import parse_with_sidecar
from claimguard.storage.catalog import Catalog
from claimguard.corpora import paths
from claimguard.retrieval.engine import RetrievalEngine

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/external/drip_r'
DATA=ROOT/'data/drip_r'

def test_pinned_original_bytes_and_dataset_shape():
    for name,digest in HASHES.items():
        assert hashlib.sha256((RAW/name).read_bytes()).hexdigest()==digest
    rows=read_jsonl(RAW/'scenarios.jsonl')
    assert len(rows)==len({r['scenario_id'] for r in rows})==400
    assert len({r['task_id'] for r in rows})==40
    assert len({r['persona']['Persona_id'] for r in rows})==10

def test_no_simulator_or_persona_leakage():
    row=read_jsonl(RAW/'scenarios.jsonl')[0]
    before=query_for(row)
    row['task']={'related_policy_issues':'SECRET_GOLD_ANNOTATION'}
    row['customer_task_detail']={'private_info':'SECRET_FACT','behavior':'SECRET_BEHAVIOR'}
    row['persona']={'Gender':'SECRET_DEMOGRAPHICS'}
    assert query_for(row)==before
    assert set(agent_input(row))=={'scenario_id','task_id','complaint','agent_brief'}
    assert 'SECRET_' not in json.dumps(agent_input(row))

def test_source_nan_is_flagged_and_never_exposed_to_agent():
    audit=json.loads((ROOT/'reports/drip_r/audit.json').read_text(encoding='utf-8'))
    assert len(audit['placeholder_fields_in_scenarios'])==10
    assert {r['task_id'] for r in audit['placeholder_fields_in_scenarios']}=={'task_051'}
    def reject_constant(value):
        raise ValueError('Nonstandard JSON constant: '+value)
    for line in (DATA/'agent_cases.jsonl').read_text(encoding='utf-8').splitlines():
        json.loads(line,parse_constant=reject_constant)

def test_extracted_policies_preserve_exact_text_and_cover_every_line():
    row=read_jsonl(RAW/'scenarios.jsonl')[0]
    originals=[row['Policy']['Primary Policy'],*row['Policy']['Related policies']]
    for i,original in enumerate(originals,1):
        p=DATA/'policies'/f'DRIP-{i:03d}.txt'
        assert p.read_bytes()==original['text'].encode('utf-8')
        meta,chunks=parse_with_sidecar(p)
        assert meta.effective_date is None and meta.temporal_basis=='dataset_snapshot'
        assert meta.version_origin=='project_snapshot'
        assert all(c.section_origin=='project_segmentation' and c.source_line_start for c in chunks)
        assert all(c.metadata.policy_id.startswith('DRIP-') for c in chunks)
        mapping=json.loads(p.with_suffix('.txt.sections.json').read_text(encoding='utf-8'))
        lines=p.read_text(encoding='utf-8').splitlines(keepends=True)
        assert ''.join(''.join(lines[s['start_line']-1:s['end_line']]) for s in mapping['sections'])==original['text']

def test_changed_source_rejects_stale_mapping(tmp_path):
    src=DATA/'policies/DRIP-001.txt';p=tmp_path/src.name
    for suffix in ('','.json','.sections.json'):
        (tmp_path/(src.name+suffix)).write_bytes(Path(str(src)+suffix).read_bytes())
    p.write_text(p.read_text(encoding='utf-8').replace('30 days','300 days',1))
    with pytest.raises(ValueError,match='SHA-256'):parse_with_sidecar(p)

def test_snapshot_never_invents_effective_date():
    data=json.loads((DATA/'policies/DRIP-001.txt.json').read_text(encoding='utf-8'))
    with pytest.raises(ValueError,match='cannot claim'):PolicyMetadata(**(data|{'effective_date':'2026-01-01'}))
    with pytest.raises(ValueError,match='required'):PolicyMetadata(**(data|{'temporal_basis':'effective_date'}))

def test_mapping_cannot_be_changed_under_existing_snapshot(tmp_path):
    src=DATA/'policies/DRIP-001.txt';p=tmp_path/src.name
    for suffix in ('','.json','.sections.json'):
        (tmp_path/(src.name+suffix)).write_bytes(Path(str(src)+suffix).read_bytes())
    catalog=Catalog(tmp_path/'catalog')
    assert catalog.ingest(p)['status']=='added'
    assert catalog.ingest(p)['status']=='duplicate'
    mapping_path=p.with_suffix('.txt.sections.json')
    mapping=json.loads(mapping_path.read_text(encoding='utf-8'))
    mapping['sections'][0]['title']='Changed title with identical source bytes'
    mapping_path.write_text(json.dumps(mapping),encoding='utf-8')
    with pytest.raises(ValueError,match='section mapping conflict'):catalog.ingest(p)

def test_sample_is_balanced_and_explicit_task_ids_are_used():
    sample=evaluation_sample(read_jsonl(RAW/'scenarios.jsonl'))
    assert len(sample)==len({r['scenario_id'] for r in sample})==50
    assert len({r['task_id'] for r in sample})==40
    from collections import Counter
    assert set(Counter(r['persona']['Persona_id'] for r in sample).values())=={5}
    assert any(r['task_id']=='task_019' and '_t018_' in r['scenario_id'] for r in sample)

def test_annotations_are_resolvable_and_training_excludes_benchmark(tmp_path):
    catalog=Catalog(tmp_path/'catalog')
    for p in (DATA/'policies').glob('*.txt'):catalog.ingest(p)
    refs={c.reference() for c in catalog.chunks()}
    qs=read_jsonl(DATA/'evaluation/questions.jsonl')
    assert len(qs)==58 and sum(bool(q['relevant_sections']) for q in qs)==50
    for q in qs:
        assert set(q['relevant_sections'])<=refs
        assert q['annotation_status']=='project_model_authored_needs_independent_review'
    raw=read_jsonl(RAW/'scenarios.jsonl')
    benchmark_queries={query_for(r) for r in raw}|{r['first_customer_message'] for r in raw}
    train,val=(read_jsonl(DATA/'training'/f'{name}.jsonl') for name in ('train','validation'))
    assert len(train)==60 and len(val)==30
    assert not {r['query'] for r in train+val}&benchmark_queries
    assert not {r['query'] for r in train}&{r['query'] for r in val}
    assert not {r['scenario_group'] for r in train+val}&{r['task_id'] for r in raw}
    for r in train+val:
        assert r['positive_reference'] in refs and r['negative_reference'] in refs

def test_corpus_paths_are_isolated_and_allowlisted():
    a,b=(paths(ROOT,x) for x in ('novaretail','drip_r'))
    assert all(a[k]!=b[k] for k in a)
    with pytest.raises(ValueError):paths(ROOT,'../../')

def test_empty_filtered_candidates_do_not_call_reranker():
    class EmptyIndex:
        def search(self,**kwargs):return []
    class Reranker:
        def predict(self,*args,**kwargs):raise AssertionError('No pairs should be scored')
    trace=RetrievalEngine(EmptyIndex(),Reranker()).retrieve(SearchRequest(query='nothing',incident_date='2026-11-02',mode='rerank'))
    assert trace['final']==[]

@pytest.fixture(scope='module')
def real_drip_engine():
    from claimguard.runtime import build
    _,engine=build(ROOT,corpus='drip_r',with_reranker=True)
    yield engine
    engine.index.close()

def test_real_drip_retrieval_sources_and_modes(real_drip_engine):
    for mode in ('dense','sparse','hybrid','rerank'):
        trace=real_drip_engine.retrieve(SearchRequest(query='Returning a gift without an order number',incident_date='2026-11-02',mode=mode,top_k=5))
        assert 'DRIP-001@1.0#1.15' in {h.chunk.reference() for h in trace['final']}
        assert all(h.chunk.metadata.policy_id.startswith('DRIP-') for h in trace['final'])
        assert all(h.chunk.metadata.effective_date is None for h in trace['final'])
    trace=real_drip_engine.retrieve(SearchRequest(query='Insure shipment and use signature for items valued at 100 dollars or more',incident_date='2026-11-02',mode='rerank'))
    assert 'DRIP-002@1.0#2.5' in {h.chunk.reference() for h in trace['final']}

def test_real_drip_empty_filter(real_drip_engine):
    trace=real_drip_engine.retrieve(SearchRequest(query='gift return',incident_date='2026-11-02',category='does-not-exist',mode='rerank'))
    assert trace['final']==[]
