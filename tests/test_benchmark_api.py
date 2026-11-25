"""Benchmark loop (accumulators reset per strategy, splits) and thin API, with test doubles."""
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from claimguard import evaluation
from claimguard.config import write_jsonl
from claimguard.rag import Result

ROOT = Path(__file__).resolve().parents[1]


class FakeTokenizerModel:
    max_seq_length = 256

    def tokenizer(self, text, add_special_tokens=True):
        return {'input_ids': text.split()}


class FakeRAG:
    collection = 'claimguard_c1000_o100'

    def __init__(self):
        self.models = type('M', (), {'dense': type('D', (), {'_client': FakeTokenizerModel()})(), 'reranker': None})()

    def retrieve(self, query, mode='hybrid', rerank=False, k=5, n_candidates=20, as_of=None):
        ids = ['r1', 'x', 'r2', 'y', 'z'] if rerank else ['r1', 'x', 'y', 'z', 'w']
        return [Document(page_content=i, metadata={'_id': i, 'reference': i}) for i in ids[:k]]


def test_every_strategy_starts_from_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, 'BENCHMARK', tmp_path)
    monkeypatch.setattr(evaluation, 'REPORTS', tmp_path)
    write_jsonl(tmp_path / 'questions.jsonl', [
        {'query_id': f'Q{i}', 'question': 'q', 'reference': f'R{i}', 'split': 'development'} for i in range(3)])
    (tmp_path / 'qrels_claimguard_c1000_o100.json').write_text(json.dumps({'Q0': ['r1', 'r2'], 'Q1': ['r1', 'r2'],
                                                                           'Q2': []}))
    report = evaluation.run_benchmark(FakeRAG(), 'documents', 'development', log=lambda *_: None)
    assert report['questions_without_qrels'] == ['Q2']  # reported, not silently dropped
    for name, result in report['results'].items():
        expected = 1.0 if 'rerank' in name else 0.5
        assert result['metrics']['recall@5'] == expected, name  # the notebook would accumulate up to 3.0
        assert 0 <= result['metrics']['precision@5'] <= 1
    assert len(report['results']) == 6


def test_documents_leakage_is_refused():
    questions = [{'reference': 'R1', 'split': 'development'}, {'reference': 'R1', 'split': 'test'}]
    try:
        evaluation.check_documents_leakage(questions)
    except ValueError:
        return
    raise AssertionError('leakage not detected')


def test_real_cfpb_splits_do_not_leak():
    evaluation.check_cfpb_leakage()


class FakeAppRAG:
    def ask(self, question, **options):
        assert set(options) == {'mode', 'rerank', 'rewrite', 'k', 'n_candidates', 'as_of'}  # no ground truth
        document = Document(page_content='The creditor shall mail written acknowledgment within 30 days.', metadata={
            '_id': 'id-1', 'citation': '12 CFR 1026.13(c)', 'reference': 'REGZ-013@2.0#c', 'paragraph_title': 'Time',
            'section_title': '§ 1026.13', 'regulation': 'Regulation Z', 'version': '2.0', 'version_date': '2019-04-01',
            'valid_until': None, 'source': '1026.13_2019-04-01.xml', 'url': 'https://www.ecfr.gov', 'start_index': 0})
        return Result(question=question, search_query=question, documents=[document],
                      generation_error='ConnectionError: down', warnings=['Génération indisponible'])


def test_api_returns_passages_when_generation_fails():
    from claimguard.api import create_app
    client = TestClient(create_app(rag_factory=FakeAppRAG))
    body = client.post('/api/ask', json={'question': 'How long to acknowledge?', 'as_of': '2025-01-15'}).json()
    assert body['answer'] is None and body['generation_error']
    assert body['documents'][0]['citation'] == '12 CFR 1026.13(c)'
    assert client.get('/api/evaluation').status_code == 200
    assert client.get('/api/status').json()['collection'].startswith('claimguard_')


def test_no_sqlite_in_application_code():
    for path in (ROOT / 'src').rglob('*.py'):
        assert not re.search(r'\bsqlite3?\b', path.read_text(encoding='utf-8'), re.I), path
    assert not list(ROOT.glob('**/*.sqlite')) or all('.venv' in p.parts for p in ROOT.glob('**/*.sqlite'))
