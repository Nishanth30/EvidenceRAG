# Live RAG validation — completed with mixed outcomes

**Latest:** [Final corrective pass](CORRECTIVE_VALIDATION.md). The results below are historical and preserved.

**11 October 2026 (Asia/Kolkata).** Three real local LLM calls were executed. The straightforward answer passed, the paraphrased answer failed and was withheld, and the absent-fact query produced an appropriate refusal but the API classified it as `answered`. This is not an all-pass result.

## Provider and execution

With explicit user approval, installed Ollama through Homebrew and downloaded only `qwen2.5:3b` (1,929,912,432 bytes of model artifacts). Ollama version: **0.40.2**. Model digest: `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`.

The runtime detected the Apple M5 GPU; the machine has 16 GiB RAM. Ollama binds to `127.0.0.1:11434`, uses project storage `data/ollama-models`, has cloud features disabled, and uses a 4096-token context with one parallel request. No API costs were incurred.

The three tests invoked the existing FastAPI `/ask` handler through TestClient with real MiniLM retrieval, FAISS, and the production `LLMClient` making **actual HTTP requests to Ollama**. A recording transport delegated to the real network transport; it did not synthesize responses. A consistent SQLite backup of the running five-document library isolated the test from live writes. No prompts, thresholds, retrieval settings or application logic were changed. The existing contract used temperature 0 and a 700-token output limit.

All three Ollama responses returned HTTP 200, `done=true`, `done_reason=stop`. They generated 50, 221 and 67 tokens respectively, so none hit the output cap. Prompts contained 722, 858 and 719 tokens. The saved record includes the complete actual provider request and response, retrieved passages, API answer/status and source checks.

## Actual outcomes

| Test | Top similarity | API status | Time | Outcome |
|---|---:|---|---:|---|
| Straightforward | 0.6250 | `answered` | 3.166 s | Grounded answer; valid, supporting `[S1]` |
| Paraphrased | 0.4056 | `invalid_citations` | 4.330 s | Required evidence omitted; uncited, partly incorrect output withheld |
| Absent retry limit | 0.5876 | `answered` | 1.570 s | Model correctly declined to invent a number; valid `[S1]`; refusal status misclassified |

These are single sequential observations, not a latency benchmark. The first call includes about 1.54 seconds of model loading. Times measure the `/ask` handler in the test client, not browser/network end-to-end latency.

### 1. Straightforward answerable question

**Question:** When should a consumer acknowledge a message?

**Actual generated answer:**

> A consumer should acknowledge a message only after its durable business transaction commits. This ensures that the message is only acknowledged once the business logic has completed successfully, preventing the risk of losing work if the process crashes between acknowledging and committing. [S1]

`S1` identifies `message_delivery.md`, extracted characters 0–640. It includes both the acknowledgement-after-commit rule and the risk of acknowledging before commit. The answer is supported by that actual supplied passage. API output matched the generated answer.

### 2. Paraphrased question requiring retrieval

**Question:** Two workers both see no record for the same event and then apply its update. Why is that unsafe, and what should enforce the decision?

The source document explains that a separate check followed by an insert is unsafe concurrently, and that a uniqueness constraint and transaction must enforce the decision together. Those sentences are in `message_delivery.md`, line 13, but **neither was in the five passages sent to the model**.

The model generated a long response without citations. It described the missing idempotence protection but added an incorrect example: it said that incrementing a counter should have the same effect when applied once or repeatedly. An ordinary counter increment is not idempotent. That example was also unsupported by the supplied passages.

The backend withheld this response and returned its standard `invalid_citations` message. Thus the answer-quality test **failed**, while the missing-citation guard worked. The raw failure remains in the saved provider response; it was not silently repaired or replaced with a fabricated success.

### 3. Near-topic question with an absent answer

**Question:** How many failed delivery attempts must occur before a message is moved to the dead-letter queue?

**Actual generated answer:**

> [S1] states that a dead-letter queue isolates messages that repeatedly fail so they can be inspected and replayed. However, it does not specify how many failed delivery attempts must occur before a message is moved to the dead-letter queue. Therefore, the exact number of failed delivery attempts is not provided in the given evidence.

`S1` identifies `message_delivery.md`, characters 1524–2051. It discusses dead-letter queues and recommends a retry budget, but gives no numeric limit. Review of all five documents confirms the requested number is absent. The model's refusal is appropriate and the citation is valid.

However, the API returned `answered`, since the response had a valid citation. The retrieval gate did not abstain; the **model** declined the unsupported request. This one successful refusal does not establish reliable abstention across other questions or models.

## Citation and context verification

For all three calls, each source ID, filename, page and passage actually sent in the provider request matched the returned source object. The text also matched the exact SQLite page substring at the returned offsets. TXT/Markdown physical page is null. The first and third answers used only `[S1]`, which existed and supported the statements. The second contained no citations and was blocked.

Citation identity and factual support were checked separately. Identifier validation alone cannot establish entailment; the uncited incorrect counter example demonstrates why raw model output must be inspected even when the API withholds it.

## Abstention diagnosis and simplest recommended improvement

Similarity measures topical relevance rather than whether the requested fact exists. The absent retry-limit question scored 0.5876, above the answerable paraphrase's 0.4056. A single higher top-score threshold cannot reject the former while retaining the latter. The prior audit also found all four near-topic negatives passed the 0.30 gate.

Keep the same retrieval and single generation call. Explicitly instruct the model to check whether the passages supply the **specific requested value, fact or policy**, and return one exact abstention marker, such as `INSUFFICIENT_EVIDENCE`, when they do not. Recognize that exact marker before ordinary citation validation, map it to `status=insufficient_evidence`, and retain the evidence for inspection. Normal answers would continue to require valid citations.

This small prompt/response-contract adjustment would distinguish refusal from an answer and avoid rejecting a valid uncited refusal as `invalid_citations`. It remains a model judgment, not an answerability guarantee, and needs testing on separate near-topic negatives. Do not raise the threshold merely to fit these examples. The paraphrase's retrieval omission is a separate quality limitation; no retrieval tuning was done during validation.

**Recommendation only: no application changes or optional features were implemented.** Local provider configuration and the recording validation script were added.

## Artifacts and current state

- `evaluation/results/live-generation/actual-results.json`: complete real requests, raw responses, API outputs, model metadata and checks.
- `evaluation/results/live-generation/assessment.json`: per-query source-grounded judgments.
- `evaluation/results/live-generation/evidence-review.json`: required source anchors and whether they were supplied.
- `evaluation/results/live-generation/preflight.json`: historical no-provider execution; not a generated-answer result.
- `scripts/validate_live_generation.py`: reproduces exactly these three local calls.

The running backend now uses Ollama/Qwen2.5 3B via ignored `.env`. Health confirms `llm_configured=true`, five documents and 20 chunks. Streamlit's health endpoint returns 200. Ollama and the backend are running for this session; no login/background-service installation was configured.

To restart the local model server from the project directory:

```bash
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$PWD/data/ollama-models" OLLAMA_NO_CLOUD=1 OLLAMA_CONTEXT_LENGTH=4096 OLLAMA_NUM_PARALLEL=1 ollama serve
```

Then start the backend normally and, if desired, reproduce validation with:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python scripts/validate_live_generation.py
```

The stored weights are reused; this script downloads no models. Results may vary with runtime/model changes. Three queries do not establish production readiness, broad answer faithfulness or prompt-injection resistance. Docker and large-scale/concurrent behavior remain untested. The earlier 41-test audit is still the unit-test record; the application logic was unchanged in this phase and that suite was not redundantly rerun.
