# Validation record

**Latest:** [Final corrective pass](CORRECTIVE_VALIDATION.md). The results below are historical and preserved.

Latest generation check: [LIVE_GENERATION_VALIDATION.md](LIVE_GENERATION_VALIDATION.md). Three real local Qwen2.5 3B calls completed: one grounded answer passed, one paraphrase failed and was withheld, and one absent-fact question received a correct model refusal but was classified as answered. Complete raw results are saved. The initial-build table below is historical.

This is the initial build record. The later [engineering audit](ENGINEERING_AUDIT.md) contains updated tests, fixes, and harder evaluation results.

Validated on **11 October 2026 (Asia/Kolkata)** using Python 3.11.16 on macOS ARM64. Exact package versions are in `requirements-lock.txt`.

| Check | Result | Evidence / boundary |
|---|---|---|
| Automated pytest suite | **38 passed, 0 failed, 0 skipped** | `evaluation/results/tests.xml`; 0.28 seconds; five third-party SWIG deprecation warnings |
| Ruff | Passed | `ruff check app frontend evaluation tests scripts` |
| Real MiniLM + FAISS smoke | Passed | `python scripts/smoke_model.py`; shape, unit norms, exact self-match, actual production import path |
| Real API PDF lifecycle | Passed | `evaluation/results/api-smoke.json`; two-page PDF extraction/embedding, correct page-one top result, duplicates, missing LLM, validation and deletion |
| Real application restart | Passed | Restarted Uvicorn; five sample documents and 20 vectors recovered; outbox query ranked `message_delivery.md` first |
| Retrieval evaluation | Passed | Two configurations, 28 queries, 84 warm timings each; saved JSON, CSV, per-query evidence and chart |
| Streamlit in browser | Passed | Actual API-connected upload/index of disposable `ui-upload.txt`, counters increased 5→6 and 20→21, deletion returned to 5/20; semantic search rendered five real passages; chat showed missing-provider message plus sources |
| Upload UI limit | Passed | Browser displays 10 MB, matching default backend limit |
| Docker Compose schema | Passed | `docker compose config --quiet` |
| Docker image build/run | **Not tested** | Docker CLI exists but daemon socket unavailable |
| Live LLM generation | **Not tested** | No configured credentials or running Ollama service; both HTTP provider contracts, errors and citation validation tested with mocks |
| LLM answer quality/faithfulness | **Not measured** | Retrieval metrics do not evaluate generated answers |

## Native runtime issue found and mitigated

The first real evaluation exited with code 139 during combined FAISS/PyTorch inference. A minimal run loading FAISS before real MiniLM inference reproduced a segmentation fault. The encoder alone succeeded. The same combined path with `OMP_NUM_THREADS=1` succeeded; the real model smoke test and complete evaluation then passed.

`app/__init__.py` sets the one-thread default before native imports. This is a validated mitigation for this installed runtime; a complete upstream root-cause analysis is not claimed. The regression smoke script keeps the production import path, dimension/normalization assertions and actual FAISS search. Do not replace it with a fake embedding test when changing native dependencies.

## Evaluation integrity

The sample questions and documents were AI-authored together and are not independently verified. Relevant anchors were checked to exist in their source documents. The results establish reproducible operation on this sample, not general retrieval quality or production performance. All measured values are preserved in `evaluation/results/report.json`; no generation benchmark was run.

## Re-run

```bash
source .venv/bin/activate
pytest -q --junitxml=evaluation/results/tests.xml
ruff check app frontend evaluation tests scripts
python scripts/smoke_model.py
python -m evaluation.evaluate --repeats 3
# Requires the real API to already be running:
python scripts/smoke_api.py
```

The API smoke script creates and deletes only its own temporary PDF. It preserves the existing library. Unit tests create isolated temporary data directories. The evaluator builds separate temporary databases.
