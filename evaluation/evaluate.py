"""python -m evaluation.evaluate --repeats 3"""
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import tempfile
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from app.config import Settings
from app.embeddings.embedding_service import EmbeddingService
from app.ingestion.pipeline import DocumentService
from app.retrieval.retriever import Retriever
from evaluation.metrics import normalize, recall_at_k, reciprocal_rank

ROOT = Path(__file__).resolve().parents[1]


def run(repeats=3, output=None, dataset_path=None):
    if repeats < 1:
        raise ValueError('repeats must be positive')
    output = output or ROOT / 'evaluation/results'
    output.mkdir(parents=True, exist_ok=True)
    dataset_path = dataset_path or ROOT / 'evaluation/dataset.json'
    dataset = json.loads(dataset_path.read_text())
    questions = dataset['questions']
    documents = sorted((ROOT / 'sample_documents').glob('*.md'))
    contents = {p.name: p.read_text() for p in documents}
    for question in questions:
        for evidence in question['evidence']:
            assert normalize(evidence['quote']) in normalize(contents[evidence['document']]), question['id']
    base = Settings(_env_file=None, data_dir=ROOT / 'data', embedding_device='cpu')
    embeddings = EmbeddingService(base)
    # Explicit warmup excludes download/model initialization from all measured queries.
    embeddings.encode(['Warm the encoder before retrieval timing.'])
    records, summaries = [], []
    (ROOT / 'data/evaluation').mkdir(parents=True, exist_ok=True)
    for label, size, overlap in [('A', 500, 100), ('B', 1000, 150)]:
        with tempfile.TemporaryDirectory(dir=ROOT / 'data/evaluation') as directory:
            settings = base.model_copy(update={'data_dir': Path(directory), 'chunk_size': size,
                                              'chunk_overlap': overlap, 'chunk_strategy': 'recursive'})
            service = DocumentService(settings, embeddings)
            try:
                for document in documents:
                    service.ingest(document.name, document.read_bytes(), 'text/markdown')
                retriever = Retriever(service)
                retriever.search(questions[0]['question'])
                latencies = []
                quality = []
                for repeat in range(repeats):
                    for question in questions:
                        response = retriever.search(question['question'], 5)
                        latencies.append(response.elapsed_ms)
                        if repeat:
                            continue
                        results = [p.model_dump() for p in response.results]
                        truth = question['evidence']
                        record = {'configuration': label, 'id': question['id'], 'kind': question['kind'],
                                  'question': question['question'], 'answerable': bool(truth),
                                  'recall_at_3': recall_at_k(results, truth, 3) if truth else None,
                                  'recall_at_5': recall_at_k(results, truth, 5) if truth else None,
                                  'mrr_at_5': reciprocal_rank(results, truth) if truth else None,
                                  'rejected_by_threshold': response.insufficient_evidence,
                                  'top_score': results[0]['score'] if results else None,
                                  'elapsed_ms_first_repeat': response.elapsed_ms,
                                  'retrieved': results}
                        records.append(record)
                        quality.append(record)
                positives = [r for r in quality if r['answerable']]
                negatives = [r for r in quality if not r['answerable']]
                summary = {'configuration': label, 'strategy': 'recursive', 'chunk_size': size,
                           'overlap': overlap, 'chunks': service.store.index.ntotal,
                           'queries': len(questions), 'answerable_queries': len(positives),
                           'unanswerable_queries': len(negatives), 'timed_retrievals': len(latencies),
                           'recall_at_3': float(np.mean([r['recall_at_3'] for r in positives])),
                           'recall_at_5': float(np.mean([r['recall_at_5'] for r in positives])),
                           'mrr_at_5': float(np.mean([r['mrr_at_5'] for r in positives])),
                           'negative_rejection_rate': float(np.mean([r['rejected_by_threshold'] for r in negatives])),
                           'answerable_rejection_rate': float(np.mean([r['rejected_by_threshold'] for r in positives])),
                           'threshold': settings.similarity_threshold,
                           'latency_mean_ms': float(np.mean(latencies)),
                           'latency_p50_ms': float(np.percentile(latencies, 50)),
                           'latency_p95_ms': float(np.percentile(latencies, 95)),
                           'latency_min_ms': min(latencies), 'latency_max_ms': max(latencies)}
                summaries.append(summary)
                print(json.dumps(summary), flush=True)
            finally:
                service.close()
    environment = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                   'platform': platform.platform(), 'machine': platform.machine(),
                   'processor': platform.processor(), 'logical_cpus': os.cpu_count(),
                   'python': platform.python_version(), 'embedding_device': 'cpu',
                   'omp_num_threads': os.getenv('OMP_NUM_THREADS'),
                   'embedding_model': base.embedding_model, 'embedding_revision': base.embedding_revision,
                   'packages': {p: version(p) for p in ['sentence-transformers', 'torch', 'faiss-cpu', 'numpy']},
                   'provenance': dataset['provenance'],
                   'dataset_sha256': hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
                   'document_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in documents},
                   'methodology': f'{repeats} sequential passes over all {len(questions)} queries per configuration, after warmup. perf_counter inside Retriever.search includes lock acquisition, query encoding, FAISS search, metadata assembly and deduplication. Excludes HTTP, UI, ingestion, model load and generation. Quality is measured once; MRR is truncated at 5. Relevance requires the full normalized anchor quote in the retrieved passage. Negatives excluded from recall/MRR. Threshold is not tuned on this dataset.'}
    (output / 'report.json').write_text(json.dumps({'environment': environment, 'configurations': summaries}, indent=2) + '\n')
    (output / 'per_query.json').write_text(json.dumps(records, indent=2) + '\n')
    pd.DataFrame(summaries).to_csv(output / 'comparison.csv', index=False)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    positions = np.arange(2)
    for i, (key, label) in enumerate([('recall_at_3', 'Recall@3'), ('recall_at_5', 'Recall@5'), ('mrr_at_5', 'MRR@5')]):
        axes[0].bar(positions + (i - 1) * .23, [s[key] for s in summaries], .23, label=label)
    labels = ['A: 500 / 100', 'B: 1000 / 150']
    answerable_count = sum(bool(q['evidence']) for q in questions)
    axes[0].set(xticks=positions, xticklabels=labels, ylim=(0, 1.08), ylabel='Score', title=f'Evidence retrieval · {answerable_count} answerable examples')
    axes[0].legend(loc='lower right')
    axes[1].bar(positions - .17, [s['latency_p50_ms'] for s in summaries], .34, label='p50')
    axes[1].bar(positions + .17, [s['latency_p95_ms'] for s in summaries], .34, label='p95')
    axes[1].set(xticks=positions, xticklabels=labels, ylabel='Milliseconds', title=f'Warm CPU retrieval · {len(questions)} queries per pass')
    axes[1].legend()
    fig.suptitle('EvidenceRAG | AI-authored sample set, not an independent benchmark')
    fig.savefig(output / 'comparison.png', dpi=170)
    plt.close(fig)
    return summaries


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--dataset', type=Path)
    args = parser.parse_args()
    run(args.repeats, args.output, args.dataset)
