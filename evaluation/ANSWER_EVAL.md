# Answer-level evaluation

Retrieval metrics (Recall@k, MRR in [RESULTS.md](RESULTS.md)) say whether the evidence was found. This evaluation
grades the **answers**: the full `/ask` pipeline (retrieval → local LLM → response contract) on all 28 questions of
`evaluation/dataset.json`, graded by code (no LLM judge). Script: `evaluation/answer_eval.py`.

**Caveat.** Questions and documents were AI-authored together; this is a development set, not a benchmark.
"Supported" means every gold evidence quote is inside a passage the answer cites. It does not prove every word of
the answer is faithful.

Defaults: chunks 800/150 recursive, top-k 6, similarity threshold 0.30, temperature 0, Ollama on a 16 GB M5 laptop.

## Results

| | Qwen2.5 3B | Qwen2.5 7B, before fix | **Qwen2.5 7B, after fix** |
|---|---|---|---|
| Answerable (24): answered and supported by its citations | 22 | 19 | **23** |
| … direct / paraphrased / multi-evidence | 10/10 · 10/10 · 2/4 | 9/10 · 8/10 · 2/4 | 10/10 · 9/10 · 4/4 |
| Answered with partial support | 1 | 0 | 0 |
| **Answered without support (passed the contract but cited the wrong passages)** | **0** | **0** | **0** |
| Withheld by the response contract | 1 | 5 | 1 |
| Unanswerable (4): correctly refused | 4/4 | 4/4 | 4/4 |
| Citation precision (cited passages containing gold evidence) | 97.8 % | 100 % | 100 % |
| Latency per answer, median / p95 | 1.2 s / 3.2 s | 2.9 s / 4.5 s | 2.7 s / 4.6 s |

## What the evaluation found

**The citation check was withholding correct answers.** Four of the 7B's five withheld answers were correct and
cited the right passages, written as grouped citations: `... [S1, S3].` The earlier fix for the citation bypass
(an unknown ID hidden in a group, `[S99, S1]`) rejected *every* grouped bracket. Fix in
`app/generation/rag_pipeline.py`: a grouped bracket is accepted only if every ID in it was supplied, so `[S99, S1]`
is still withheld. Three regression tests in `tests/test_audit_regressions.py` (58 tests pass). Result: 19 → 23 of 24.

**Remaining failures are the contract doing its job.** The 7B's last withheld answer (q14) and the 3B's (q21) omitted
the required `citations` list; withholding them is correct behaviour. The 3B's partial answer (q22) cited one of the
two passages a multi-part question needed.

**3B vs 7B.** The 3B is twice as fast and nearly as accurate on single-fact questions, but weaker on questions that
need two passages (2/4 vs 4/4).

Raw per-question outputs, including the model text the contract withheld: `results/answer-eval/` (after the fix)
and `results/answer-eval-before-fix/`.
