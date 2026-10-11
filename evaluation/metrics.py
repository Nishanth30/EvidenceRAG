"""Evidence-level recall and MRR with explicit cutoff; negatives are separate."""
import re


def normalize(text):
    return re.sub(r'\s+', ' ', text).strip()


def relevant_indices(result, evidence):
    return {i for i, item in enumerate(evidence)
            if result['document_name'] == item['document']
            and result['page'] == item.get('page')
            and normalize(item['quote']) in normalize(result['text'])}


def recall_at_k(results, evidence, k):
    if not evidence:
        raise ValueError('Recall is undefined for unanswerable questions')
    found = set()
    for result in results[:k]:
        found.update(relevant_indices(result, evidence))
    return len(found) / len(evidence)


def reciprocal_rank(results, evidence, k=5):
    if not evidence:
        raise ValueError('MRR is undefined for unanswerable questions')
    return next((1 / rank for rank, result in enumerate(results[:k], 1)
                 if relevant_indices(result, evidence)), 0.0)
