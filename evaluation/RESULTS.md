# Retrieval experiment results

Measured on 11 October 2026 IST (raw UTC timestamp: 2026-10-10T19:10:01Z). The full environment and corpus hashes are preserved in `results/report.json`.

## Setup

- Five original AI-authored Markdown documents about queues, databases, distributed systems, retrieval and observability.
- 28 AI-authored candidate questions: 20 direct/paraphrased, four requiring two evidence units, four unanswerable.
- Source anchors checked programmatically for exact presence. No independent human adjudication or held-out split. The question set is an educational development example, not a rigorous benchmark.
- Real `sentence-transformers/all-MiniLM-L6-v2`, pinned revision `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, CPU, 384-dimensional normalized embeddings.
- macOS 27.0.1, ARM64, 10 logical CPUs, Python 3.11.16. OpenMP thread count: one. Hardware model/RAM were not collected; the reproducible environment record contains available platform details.
- Both configurations use recursive splitting, the same corpus/questions and top five retrieval. Quality excludes the four unanswerable questions.

| Measurement | A: 500 chars / 100 overlap | B: 1000 chars / 150 overlap |
|---|---:|---:|
| Chunks | 31 | 16 |
| Recall@3 | 0.895833 | 1.000000 |
| Recall@5 | 0.937500 | 1.000000 |
| MRR@5 | 0.857639 | 1.000000 |
| Unanswerable rejection rate at 0.30 | 4/4 | 4/4 |
| Answerable rejection rate at 0.30 | 0/24 | 0/24 |
| Warm mean latency | 2.642 ms | 2.611 ms |
| Warm p50 latency | 2.622 ms | 2.610 ms |
| Warm p95 latency | 3.020 ms | 2.908 ms |
| Timed queries | 84 | 84 |

Three sequential passes over the 28 questions were timed after warming the model. Timings include query embedding, lock acquisition, FAISS lookup, metadata assembly and duplicate suppression. They exclude indexing, model initialization, HTTP, UI and generation. A and B ran sequentially; small latency differences are not evidence of a statistically meaningful speedup. Browser/API requests can show larger timings because their environment and workload differ.

## What changed and why it matters

B produced roughly half as many passages and retrieved every labeled unit within the top three for these examples. These documents contain short, clearly named sections; larger chunks often include more of each section's explanatory context. That is a plausible explanation for better retrieval, rather than proof that larger chunks generally win.

The recorded A failures at five results are concrete:

- **q03**, reliably scheduling an event after a database update: A retrieved outbox-related passages but did not retrieve a passage containing the complete labeled anchor among the top five. Evidence recall and reciprocal rank were zero under the strict relevance definition.
- **q22**, timeouts plus idempotent consumer updates: A retrieved the timeout evidence first but missed the required deduplication-table anchor in its top five. Evidence recall was 0.5 while reciprocal rank was 1.0. This demonstrates why MRR alone can hide incomplete evidence for multi-part questions.

Use `results/per_query.json` to inspect the actual passages, scores and offsets. A passage containing useful partial context can still fail the full-anchor rule. Labeling and chunk boundary effects therefore influence these numbers.

## Interpretation limits

The corpus and questions were authored together, so the set is easy and potentially biased. B's 100% is retrieval coverage on 24 examples, not answer accuracy or a production guarantee. No LLM answer quality was evaluated. The four negatives were rejected, but four examples cannot establish a robust threshold, especially for near-topic questions lacking the requested detail.

Do not tune the application default to B based only on these results. First add independently written questions, broader documents, multiple valid evidence spans and a held-out test set. Inspect token truncation and exact-identifier queries. Evaluate false acceptance/rejection on a separate threshold-calibration set.

## Reproduce

```bash
python -m evaluation.evaluate --repeats 3
```

The command rewrites raw reports and the chart. This narrative records the initial measured run; update it only after inspecting new results. The evaluator builds temporary databases under `data/evaluation` and leaves the app's library intact.
