"""RAG core with test doubles: retrieval, reranking, rewriting fallback, Groq failures, citations."""
import pytest
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from claimguard import rag as core
from claimguard.rag import RAG, Answer, Citation, dropped_terms, in_force, retrieve, verify


def doc(identifier, text):
    return Document(page_content=text, metadata={'_id': identifier, 'citation': f'12 CFR x({identifier})',
                                                 'paragraph_title': 't', 'reference': identifier})


class FakeStore:
    def __init__(self, documents):
        self.documents, self.calls = documents, []

    def similarity_search(self, query, k, filter=None):
        self.calls.append({'query': query, 'k': k, 'filter': filter})
        return [Document(page_content=d.page_content, metadata=dict(d.metadata)) for d in self.documents[:k]]


class FakeReranker:
    def predict(self, pairs, show_progress_bar=False):
        return [float(len(text)) for _, text in pairs]  # longer passage = higher score


DOCS = [doc('a', 'short'), doc('a', 'short'), doc('b', 'a much longer passage'), doc('c', 'mid size')]


def stores():
    return {mode: FakeStore(DOCS) for mode in core.MODES}


def test_retrieve_requests_candidates_dedups_and_cuts_to_k():
    s = stores()
    result = retrieve(s, None, 'q', mode='dense', k=2, n_candidates=20)
    assert s['dense'].calls[0]['k'] == 20
    assert [core.doc_id(d) for d in result] == ['a', 'b']


def test_rerank_reorders_candidates():
    result = retrieve(stores(), FakeReranker(), 'q', mode='hybrid', rerank=True, k=3, n_candidates=20)
    assert [core.doc_id(d) for d in result] == ['b', 'c', 'a']
    assert result[0].metadata['rerank_score'] > result[1].metadata['rerank_score']


def test_rerank_without_model_fails_loudly():
    with pytest.raises(RuntimeError):
        retrieve(stores(), None, 'q', rerank=True)


def test_in_force_filter_on_dates():
    flt = in_force('2025-01-15')
    assert flt.must[0].key == 'metadata.valid_from_int' and flt.must[0].range.lte == 20250115
    assert flt.must[1].range.gt == 20250115
    assert in_force(None) is None


def make_rag(llm):
    instance = RAG.__new__(RAG)
    instance.models = type('M', (), {'reranker': None})()
    instance.collection = 'test'
    instance.stores = stores()
    instance._llm = llm
    return instance


class FailingLLM:
    def invoke(self, *_args, **_kwargs):
        raise ConnectionError('Groq down')

    def __or__(self, other):
        return self

    def __ror__(self, other):
        return self

    def with_structured_output(self, *_args, **_kwargs):
        return self


def test_groq_failure_keeps_passages_and_invents_nothing():
    result = make_rag(FailingLLM()).ask('How many days?', mode='dense', rewrite=True, k=2)
    assert result.search_query == 'How many days?'  # rewrite failed -> original question
    assert result.rewrite_error and result.generation_error
    assert result.answer is None
    assert [core.doc_id(d) for d in result.documents] == ['a', 'b']


def test_rewrite_is_used_for_search_but_answer_uses_original_question(monkeypatch):
    llm = FakeListChatModel(responses=['billing error notice 60 days'])
    seen = {}

    def fake_answer_chain(_llm):
        class Chain:
            def invoke(self, payload):
                seen.update(payload)
                return Answer(answer='Within 60 days.', citations=[Citation(passage=2, quote='a much longer passage')])
        return Chain()

    monkeypatch.setattr(core, 'answer_chain', fake_answer_chain)
    rag = make_rag(llm)
    result = rag.ask('Within how many days must I write?', mode='dense', k=3)
    assert rag.stores['dense'].calls[0]['query'] == 'billing error notice 60 days'
    assert seen['question'] == 'Within how many days must I write?'
    assert result.citations[0]['verified'] is True
    assert any('60' in w for w in result.warnings)  # 60 appears neither in passages nor in the question


def test_verify_rejects_fabricated_quotes():
    documents = [doc('a', 'The creditor shall mail written acknowledgment within 30 days.')]
    answer = Answer(answer='30 days', citations=[Citation(passage=1, quote='within 45 days'),
                                                 Citation(passage=7, quote='x')])
    checked, warnings, _ = verify(answer, documents, 'q')
    assert [c['verified'] for c in checked] == [False, False]
    assert any('non étayée' in w for w in warnings)


def test_quote_with_ellipsis_must_match_each_fragment_in_order():
    from claimguard.rag import quote_found
    passage = 'The creditor shall mail written acknowledgment to the consumer within 30 days of receiving a notice.'
    assert quote_found('The creditor shall mail written acknowledgment...', passage)
    assert quote_found('The creditor shall mail … within 30 days of receiving', passage)
    assert not quote_found('within 30 days … The creditor shall mail', passage)  # wrong order
    assert not quote_found('The creditor shall email written acknowledgment...', passage)
    assert not quote_found('30 days', passage)  # too short to be evidence


def test_rewrite_dropped_terms_are_reported():
    assert dropped_terms('I did not authorize the $500 charge on 01/15', 'unauthorized charge') == \
        sorted(['$500', '01', '15', 'negation'])
