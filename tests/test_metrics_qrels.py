"""Retrieval metrics and qrels matching on cases with known results."""
import pytest

from claimguard.evaluation import hit, match_chunks, mrr, ndcg, ngrams, normalize, precision, recall, score, split_of


def test_precision_recall_known_values():
    rels, ret = ['a', 'b'], ['a', 'x', 'b', 'y', 'z']
    assert precision(5, rels, ret) == pytest.approx(2 / 5)
    assert recall(5, rels, ret) == 1.0
    assert precision(1, rels, ret) == 1.0
    assert recall(1, rels, ret) == 0.5
    assert mrr(5, rels, ['x', 'a']) == 0.5
    assert ndcg(5, ['a'], ['a']) == 1.0
    assert recall(5, [], ret) == 0.0
    assert hit(5, rels, ['x', 'b']) == 1.0 and hit(1, rels, ['x', 'b']) == 0.0


def test_duplicate_ids_are_counted_once():
    # without deduplication, ['a', 'a', 'a'] would give recall 3.0 for a single relevant chunk
    assert recall(5, ['a'], ['a', 'a', 'a']) == 1.0
    assert precision(5, ['a'], ['a', 'a', 'a', 'b']) == pytest.approx(1 / 5)


def test_metrics_are_bounded():
    for rels, ret in ([['a'], ['a'] * 5], [['a', 'b', 'c'], ['c', 'b', 'a', 'd', 'e']], [['q'], []]):
        assert all(0 <= v <= 1 for v in score(5, rels, ret).values())


def test_five_gram_match_and_generic_filter():
    passage = 'The creditor shall mail or deliver written acknowledgment within 30 days of receiving a notice.'
    chunks = [('c1', 'Intro. The creditor shall mail or deliver written acknowledgment within 30 days of receiving'),
              ('c2', 'For purposes of this section the creditor shall mail or deliver a statement.'),
              ('c3', 'Unrelated text about debt collection validation notices.')]
    frequency = {g: 1 for g in ngrams(passage, 5)}
    frequency['the creditor shall mail or'] = frequency['creditor shall mail or deliver'] = 50  # boilerplate
    relevant, generic = match_chunks(passage, chunks, frequency, 5, limit=5)
    assert relevant == ['c1']
    assert generic == ['c2']  # shares only the generic 5-grams


def test_normalize_matches_course_definition():
    assert normalize('No later than 60 days, § 1026.13(b).') == 'nolaterthan60days102613b'


def test_split_is_deterministic():
    assert split_of('REGZ-013@2.0#b') == split_of('REGZ-013@2.0#b')
    assert split_of('REGZ-013@2.0#b') in {'development', 'test'}
