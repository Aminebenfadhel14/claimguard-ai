from datetime import date
import json
from pathlib import Path
import pytest
from claimguard.models import PolicyMetadata, Hit, GeneratedAnswer, Citation
from claimguard.ingestion.pipeline import parse,clean_text,extract_tables
from claimguard.storage.catalog import Catalog
from claimguard.retrieval.fusion import rrf
from claimguard.evaluation.metrics import metrics
from claimguard.prompts.rag import validate_citations,generate

ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def metadata():
    return PolicyMetadata(document_id='TEST-V1',policy_id='TEST-001',title='Test',category='returns',department='Support',version='1.0',effective_date='2025-01-01')
@pytest.fixture
def source(tmp_path,metadata):
    p=tmp_path/'policy.md';p.write_text('## 4.2 Exchange\nDo not refund without proof. Within 14 days; maximum EUR 100.\n\n## 4.3 Exceptions\nLiquid damage is excluded.')
    p.with_suffix('.md.json').write_text(metadata.model_dump_json());return p

def test_clean_preserves_business_rules():
    assert clean_text(' Do  not refund\tEUR 100.\r\n14 days ')=='Do not refund EUR 100.\n14 days'
def test_sections_pages_metadata(source,metadata):
    cs=parse(source,metadata,chunk_size=80,chunk_overlap=10)
    assert {c.section for c in cs}=={'4.2','4.3'}
    assert all(c.page==1 and c.file_hash and c.metadata.version=='1.0' for c in cs)
    assert len({c.chunk_id for c in cs})==len(cs)
    assert [c.chunk_id for c in cs]==[c.chunk_id for c in parse(source,metadata,80,10)]
def test_pdf_parsing_and_tables(tmp_path,metadata):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,PageBreak,Table,TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    p=tmp_path/'policy.pdf';s=getSampleStyleSheet()
    t=Table([['Condition','Days'],['Defect','14']]);t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),1,colors.black)]))
    SimpleDocTemplate(str(p)).build([Paragraph('4.2 Exchange',s['Heading2']),Paragraph('Do not refund without proof.',s['BodyText']),t,
                                  PageBreak(),Paragraph('4.3 Exceptions',s['Heading2']),Paragraph('Misuse is excluded.',s['BodyText'])])
    cs=parse(p,metadata)
    assert {c.page for c in cs}=={1,2}
    assert any('Do not refund' in c.text for c in cs)
    assert extract_tables(p)[0]['rows'][1]==['Defect','14']
def test_txt_page_numbers(tmp_path,metadata):
    p=tmp_path/'policy.txt';p.write_text('4.2 Exchange\nWithin 14 days.\fContinue checking proof.')
    cs=parse(p,metadata);assert [(c.page,c.section) for c in cs]==[(1,'4.2'),(2,'4.2')]
def test_catalog_dedup_conflict_and_deactivate(source,tmp_path):
    c=Catalog(tmp_path/'db');assert c.ingest(source)['status']=='added'
    assert c.ingest(source)['status']=='duplicate'
    source.write_text(source.read_text(encoding='utf-8').replace('14','7'))
    with pytest.raises(ValueError,match='Immutable'):c.ingest(source)
    c.deactivate('TEST-001','1.0','reviewer');assert c.chunks()==[]
def test_historical_access_and_category(tmp_path):
    c=Catalog(tmp_path/'db')
    for p in sorted((ROOT/'data/policies').glob('*.md')):c.ingest(p)
    old=[x for x in c.chunks(date(2025,11,2)) if x.metadata.policy_id=='RETURN-001']
    new=[x for x in c.chunks(date(2026,1,1)) if x.metadata.policy_id=='RETURN-001']
    assert {x.metadata.version for x in old}=={'1.0'}
    assert {x.metadata.version for x in new}=={'2.0'}
    assert c.chunks(access=('public',))==[]
    assert all(x.metadata.category=='billing' for x in c.chunks(category='billing'))
    assert '7 calendar days' in c.compare('RETURN-001','1.0','2.0')
def test_overlap_is_rejected(source,tmp_path,metadata):
    c=Catalog(tmp_path/'db');c.ingest(source)
    metadata.version='2.0';source.with_suffix('.md.json').write_text(metadata.model_dump_json())
    with pytest.raises(ValueError,match='Overlapping'):c.ingest(source)
def test_rrf_exact_and_dedup(source,metadata):
    a,b=parse(source,metadata)
    ha,hb=Hit(chunk=a,score=100,stage='dense'),Hit(chunk=b,score=.1,stage='sparse')
    r=rrf([[ha,hb],[hb,ha]])
    assert len(r)==2 and all(h.score==pytest.approx(1/61+1/62) for h in r)
    assert rrf([[ha,ha]])[0].score==pytest.approx(1/61)
def test_metrics_do_not_count_duplicate_sections():
    m=metrics(['a','a','b'],['a','b'])
    assert m['recall@1']==.5 and m['recall@3']==1 and m['mrr@10']==1
    assert metrics(['x','a'],['a'])['mrr@10']==.5
    with pytest.raises(ValueError):metrics([],[])
def test_fabricated_citations_rejected(source,metadata):
    hit=Hit(chunk=parse(source,metadata)[0],score=.5,stage='dense')
    for cid,quote in [('nonexistent','refund'),(hit.chunk.chunk_id,'Refund is guaranteed.')]:
        a=GeneratedAnswer(answer='X',citations=[Citation(chunk_id=cid,quote=quote)],abstained=False)
        with pytest.raises(ValueError):validate_citations(a,[hit])
    with pytest.raises(ValueError):validate_citations(GeneratedAnswer(answer='X',citations=[],abstained=False),[hit])
def test_empty_context_abstains_without_llm():
    assert generate('Should I be refunded?',[],None).abstained

def test_annotation_references_and_split_integrity(tmp_path):
    c=Catalog(tmp_path/'db')
    for p in sorted((ROOT/'data/policies').glob('*.md')):c.ingest(p)
    questions=[json.loads(l) for l in (ROOT/'data/evaluation/questions.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(questions)>=50 and len({q['question_id'] for q in questions})==len(questions)
    for q in questions:
        refs={x.reference() for x in c.chunks(date.fromisoformat(q['incident_date']))}
        assert set(q['relevant_sections'])<=refs
        assert bool(q['relevant_sections'])==(q['difficulty']!='no_answer')
    train=[json.loads(l) for l in (ROOT/'data/synthetic/train.jsonl').read_text(encoding='utf-8').splitlines()]
    val=[json.loads(l) for l in (ROOT/'data/synthetic/validation.jsonl').read_text(encoding='utf-8').splitlines()]
    a,b,d=({x['scenario_group'] for x in r} for r in (train,val,questions))
    assert not (a&b or a&d or b&d)
