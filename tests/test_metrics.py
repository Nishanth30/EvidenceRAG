import pytest
from evaluation.metrics import recall_at_k, reciprocal_rank


def test_evidence_recall_is_not_hit_rate():
    truth = [{'document': 'a', 'page': None, 'quote': 'first fact'},
             {'document': 'b', 'page': 2, 'quote': 'second fact'}]
    wrong = {'document_name': 'x', 'page': None, 'text': 'unrelated'}
    first = {'document_name': 'a', 'page': None, 'text': 'first fact'}
    second = {'document_name': 'b', 'page': 2, 'text': 'second fact'}
    results = [wrong, first, first, second]
    assert recall_at_k(results, truth, 3) == .5
    assert recall_at_k(results, truth, 5) == 1
    assert reciprocal_rank(results, truth) == .5
    assert reciprocal_rank([wrong], truth) == 0
    with pytest.raises(ValueError):
        recall_at_k([], [], 3)
