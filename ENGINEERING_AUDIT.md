# Final engineering audit

Subsequent live-model validation is now recorded in [LIVE_GENERATION_VALIDATION.md](LIVE_GENERATION_VALIDATION.md), with mixed outcomes. This audit describes the earlier pre-provider state.

**11 October 2026 · Verdict:** ingestion and retrieval are verified with real MiniLM inference. Complete RAG answer generation remains **unverified** because no LLM provider is configured. The architecture is unchanged.

## Verified through real execution

- PDF, TXT and Markdown ingestion through actual FastAPI handlers with real 384-dimensional MiniLM embeddings and FAISS. A two-page PDF retrieved the correct document and page.
- Three renamed reuploads returned `409`; SQLite chunk count and FAISS count stayed unchanged. No duplicate index entries were created.
- A separate Python process recovered the same search ranking from SQLite after intentionally corrupting the derived FAISS file. Deletion removed document/page/chunk rows; another fresh process confirmed that deletion persisted.
- Blank/invalid queries, corrupt PDF, empty file, unsupported type, oversized upload and unknown deletion returned the expected `422/400/415/413/404` statuses.
- Real retrieved passages were put into a bounded context. Every context source ID, filename, page and passage matched returned source objects; truncated passage text matched the exact SQLite page substring and offsets.
- The running API was checked outside the network sandbox: `llm_configured=false`. Local settings have provider `none`, no model/key and no `.env`; local Ollama was unreachable. No LLM was installed or downloaded.
- **41 automated tests passed, 0 failed, 0 skipped; Ruff passed.** Real-model lifecycle checks above run separately from the unit suite.

Evidence: [engineering execution](evaluation/results/audit/engineering.json), [test results](evaluation/results/audit/tests.xml).

## Verified only with mocks / injected failures

OpenAI-compatible and Ollama HTTP request/response contracts, timeout/auth/malformed-response handling, generated-answer citation validation, and exact outgoing-context/returned-source identity through the generation call. The generation callback in that test is a recording test double, not a model. Transaction/rebuild failure scenarios are injected; real crash/power-loss testing was not performed.

## Bugs fixed

1. **Committed first upload could remain invisible after a transient rebuild failure.** Retrieval returned early on empty cached metadata and never retried the invalid index. It now rebuilds an invalid index before checking emptiness. The regression failed before the change and passes afterward.
2. **Malformed citations could bypass validation.** An answer with `[S1]` plus `[S99, S1]` was accepted because only standalone citation syntax was extracted. Source-like bracket groups outside the allowed standalone identifiers are now rejected. The regression failed before the change and passes afterward.

Only those production fixes were made. The evaluator gained dataset selection and dynamic chart counts to run the requested additional questions; no retrieval method, model, threshold or architecture was changed.

## Retrieval results

Real pinned MiniLM, CPU, one OpenMP thread, unchanged corpus. Three sequential warm passes per configuration. Times include query encoding/search/metadata, exclude model loading, HTTP and generation. New set: **six answerable + four near-topic unanswerable**. Original set: 24 + four. Ground-truth review: [DATASET_AUDIT.md](evaluation/DATASET_AUDIT.md).

| Dataset | Config (size/overlap) | Recall@3 | Recall@5 | MRR@5 | Negative rejection | p50 / p95 |
|---|---|---:|---:|---:|---:|---:|
| Original 28 | A: 500/100 | 89.58% | 93.75% | 0.8576 | 4/4 | 2.44 / 2.71 ms |
| Original 28 | B: 1000/150 | 100% | 100% | 1.0000 | 4/4 | 2.37 / 2.55 ms |
| New 10 | A: 500/100 | 91.67% | 91.67% | 0.9167 | **0/4** | 3.19 / 3.57 ms |
| New 10 | B: 1000/150 | 83.33% | 100% | 0.7000 | **0/4** | 3.16 / 3.39 ms |

A generated 31 chunks and B generated 16. The original set had 84 timed retrievals per configuration; the new set had 30. Both rejected zero answerable questions. Environment, corpus/dataset hashes and per-question passages are preserved under [audit results](evaluation/results/audit/).

**The important failure is abstention:** all four new unknown-specific-value questions scored above the unchanged 0.30 threshold (A: 0.455–0.602; B: 0.378–0.588). Relevant topic text does not establish the requested number or guarantee. These are false evidence acceptances, not observed hallucinations: no LLM was run. Increasing the threshold on these ten examples would be test-set tuning, so it was not done.

The larger chunks also no longer win every metric: h02's necessary passage ranked fifth in B, reducing Recall@3 and MRR. A missed half of h05's cross-document evidence at five results. This is visible in saved per-query traces.

## Not tested and remaining limitations

- No live LLM answer, live-provider citation behavior, answer faithfulness or real prompt-injection resistance was tested. A citation ID can be valid while its associated claim is unsupported. Complete end-to-end RAG validation still requires an available provider.
- No new Docker build/run, production concurrency, power-loss recovery, OCR or public-deployment security validation. The earlier browser UI checks remain documented in `VALIDATION.md`; the UI was unchanged and was not re-audited here.
- Original questions are mostly close paraphrases; corpus/question co-authorship introduces construction bias. No direct evaluation-file leakage into indexing was found. New labels were read against complete source sections and mechanically checked, but are not independently human-adjudicated. Exact-anchor relevance may miss alternative evidence.
- Single backend worker, in-memory exact index and complete rebuilds remain appropriate only for the documented local scale. Similarity abstention is demonstrably unreliable for near-topic unknowns; no universal retrieval/answer-accuracy claim is justified.

## Reproduce

```bash
HF_HUB_OFFLINE=1 python scripts/audit_engineering.py
pytest -q --junitxml=evaluation/results/audit/tests.xml
HF_HUB_OFFLINE=1 python -m evaluation.evaluate --output evaluation/results/audit/original
HF_HUB_OFFLINE=1 python -m evaluation.evaluate --dataset evaluation/audit_dataset.json --output evaluation/results/audit/challenging
```

Use the existing `.venv`; offline commands require the already downloaded model. Audit lifecycle tests use temporary storage and preserve the live application library. The original experiment artifacts are retained separately.
