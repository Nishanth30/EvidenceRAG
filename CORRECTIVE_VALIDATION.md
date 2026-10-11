# Final corrective validation

11 October 2026, local macOS ARM64, Python 3.11.16. No new dependencies or architecture changes. No paid APIs.

## Changes

- Generation returns strict JSON (`status`, `answer`, `citations`). The API distinguishes `answered`, `insufficient_evidence`, and `error`; generation errors include a reason code.
- Answered responses require nonempty text and valid supplied citation IDs. Optional inline references must agree with the list. Abstentions require empty text/citations and receive a standard backend refusal.
- Invalid JSON, duplicate keys, extra fields, wrong types, contradictory abstentions and invalid citation lists are withheld. Ollama requests JSON mode, supported by its [chat API](https://docs.ollama.com/api/chat).
- Default retrieval count increased from five to six. Threshold 0.30, chunking 800/150, encoder, index and context budget remain unchanged.

## Exact retrieval diagnosis

Question: “Two workers both see no record for the same event and then apply its update. Why is that unsafe, and what should enforce the decision?”

The expected evidence is `message_delivery.md`, characters 490–1174: the separate check/insert is unsafe under concurrent consumers, and the unique constraint and transaction must enforce the decision together. The complete text exists in a single stored chunk: no evidence-fragmentation failure was found. Real MiniLM ranked it **sixth, score 0.3396368**. Related retries/outbox/isolation passages ranked higher. The five-result cutoff excluded it despite passing the threshold. Six results include it as S6 within the existing 6000-character budget.

[Full measured ranking](evaluation/results/corrective/paraphrase-ranking.json). This is a targeted remedy to an observed ranking weakness, not a held-out retrieval improvement. Explicit top_k=5 still reproduces the omission. Existing benchmark files and their Recall@5/MRR@5 values were not modified or rerun.

## Real execution

The same three questions ran through actual FastAPI /ask handlers (TestClient), real MiniLM/FAISS, and real HTTP inference using local Ollama 0.40.2, Qwen2.5 3B. Model identity and complete request/response payloads are recorded. The test used a consistent SQLite backup of the five-document library. For every sent passage, the test checked equality with returned sources and the stored page substring at its offsets.

| Case | Final API outcome | Evidence and answer assessment | Wall time |
|---|---|---|---:|
| When should a consumer acknowledge a message? | answered | S1; correctly says after the durable business transaction commits. | 1077.5 ms |
| Two workers both see no record… | answered | S5/S6; identifies message-ID unique constraint plus business transaction. However, explains the danger via retries/duplicate events rather than clearly describing concurrent check-then-insert. Partial quality success. | 2814.2 ms |
| How many failed delivery attempts before dead-lettering? | insufficient_evidence | Empty model answer/citations; canonical API refusal. No numeric limit appears in the documents. Correct abstention despite strong topical retrieval. | 720.7 ms |

[Final raw responses](evaluation/results/corrective/verified-live/actual-results.json) and [structured-citation/source checks](evaluation/results/corrective/source-review.json). The raw recorder's `raw_cited_ids` fields refer only to optional inline brackets, which are absent in this run; the structured IDs are verified in source-review.json and returned as cited_source_ids by the API. The current recorder also saves structured citation checks on subsequent runs.

### Preserved unsuccessful iterations

The first [strict-contract run](evaluation/results/corrective/live/actual-results.json) withheld both answers for missing inline references and rejected malformed refusal JSON. The [JSON-mode run](evaluation/results/corrective/final-live/actual-results.json) fixed refusal serialization but still withheld answers because the initial contract redundantly required inline references and a citation list. Its paraphrase also confused transactional outbox behavior with deduplication.

The final contract uses one authoritative citation list, permits consistent inline references, and requests concise answers. No outputs were repaired, fabricated, or manually edited. These intermediate failures remain part of the record. Earlier pre-correction results remain in LIVE_GENERATION_VALIDATION.md.

## Automated regression validation

**55 passed, no failures/skips**, including all prior tests; five existing third-party SWIG deprecation warnings. [JUnit results](evaluation/results/corrective/tests.xml). Ruff passed for app, frontend, evaluation, tests and scripts.

New regression coverage includes valid citation-free abstention, contradictory abstention text/citations, plain-text refusals, fenced/malformed JSON, duplicate/extra keys, empty answers, invalid field types/statuses, empty/mismatched/duplicate citations, provider failure without upstream-detail leakage, and Ollama JSON-mode requests. Existing persistence, deletion, duplicate upload, context identity and retrieval recovery tests also passed.

The unit/API suite uses deterministic fake embeddings and mocked LLM outputs. These tests prove handling of those cases, not real model accuracy. The three live tests above use neither fake embeddings nor mocked generation. Earlier real lifecycle/evaluation evidence remains in ENGINEERING_AUDIT.md and VALIDATION.md.

## Remaining limitations and untested areas

- The paraphrased answer's causal explanation remains imprecise. Valid source IDs do not establish entailment; the backend does not detect a fluent unsupported answer with valid IDs.
- Structured status is still model-reported. Correct abstention on one near-topic question does not establish a calibrated rejection rate; the harder retrieval audit's four negatives all passed the similarity filter.
- Six passages increases context and may introduce distracting text. This case was used for tuning, not independent testing. Chunk input truncation and other paraphrases remain unmeasured in this pass.
- Live OpenAI-compatible generation, Docker execution, adversarial prompt injection, broad answer faithfulness, repeated-run stability and production concurrency were not tested here. The final browser UI was not re-exercised; API handlers, provider traffic and source data were verified.
- Schema/request errors and underlying retrieval/storage failures retain HTTP error handling; the three-state contract describes successfully returned /ask generation responses.

Reproduce with the approved local model running:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python scripts/validate_live_generation.py --output evaluation/results/new-live-run
.venv/bin/python -m pytest -q
```

Use a new output directory to preserve previous records. No optional enhancements were implemented.
