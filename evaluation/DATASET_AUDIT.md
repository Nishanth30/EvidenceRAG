# Dataset audit — 11 October 2026

## Original 28 examples

I read all five complete source documents and checked each question and evidence anchor against its surrounding section. All 24 answerable questions have correctly located, relevant anchors; no wrong-file annotation or unsupported numerical answer was found. The four negative questions request information absent from the corpus. The exact source locations for every original positive label are saved in `results/audit/original-label-checks.json`.

The annotations still have important limits:

- q01–q20 are mostly definitions or close paraphrases of section-opening sentences. q05 asks for an application of atomicity; q16 asks for a simple reciprocal-rank calculation, for which the labeled formula does support 1/4. These are easy conceptual checks.
- q21–q24 each require two relevant concepts. Their anchors are relevant, but are not an exhaustive collection of every passage that could support an answer. In q24 the circuit breaker reacts to failures; it is not described as a general overload detector.
- q25 and q28 are obviously outside the document topics. q26 and q27 ask for missing organization-specific values, but provide weak coverage of adversarial near-topic unknowns.
- Full-anchor matching measures a particular evidence span. Useful alternative passages or split anchors can be marked as misses. Recall is evidence-span recall, not manual answerability judgment.

There is **no direct question/answer-file leakage into the index**: the evaluator ingests only the five `sample_documents/*.md` files. Their hashes match the original experiment. However, the original corpus and questions were authored together, giving strong construction bias and lexical overlap. There is no train/validation/test split or independent adjudication. Neither the original nor the new set supports an independent benchmark claim.

## Ten added challenges

`audit_dataset.json` is separate so the old results remain reproducible. It was finalized before the new retrieval run, with no subsequent label, threshold, model or chunking tuning. It contains six answerable and four near-topic unanswerable questions. Each positive stores an expected answer, semantic-review rationale and exact source offsets/line. Each negative records the missing specific information after reviewing the full corpus.

| ID | What is tested | Ground-truth review |
|---|---|---|
| h01 | Publisher crash after broker acceptance | Outbox paragraph explicitly permits duplicate publication and requires consumer deduplication. |
| h02 | Two workers racing after an absent-ID check | Idempotent consumers explicitly rejects separate check/insert and requires constraint plus transaction. |
| h03 | Doctors leaving duty under snapshots | Isolation explicitly identifies write skew and serializable equivalence. |
| h04 | Two-of-three quorums and linearizability | Quorum paragraph gives the overlap example and says ordering, concurrency and failures still matter. |
| h05 | Logs versus disk loss, then proving recovery | WAL section requires a separate backup strategy; Recovery testing requires restoring and checking data. |
| h06 | First hit present but only half the evidence | Recall paragraph supplies 1/2; Reciprocal rank paragraph supplies 1 for the first result. |
| h07 | Numeric dead-letter retry limit | No maximum attempt count appears in any document. |
| h08 | Exact circuit-breaker open duration | Only “after a delay” is supplied, with no numeric duration. |
| h09 | Deduplication retention days | No purge policy or retention interval is supplied. |
| h10 | Cosine cutoff guaranteeing 99% correctness | No cutoff/calibration is supplied; the embedding section warns similarity is not a correctness probability. |

“Unanswerable” here means the **requested specific value cannot be supplied**. An appropriate response can still explain its absence or reject a premise using the documents. It does not mean there are no topically relevant passages. This is exactly what the threshold test needs to distinguish.

The review is an explicit source-grounded AI audit, **not independent human verification**. The new questions still draw from a small, known corpus, and h03/h06 reuse scenarios described in the text. Their harder wording, cross-section requirements and near-topic negatives improve coverage without creating a rigorous held-out benchmark.
